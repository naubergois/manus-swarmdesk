"""Real LangGraph orchestrator for the control-plane pipeline."""

from __future__ import annotations

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
        card.column = KanbanColumn.TRIAGEM
        card.updated_at = datetime.utcnow()
        await store.upsert("task_cards", card)

        triage = await runners.run_triage(card)
        card.title = triage.title or card.title
        card.type = triage.type
        card.priority = triage.priority
        card.tags = list({*card.tags, *triage.tags, "triaged"})
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
        card.subtasks = [t.title for t in tasks]
        card.agents = plan.required_agents
        card.updated_at = datetime.utcnow()
        await store.upsert("execution_plans", plan)
        await store.upsert("task_cards", card)
        await self._audit(card, "plan_execution", card.column.value, card.column.value, {
            "tasks": len(tasks),
        })
        return {
            "card": card.model_dump(mode="json"),
            "plan": plan.model_dump(mode="json"),
        }

    async def _node_request_approval(self, state: PipelineState) -> PipelineState:
        store = get_store()
        card = TaskCard.model_validate(state["card"])
        previous = card.column
        card.column = KanbanColumn.AGUARDANDO_APROVACAO
        card.updated_at = datetime.utcnow()
        approval = HumanApproval(
            card_id=card.id,
            type=ApprovalType.ESCOPO,
            requester="supervisor",
            decision=ApprovalDecision.PENDENTE,
            comment="Escopo, requisitos e plano gerados por agentes LLM — aguardando aprovação humana.",
        )
        await store.upsert("approvals", approval)
        await store.upsert("task_cards", card)
        await self._audit(
            card,
            "request_human_approval",
            previous.value,
            card.column.value,
            {"approval_id": approval.id},
        )
        return {"card": card.model_dump(mode="json")}

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
