"""Real LangGraph orchestrator for the control-plane pipeline."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from app.agents import runners
from app.db import get_store
from app.models.contracts import (
    AuditEvent,
    ExecutionPlan,
    HumanApproval,
    PlanTask,
    RequirementSpecification,
    TaskCard,
)
from app.models.enums import ApprovalDecision, ApprovalType, KanbanColumn

logger = logging.getLogger(__name__)


class PipelineState(TypedDict, total=False):
    card: dict[str, Any]
    triage: dict[str, Any]
    requirements: dict[str, Any]
    plan: dict[str, Any]
    error: str


class LangGraphOrchestrator:
    def __init__(self) -> None:
        self._graph = self._build_graph()

    def _build_graph(self):
        graph = StateGraph(PipelineState)
        graph.add_node("classify", self._node_classify)
        graph.add_node("refine", self._node_refine)
        graph.add_node("plan", self._node_plan)
        graph.add_node("request_approval", self._node_request_approval)

        graph.add_edge(START, "classify")
        graph.add_edge("classify", "refine")
        graph.add_edge("refine", "plan")
        graph.add_edge("plan", "request_approval")
        graph.add_edge("request_approval", END)
        return graph.compile()

    async def receive_demand(self, card: TaskCard) -> TaskCard:
        await self._audit(card, "receive_demand", None, KanbanColumn.ENTRADA.value)
        result = await self._graph.ainvoke({"card": card.model_dump(mode="json")})
        if result.get("error"):
            raise RuntimeError(result["error"])
        return TaskCard.model_validate(result["card"])

    async def _node_classify(self, state: PipelineState) -> PipelineState:
        store = get_store()
        card = TaskCard.model_validate(state["card"])
        previous = card.column
        card.kind = "epic"
        card.column = KanbanColumn.TRIAGEM
        card.tags = list({*card.tags, "epic", "triaged"})
        card.updated_at = datetime.utcnow()
        await store.upsert("task_cards", card)

        triage = await runners.run_triage(card)
        card.title = triage.title or card.title
        card.type = triage.type
        card.priority = triage.priority
        card.tags = list({*card.tags, *triage.tags, "epic", "triaged"})
        card.updated_at = datetime.utcnow()
        await store.upsert("task_cards", card)
        await self._audit(
            card,
            "classify_task",
            previous.value,
            card.column.value,
            triage.model_dump(mode="json"),
        )
        return {"card": card.model_dump(mode="json"), "triage": triage.model_dump(mode="json")}

    async def _node_refine(self, state: PipelineState) -> PipelineState:
        store = get_store()
        card = TaskCard.model_validate(state["card"])
        from app.agents.schemas import TriageResult

        triage = TriageResult.model_validate(state["triage"]) if state.get("triage") else None
        previous = card.column
        card.column = KanbanColumn.REFINAMENTO
        card.updated_at = datetime.utcnow()
        await store.upsert("task_cards", card)

        req = await runners.run_requirements(card, triage)
        requirements = RequirementSpecification(
            card_id=card.id,
            objective=req.objective,
            context=req.context,
            functional=req.functional,
            non_functional=req.non_functional,
            business_rules=req.business_rules,
            constraints=req.constraints,
            acceptance_criteria=req.acceptance_criteria,
            assumptions=req.assumptions,
            out_of_scope=req.out_of_scope,
            open_questions=req.open_questions,
        )
        card.acceptance_criteria = requirements.acceptance_criteria
        card.updated_at = datetime.utcnow()
        await store.upsert("requirements", requirements)
        await store.upsert("task_cards", card)
        await self._audit(card, "refine_requirements", previous.value, card.column.value)
        return {
            "card": card.model_dump(mode="json"),
            "requirements": requirements.model_dump(mode="json"),
        }

    async def _node_plan(self, state: PipelineState) -> PipelineState:
        store = get_store()
        card = TaskCard.model_validate(state["card"])
        requirements = RequirementSpecification.model_validate(state["requirements"])
        from app.agents.schemas import RequirementsResult

        req_for_llm = RequirementsResult(
            objective=requirements.objective,
            context=requirements.context,
            functional=requirements.functional,
            non_functional=requirements.non_functional,
            business_rules=requirements.business_rules,
            constraints=requirements.constraints,
            acceptance_criteria=requirements.acceptance_criteria,
            assumptions=requirements.assumptions,
            out_of_scope=requirements.out_of_scope,
            open_questions=requirements.open_questions,
        )
        plan_out = await runners.run_planner(card, req_for_llm)
        tasks = [
            PlanTask(
                title=t.title,
                agent_role=t.agent_role,
                parallel_group=t.parallel_group,
                depends_on=t.depends_on,
            )
            for t in plan_out.tasks
        ]
        # Ensure at least a few architecture work cards so the board always animates.
        if not tasks:
            tasks = [
                PlanTask(title="Scaffold app shell", agent_role="Forge", parallel_group=0),
                PlanTask(title="Implement core features", agent_role="Forge", parallel_group=1),
                PlanTask(title="Review & harden", agent_role="Lens", parallel_group=2),
                PlanTask(title="Test & ship preview", agent_role="Lens", parallel_group=3),
            ]

        plan = ExecutionPlan(
            card_id=card.id,
            objective=plan_out.objective,
            strategy=plan_out.strategy,
            tasks=tasks,
            required_agents=plan_out.required_agents,
            tools=plan_out.tools,
            risks=plan_out.risks,
            estimated_effort_hours=plan_out.estimated_effort_hours,
            completion_criteria=plan_out.completion_criteria or card.acceptance_criteria,
        )
        card.kind = "epic"
        card.subtasks = [t.title for t in tasks]
        card.agents = plan.required_agents
        card.tags = list({*card.tags, "epic", "architected"})
        card.updated_at = datetime.utcnow()
        await store.upsert("execution_plans", plan)
        await store.upsert("task_cards", card)

        # Work cards are materialised only after human scope approval — never auto-spawn.
        await self._audit(
            card,
            "plan_execution",
            KanbanColumn.REFINAMENTO.value,
            KanbanColumn.REFINAMENTO.value,
            {"tasks": len(tasks), "child_ids": []},
        )
        return {
            "card": card.model_dump(mode="json"),
            "plan": plan.model_dump(mode="json"),
        }

    async def _node_request_approval(self, state: PipelineState) -> PipelineState:
        """Pause for human scope approval before swarm / work cards / app deploy."""
        store = get_store()
        card = TaskCard.model_validate(state["card"])
        previous = card.column
        card.column = KanbanColumn.AGUARDANDO_APROVACAO
        card.kind = "epic"
        card.tags = list({*card.tags, "epic", "awaiting_approval"})
        card.updated_at = datetime.utcnow()
        await store.upsert("task_cards", card)

        approval = HumanApproval(
            card_id=card.id,
            type=ApprovalType.ESCOPO,
            requester="supervisor",
            decision=ApprovalDecision.PENDENTE,
            comment=(
                "Escopo e plano prontos. Aprove para criar os cartões de trabalho "
                "e liberar o enxame para construir/deployar a aplicação."
            ),
        )
        await store.upsert("approvals", approval)
        await self._audit(
            card,
            "request_scope_approval",
            previous.value,
            card.column.value,
            {"approval_id": approval.id, "auto": False},
        )
        return {"card": card.model_dump(mode="json")}

    async def materialize_work_cards(self, card: TaskCard) -> list[str]:
        """Create child work cards from the execution plan (idempotent)."""
        store = get_store()
        existing = await store.list("task_cards", {"parent_id": card.id})
        if existing:
            return [row["id"] for row in existing]

        plans = await store.list("execution_plans", {"card_id": card.id})
        if not plans:
            return []
        plan = ExecutionPlan.model_validate(plans[-1])
        child_ids: list[str] = []
        for task in plan.tasks:
            child = TaskCard(
                title=task.title,
                description=(
                    f"Work item for epic **{card.title}**.\n\n"
                    f"Role: {task.agent_role}\n"
                    f"Group: {task.parallel_group}\n\n"
                    f"{card.description[:500]}"
                ),
                type=card.type,
                project_id=card.project_id,
                board_id=card.board_id,
                priority=card.priority,
                kind="work",
                parent_id=card.id,
                plan_task_id=task.id,
                column=KanbanColumn.PRONTO_ENXAME,
                agents=[task.agent_role],
                tags=["work", f"agent:{task.agent_role}", f"group:{task.parallel_group}"],
                autonomy_level=card.autonomy_level,
            )
            await store.upsert("task_cards", child)
            child_ids.append(child.id)
            await asyncio.sleep(0.9)
        return child_ids

    async def start_swarm_after_approval(self, card_id: str) -> TaskCard:
        """Materialize work cards and start Ruflo in the background after scope approval."""
        store = get_store()
        raw = await store.get("task_cards", card_id)
        if not raw:
            raise RuntimeError(f"Card {card_id} not found")
        card = TaskCard.model_validate(raw)
        card.column = KanbanColumn.PRONTO_ENXAME
        card.tags = list({*card.tags, "epic", "swarm_queued"})
        card.updated_at = datetime.utcnow()
        await store.upsert("task_cards", card)
        await self.materialize_work_cards(card)
        asyncio.create_task(self._run_swarm_safe(card.id))
        return card

    async def _run_swarm_safe(self, card_id: str) -> None:
        from app.adapters.ruflo_swarm import ruflo

        task = asyncio.current_task()
        if task:
            ruflo.register_task(card_id, task)
        try:
            store = get_store()
            raw = await store.get("task_cards", card_id)
            if not raw:
                return
            card = TaskCard.model_validate(raw)
            await ruflo.create_mission(card)
            await ruflo.execute(card)
        except asyncio.CancelledError:
            logger.info("Background swarm stopped for %s", card_id)
            raise
        except Exception:
            logger.exception("Background swarm failed for %s", card_id)
            try:
                store = get_store()
                raw = await store.get("task_cards", card_id)
                if raw:
                    card = TaskCard.model_validate(raw)
                    card.tags = list({*card.tags, "swarm_error"})
                    card.updated_at = datetime.utcnow()
                    await store.upsert("task_cards", card)
            except Exception:
                logger.exception("Failed to mark swarm_error on %s", card_id)
        finally:
            if task:
                ruflo.unregister_task(card_id, task)

    async def _audit(
        self,
        card: TaskCard,
        action: str,
        previous: str | None,
        nxt: str | None,
        result: dict | None = None,
    ) -> None:
        store = get_store()
        event = AuditEvent(
            card_id=card.id,
            actor="langgraph",
            action=action,
            previous_state=previous,
            next_state=nxt,
            result=result or {},
        )
        await store.insert("audit_events", event)


langgraph = LangGraphOrchestrator()
