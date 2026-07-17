"""Hierarchical swarm execution (Ruflo-style topology) powered by real LLM agents.

Ruflo MCP/CLI is an external harness for Claude Code; this adapter implements the
same control contract inside SwarmDesk using LangChain specialists coordinated
hierarchically by a coordinator design step.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any, TypedDict

logger = logging.getLogger(__name__)

from langgraph.graph import END, START, StateGraph

from app.agents import runners
from app.agents.schemas import RequirementsResult
from app.db import get_store
from app.models.contracts import (
    AgentAssignment,
    AuditEvent,
    ExecutionPlan,
    HumanApproval,
    RequirementSpecification,
    ReviewDecision,
    SupportTicket,
    SwarmMission,
    TaskCard,
    TestFailure,
    TestResult,
    WorkArtifact,
)
from app.models.enums import (
    ApprovalDecision,
    ApprovalType,
    KanbanColumn,
    ReviewVerdict,
    TicketCategory,
    TicketStatus,
)
from app.services import agent_bus as a2a

_CHILD_MOVE_DELAY_S = 1.05


class SwarmState(TypedDict, total=False):
    card: dict[str, Any]
    requirements: dict[str, Any]
    plan: dict[str, Any]
    mission: dict[str, Any]
    implementation: dict[str, Any]
    review: dict[str, Any]
    tests: dict[str, Any]
    documentation: dict[str, Any]
    feedback: str
    correction_round: int
    error: str


class RufloSwarmManager:
    def __init__(self) -> None:
        self._graph = self._build_graph()
        self._tasks: dict[str, asyncio.Task[None]] = {}

    def register_task(self, card_id: str, task: asyncio.Task[None]) -> None:
        self._tasks[card_id] = task

    def unregister_task(self, card_id: str, task: asyncio.Task[None]) -> None:
        if self._tasks.get(card_id) is task:
            self._tasks.pop(card_id, None)

    def _build_graph(self):
        graph = StateGraph(SwarmState)
        graph.add_node("design_swarm", self._node_design)
        graph.add_node("execute_dev", self._node_execute_dev)
        graph.add_node("review", self._node_review)
        graph.add_node("test", self._node_test)
        graph.add_node("document", self._node_document)
        graph.add_node("prepare_delivery", self._node_prepare_delivery)

        graph.add_edge(START, "design_swarm")
        graph.add_edge("design_swarm", "execute_dev")
        graph.add_edge("execute_dev", "review")
        graph.add_conditional_edges(
            "review",
            self._route_after_review,
            {"test": "test", "fix": "execute_dev", "block": END},
        )
        graph.add_conditional_edges(
            "test",
            self._route_after_test,
            {"document": "document", "fix": "execute_dev", "block": END},
        )
        graph.add_edge("document", "prepare_delivery")
        graph.add_edge("prepare_delivery", END)
        return graph.compile()

    def _route_after_review(self, state: SwarmState) -> str:
        if state.get("error"):
            return "block"
        review = state.get("review") or {}
        if review.get("decision") == ReviewVerdict.REPROVADO.value:
            round_n = int(state.get("correction_round") or 0)
            return "fix" if round_n < 1 else "block"
        return "test"

    def _route_after_test(self, state: SwarmState) -> str:
        if state.get("error"):
            round_n = int(state.get("correction_round") or 0)
            return "fix" if round_n < 1 else "block"
        return "document"

    async def _list_children(self, epic_id: str) -> list[TaskCard]:
        store = get_store()
        rows = await store.list("task_cards", {"parent_id": epic_id})
        children = [TaskCard.model_validate(r) for r in rows]
        return sorted(children, key=lambda c: c.created_at)

    async def _move_children(
        self,
        epic_id: str,
        column: KanbanColumn,
        *,
        stagger: bool = True,
        by_group: bool = False,
    ) -> list[str]:
        """Move work cards belonging to an epic into a column (visible on Kanban)."""
        store = get_store()
        children = await self._list_children(epic_id)
        if not children:
            return []

        epic_raw = await store.get("task_cards", epic_id)
        epic = TaskCard.model_validate(epic_raw) if epic_raw else None
        narrate_columns = {
            KanbanColumn.EM_EXECUCAO,
            KanbanColumn.EM_REVISAO,
            KanbanColumn.EM_TESTES,
            KanbanColumn.PRONTO_ENTREGA,
            KanbanColumn.CONCLUIDO,
        }

        async def _narrate_move(child: TaskCard) -> None:
            if not epic or column not in narrate_columns:
                return
            agent = child.agents[0] if child.agents else "desenvolvedor"
            await a2a.publish_a2a(
                epic,
                agent,
                f"«{child.title}» em andamento — coluna {column.value.replace('_', ' ')}.",
                message_type="status",
                pipeline_step="move_work",
            )

        if by_group:
            groups: dict[int, list[TaskCard]] = {}
            for child in children:
                group = 0
                for tag in child.tags:
                    if tag.startswith("group:"):
                        try:
                            group = int(tag.split(":", 1)[1])
                        except ValueError:
                            group = 0
                groups.setdefault(group, []).append(child)
            moved: list[str] = []
            for group in sorted(groups):
                for child in groups[group]:
                    child.column = column
                    child.updated_at = datetime.utcnow()
                    await store.upsert("task_cards", child)
                    moved.append(child.id)
                    await _narrate_move(child)
                if stagger:
                    await asyncio.sleep(_CHILD_MOVE_DELAY_S)
            return moved

        moved = []
        for child in children:
            child.column = column
            child.updated_at = datetime.utcnow()
            await store.upsert("task_cards", child)
            moved.append(child.id)
            await _narrate_move(child)
            if stagger:
                await asyncio.sleep(_CHILD_MOVE_DELAY_S)
        return moved

    async def create_mission(self, card: TaskCard) -> SwarmMission:
        store = get_store()
        plans = await store.list("execution_plans", {"card_id": card.id})
        if not plans:
            raise RuntimeError("Execution plan missing — cannot form swarm")
        plan = ExecutionPlan.model_validate(plans[-1])
        design = await runners.run_swarm_design(card, plan)

        agents: list[AgentAssignment] = [
            AgentAssignment(
                agent_id=item.agent_id,
                role=item.role,
                subtask=item.subtask,
                tools=item.tools,
                status="assigned",
            )
            for item in design.agents
        ]
        if not agents:
            agents = [
                AgentAssignment(agent_id="coordenador", role="coordenador", subtask="Coordenar", tools=["swarm"]),
                AgentAssignment(agent_id="desenvolvedor", role="desenvolvedor", subtask="Implementar", tools=["git"]),
                AgentAssignment(agent_id="testador", role="testador", subtask="Testar", tools=["tests"]),
                AgentAssignment(agent_id="revisor", role="revisor", subtask="Revisar", tools=["review"]),
                AgentAssignment(agent_id="documentacao", role="documentacao", subtask="Documentar", tools=["docs"]),
            ]

        mission = SwarmMission(
            card_id=card.id,
            objective=design.objective or card.title,
            topology=design.topology or "hierarchical",
            agents=agents,
            allowed_tools=design.allowed_tools or ["git", "tests", "docs", "review"],
            limits={"max_agents": len(agents), "token_budget": card.budget_tokens},
            consensus_policy=design.consensus_policy,
            escalation_policy=design.escalation_policy,
            expected_result=design.expected_result,
            status="running",
            progress=0.1,
        )
        card.column = KanbanColumn.PRONTO_ENXAME
        card.agents = [a.agent_id for a in agents]
        card.updated_at = datetime.utcnow()
        await store.upsert("swarm_missions", mission)
        await store.upsert("task_cards", card)
        await self._audit(card, "create_swarm", KanbanColumn.PRONTO_ENXAME.value, {
            "mission_id": mission.id,
            "topology": mission.topology,
        })
        agent_names = ", ".join(a.agent_id for a in agents[:5])
        extra = f" (+{len(agents) - 5})" if len(agents) > 5 else ""
        await a2a.publish_a2a(
            card,
            "coordenador",
            (
                f"Enxame montado ({mission.topology}): {len(agents)} agentes "
                f"— {agent_names}{extra}. Objetivo: {mission.objective[:100]}."
            ),
            message_type="status",
            pipeline_step="design_swarm",
        )
        return mission

    async def stop_mission(self, mission_id: str) -> SwarmMission | None:
        store = get_store()
        raw = await store.get("swarm_missions", mission_id)
        if not raw:
            return None

        mission = SwarmMission.model_validate(raw)
        task = self._tasks.get(mission.card_id)
        if task and not task.done():
            task.cancel()

        mission.status = "stopped"
        mission.updated_at = datetime.utcnow()
        if not mission.errors or mission.errors[-1] != "Missão parada pelo usuário":
            mission.errors.append("Missão parada pelo usuário")
        for agent in mission.agents:
            if agent.status not in {"completed", "stopped"}:
                agent.status = "stopped"
        await store.upsert("swarm_missions", mission)

        card_raw = await store.get("task_cards", mission.card_id)
        if card_raw:
            card = TaskCard.model_validate(card_raw)
            previous = card.column
            if card.column not in {KanbanColumn.CONCLUIDO, KanbanColumn.CANCELADO}:
                card.column = KanbanColumn.CANCELADO
            card.tags = list({*card.tags, "swarm_stopped"})
            card.block_reason = "Enxame parado pelo usuário."
            card.updated_at = datetime.utcnow()
            await store.upsert("task_cards", card)
            await self._move_children(card.id, KanbanColumn.CANCELADO, stagger=False)
            await self._audit(
                card,
                "stop_swarm",
                card.column.value,
                {"mission_id": mission.id, "previous_state": previous.value},
            )
            from app.services import project_manager

            try:
                await project_manager.announce(
                    card,
                    f"⏹️ Enxame parado. «{card.title}» foi para cancelado — board atualizado.",
                    pipeline_step="pm_swarm_stop",
                )
            except Exception:
                logger.exception("Nova swarm-stop announce failed")

        return mission

    async def _latest_mission_for_card(self, card_id: str) -> SwarmMission | None:
        store = get_store()
        rows = await store.list("swarm_missions", {"card_id": card_id})
        if not rows:
            return None
        items = [SwarmMission.model_validate(r) for r in rows]
        return sorted(items, key=lambda m: m.updated_at, reverse=True)[0]

    async def stop_card(self, card_id: str) -> SwarmMission:
        """Stop swarm for a card even when no mission row exists (e.g. after restart)."""
        store = get_store()
        mission = await self._latest_mission_for_card(card_id)
        if mission:
            stopped = await self.stop_mission(mission.id)
            if stopped:
                return stopped

        task = self._tasks.get(card_id)
        if task and not task.done():
            task.cancel()

        card_raw = await store.get("task_cards", card_id)
        if not card_raw:
            raise LookupError("Cartão não encontrado")
        card = TaskCard.model_validate(card_raw)
        previous = card.column
        if card.column not in {KanbanColumn.CONCLUIDO, KanbanColumn.CANCELADO}:
            card.column = KanbanColumn.CANCELADO
        card.tags = list({*card.tags, "swarm_stopped"})
        card.block_reason = "Enxame parado pelo usuário."
        card.updated_at = datetime.utcnow()
        await store.upsert("task_cards", card)
        await self._move_children(card.id, KanbanColumn.CANCELADO, stagger=False)

        mission = SwarmMission(
            card_id=card.id,
            objective=card.title,
            status="stopped",
            progress=0.0,
            errors=["Missão parada pelo usuário"],
            agents=[
                AgentAssignment(
                    agent_id="coordenador",
                    role="coordenador",
                    subtask="Coordenar",
                    tools=["swarm"],
                    status="stopped",
                )
            ],
        )
        await store.upsert("swarm_missions", mission)
        await self._audit(
            card,
            "stop_swarm",
            card.column.value,
            {"mission_id": mission.id, "previous_state": previous.value, "via": "card"},
        )
        return mission

    async def start_mission(self, mission_id: str) -> SwarmMission | None:
        """Resume or relaunch a stopped / idle mission in the background."""
        store = get_store()
        raw = await store.get("swarm_missions", mission_id)
        if not raw:
            return None

        mission = SwarmMission.model_validate(raw)
        return await self.start_card(mission.card_id)

    async def start_card(self, card_id: str) -> SwarmMission:
        """Start or resume swarm for a card (creates mission if missing)."""
        store = get_store()
        card_raw = await store.get("task_cards", card_id)
        if not card_raw:
            raise LookupError("Cartão não encontrado")
        card = TaskCard.model_validate(card_raw)

        running = self._tasks.get(card.id)
        if running and not running.done():
            existing = await self._latest_mission_for_card(card.id)
            if existing:
                return existing

        mission = await self._latest_mission_for_card(card.id)
        if mission:
            mission.status = "running"
            mission.progress = max(mission.progress, 0.1)
            mission.updated_at = datetime.utcnow()
            mission.errors = [e for e in mission.errors if e != "Missão parada pelo usuário"]
            for agent in mission.agents:
                if agent.status in {"stopped", "failed", "blocked", "error"}:
                    agent.status = "assigned"
                    agent.output_summary = None
            await store.upsert("swarm_missions", mission)
        else:
            # Prefer creating a full mission when plan/requirements exist; else stub + execute.
            try:
                mission = await self.create_mission(card)
            except Exception:
                logger.exception("create_mission failed for %s; using stub mission", card.id)
                mission = SwarmMission(
                    card_id=card.id,
                    objective=card.title,
                    status="running",
                    progress=0.1,
                    agents=[
                        AgentAssignment(
                            agent_id="coordenador",
                            role="coordenador",
                            subtask="Coordenar",
                            tools=["swarm"],
                            status="assigned",
                        ),
                        AgentAssignment(
                            agent_id="desenvolvedor",
                            role="desenvolvedor",
                            subtask="Implementar",
                            tools=["git"],
                            status="assigned",
                        ),
                    ],
                )
                await store.upsert("swarm_missions", mission)

        previous = card.column
        card.column = KanbanColumn.PRONTO_ENXAME
        card.tags = [t for t in card.tags if t not in {"swarm_stopped", "swarm_error"}]
        card.tags = list({*card.tags, "swarm_queued"})
        if (card.kind or "epic") == "epic":
            card.tags = list({*card.tags, "epic"})
        card.block_reason = None
        card.updated_at = datetime.utcnow()
        await store.upsert("task_cards", card)

        # Ensure planned work is visible as nested child cards before the swarm runs.
        if (card.kind or "epic") == "epic" and not card.parent_id:
            try:
                from app.adapters.langgraph_orchestrator import langgraph

                await langgraph.materialize_work_cards(card)
            except Exception:
                logger.exception("Failed to materialize work cards for %s", card.id)

        await self._move_children(card.id, KanbanColumn.PRONTO_ENXAME, stagger=False)
        await a2a.publish_a2a(
            card,
            "coordenador",
            f"Enxame iniciado para «{card.title}» — agentes entrando em ação.",
            message_type="status",
            pipeline_step="start_swarm",
        )
        from app.services import project_manager

        try:
            await project_manager.announce(
                card,
                (
                    f"🚀 Enxame em marcha para «{card.title}». "
                    "Vou acompanhar cada coluna e narrar o progresso no board."
                ),
                pipeline_step="pm_swarm_start",
            )
        except Exception:
            logger.exception("Nova swarm-start announce failed")
        await self._audit(
            card,
            "start_swarm",
            card.column.value,
            {"mission_id": mission.id, "previous_state": previous.value, "via": "card"},
        )

        asyncio.create_task(self._run_mission_safe(card.id))
        return mission

    async def _run_mission_safe(self, card_id: str) -> None:
        task = asyncio.current_task()
        if task:
            self.register_task(card_id, task)
        try:
            store = get_store()
            raw = await store.get("task_cards", card_id)
            if not raw:
                return
            card = TaskCard.model_validate(raw)
            await self.execute(card)
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
                self.unregister_task(card_id, task)

    async def _ensure_requirements_and_plan(self, card: TaskCard) -> None:
        """Generate requirements/plan on demand so seed or manual cards can start the swarm."""
        store = get_store()
        reqs = await store.list("requirements", {"card_id": card.id})
        if not reqs:
            req_out = await runners.run_requirements(card)
            spec = RequirementSpecification(
                card_id=card.id,
                objective=req_out.objective,
                context=req_out.context,
                functional=req_out.functional,
                non_functional=req_out.non_functional,
                business_rules=req_out.business_rules,
                constraints=req_out.constraints,
                acceptance_criteria=req_out.acceptance_criteria,
                assumptions=req_out.assumptions,
                out_of_scope=req_out.out_of_scope,
                open_questions=req_out.open_questions,
            )
            await store.upsert("requirements", spec)
            await self._audit(card, "autogenerate_requirements", card.column.value, {"spec_id": spec.id})
            await a2a.publish_a2a(
                card,
                "requisitos",
                f"Requisitos gerados para «{card.title}» — {len(spec.functional)} itens funcionais.",
                message_type="status",
                pipeline_step="autogenerate_requirements",
            )
            reqs = [spec.model_dump(mode="json")]

        plans = await store.list("execution_plans", {"card_id": card.id})
        if not plans:
            spec = RequirementSpecification.model_validate(reqs[-1])
            req_llm = RequirementsResult(
                objective=spec.objective,
                context=spec.context,
                functional=spec.functional,
                non_functional=spec.non_functional,
                business_rules=spec.business_rules,
                constraints=spec.constraints,
                acceptance_criteria=spec.acceptance_criteria,
                assumptions=spec.assumptions,
                out_of_scope=spec.out_of_scope,
                open_questions=spec.open_questions,
            )
            plan_out = await runners.run_planner(card, req_llm)
            from app.models.contracts import PlanTask

            tasks = [
                PlanTask(
                    title=t.title,
                    agent_role=t.agent_role,
                    parallel_group=t.parallel_group,
                    depends_on=t.depends_on,
                )
                for t in plan_out.tasks
            ] or [
                PlanTask(title="Scaffold app shell", agent_role="desenvolvedor", parallel_group=0),
                PlanTask(title="Implement core features", agent_role="desenvolvedor", parallel_group=1),
                PlanTask(title="Review & harden", agent_role="revisor", parallel_group=2),
                PlanTask(title="Test & ship preview", agent_role="testador", parallel_group=3),
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
            await store.upsert("execution_plans", plan)
            await self._audit(card, "autogenerate_plan", card.column.value, {"plan_id": plan.id})
            await a2a.publish_a2a(
                card,
                "planejador",
                f"Plano gerado com {len(tasks)} tarefas para o enxame.",
                message_type="status",
                pipeline_step="autogenerate_plan",
            )

    async def execute(self, card: TaskCard) -> TaskCard:
        store = get_store()
        await self._ensure_requirements_and_plan(card)
        reqs = await store.list("requirements", {"card_id": card.id})
        plans = await store.list("execution_plans", {"card_id": card.id})
        missions = await store.list("swarm_missions", {"card_id": card.id})
        if not missions:
            await self.create_mission(card)
            missions = await store.list("swarm_missions", {"card_id": card.id})

        result = await self._graph.ainvoke(
            {
                "card": card.model_dump(mode="json"),
                "requirements": reqs[-1],
                "plan": plans[-1],
                "mission": missions[-1],
                "correction_round": 0,
                "feedback": "",
            }
        )
        if result.get("error"):
            return await self._block_with_ticket(TaskCard.model_validate(result["card"]), result["error"])
        return TaskCard.model_validate(result["card"])

    async def _node_design(self, state: SwarmState) -> SwarmState:
        # Mission already created; mark progress.
        store = get_store()
        card = TaskCard.model_validate(state["card"])
        mission = SwarmMission.model_validate(state["mission"])
        mission.progress = 0.15
        mission.status = "coordinating"
        mission.updated_at = datetime.utcnow()
        await store.upsert("swarm_missions", mission)
        await a2a.publish_a2a(
            card,
            "coordenador",
            "Coordenando o enxame — distribuindo tarefas entre os agentes.",
            message_type="status",
            pipeline_step="design_swarm",
        )
        return {"mission": mission.model_dump(mode="json"), "card": card.model_dump(mode="json")}

    async def _node_execute_dev(self, state: SwarmState) -> SwarmState:
        store = get_store()
        card = TaskCard.model_validate(state["card"])
        requirements = RequirementSpecification.model_validate(state["requirements"])
        plan = ExecutionPlan.model_validate(state["plan"])
        mission = SwarmMission.model_validate(state["mission"])

        card.column = KanbanColumn.EM_EXECUCAO
        card.updated_at = datetime.utcnow()
        await store.upsert("task_cards", card)
        await self._move_children(card.id, KanbanColumn.EM_EXECUCAO, by_group=True)

        req_llm = RequirementsResult(
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
        feedback = state.get("feedback") or ""
        if feedback:
            card.description = (
                f"{card.description}\n\n---\nCorreção solicitada pelo enxame:\n{feedback}"
            )
            state["correction_round"] = int(state.get("correction_round") or 0) + 1
            state["error"] = ""
            state["feedback"] = ""
            await a2a.publish_a2a(
                card,
                "revisor",
                f"Correção solicitada ao desenvolvedor: {feedback[:220]}{'…' if len(feedback) > 220 else ''}",
                to_agent="desenvolvedor",
                message_type="handoff",
                pipeline_step="execute_dev",
            )

        await a2a.publish_a2a(
            card,
            "desenvolvedor",
            "Iniciando implementação da mini-app e deploy do preview.",
            to_agent="revisor",
            message_type="status",
            pipeline_step="execute_dev",
        )
        implementation = await runners.run_developer(card, req_llm, plan)
        from app.services.runtime import deploy_app

        card = deploy_app(card, implementation)
        card.budget_spent += 48_000
        card.updated_at = datetime.utcnow()
        for agent in mission.agents:
            if agent.role in {"desenvolvedor", "developer", "backend", "frontend", "Forge"}:
                agent.status = "completed"
                agent.output_summary = (
                    f"{implementation.summary[:200]} · live {card.preview_url or 'n/a'}"
                )
        mission.progress = 0.45
        mission.status = "executing"
        mission.updated_at = datetime.utcnow()
        await store.upsert("swarm_missions", mission)
        await store.upsert("task_cards", card)
        await self._artifact(
            card,
            "code",
            "implementation.md",
            implementation.summary,
            "desenvolvedor",
            card.preview_url or f"artifacts://{card.id}/implementation.md",
            implementation.artifact_markdown,
        )
        if card.preview_url:
            await self._artifact(
                card,
                "runtime",
                "live-preview",
                f"Mini-app deployed at {card.preview_url}",
                "desenvolvedor",
                card.preview_url,
                f"port={card.runtime_port}",
            )
        await self._audit(card, "execute_subtasks", KanbanColumn.EM_EXECUCAO.value, {
            "files": implementation.files_changed,
            "preview_url": card.preview_url,
            "runtime_status": card.runtime_status,
        })
        preview = card.preview_url or "sem preview"
        await a2a.publish_a2a(
            card,
            "desenvolvedor",
            (
                f"Implementação concluída — {len(implementation.files_changed)} arquivo(s). "
                f"Preview: {preview}. Encaminhando para revisão."
            ),
            to_agent="revisor",
            message_type="handoff",
            pipeline_step="execute_dev",
        )
        return {
            "card": card.model_dump(mode="json"),
            "mission": mission.model_dump(mode="json"),
            "implementation": implementation.model_dump(mode="json"),
            "correction_round": int(state.get("correction_round") or 0),
            "error": "",
            "feedback": "",
        }

    async def _node_review(self, state: SwarmState) -> SwarmState:
        store = get_store()
        card = TaskCard.model_validate(state["card"])
        requirements = RequirementSpecification.model_validate(state["requirements"])
        from app.agents.schemas import ImplementationResult

        implementation = ImplementationResult.model_validate(state["implementation"])
        mission = SwarmMission.model_validate(state["mission"])

        card.column = KanbanColumn.EM_REVISAO
        card.budget_spent += 18_000
        card.updated_at = datetime.utcnow()
        await store.upsert("task_cards", card)
        await self._move_children(card.id, KanbanColumn.EM_REVISAO)

        req_llm = RequirementsResult(
            objective=requirements.objective,
            context=requirements.context,
            functional=requirements.functional,
            non_functional=requirements.non_functional,
            business_rules=requirements.business_rules,
            constraints=requirements.constraints,
            acceptance_criteria=requirements.acceptance_criteria,
        )
        review_out = await runners.run_reviewer(card, req_llm, implementation)
        review = ReviewDecision(
            card_id=card.id,
            decision=review_out.decision,
            issues=review_out.issues,
            severity=review_out.severity,
            requirements_met=review_out.requirements_met,
            required_fixes=review_out.required_fixes,
            rationale=review_out.rationale,
            confidence=review_out.confidence,
            reviewer="revisor",
        )
        for agent in mission.agents:
            if agent.role in {"revisor", "reviewer"}:
                agent.status = "completed"
                agent.output_summary = review.rationale[:280]
        mission.progress = 0.7
        mission.updated_at = datetime.utcnow()
        await store.upsert("reviews", review)
        await store.upsert("swarm_missions", mission)
        await store.upsert("task_cards", card)
        await self._audit(card, "review_artifacts", KanbanColumn.EM_REVISAO.value, {
            "decision": review.decision.value,
        })

        verdict = "aprovado" if review.decision != ReviewVerdict.REPROVADO else "reprovado"
        await a2a.publish_a2a(
            card,
            "revisor",
            (
                f"Revisão {verdict} — {review.rationale[:180]}"
                f"{'…' if len(review.rationale) > 180 else ''}"
            ),
            to_agent="testador" if review.decision != ReviewVerdict.REPROVADO else "desenvolvedor",
            message_type="result" if review.decision != ReviewVerdict.REPROVADO else "handoff",
            pipeline_step="review",
        )

        if review.decision == ReviewVerdict.REPROVADO:
            round_n = int(state.get("correction_round") or 0)
            feedback = "Revisão reprovada: " + review.rationale
            if review.required_fixes:
                feedback += "\nCorreções: " + "; ".join(review.required_fixes)
            if round_n < 1:
                return {
                    "card": card.model_dump(mode="json"),
                    "mission": mission.model_dump(mode="json"),
                    "review": review.model_dump(mode="json"),
                    "feedback": feedback,
                    "correction_round": round_n,
                    "error": "",
                }
            return {
                "card": card.model_dump(mode="json"),
                "error": feedback,
            }
        return {
            "card": card.model_dump(mode="json"),
            "mission": mission.model_dump(mode="json"),
            "review": review.model_dump(mode="json"),
            "error": "",
        }

    async def _node_test(self, state: SwarmState) -> SwarmState:
        if state.get("error"):
            return state
        store = get_store()
        card = TaskCard.model_validate(state["card"])
        requirements = RequirementSpecification.model_validate(state["requirements"])
        from app.agents.schemas import ImplementationResult

        implementation = ImplementationResult.model_validate(state["implementation"])
        mission = SwarmMission.model_validate(state["mission"])

        card.column = KanbanColumn.EM_TESTES
        card.budget_spent += 22_000
        card.updated_at = datetime.utcnow()
        await store.upsert("task_cards", card)
        await self._move_children(card.id, KanbanColumn.EM_TESTES)

        req_llm = RequirementsResult(
            objective=requirements.objective,
            context=requirements.context,
            functional=requirements.functional,
            non_functional=requirements.non_functional,
            business_rules=requirements.business_rules,
            constraints=requirements.constraints,
            acceptance_criteria=requirements.acceptance_criteria,
        )
        test_out = await runners.run_tester(card, req_llm, implementation)
        failures = [
            TestFailure(
                name=str(f.get("name", "test")),
                message=str(f.get("message", "")),
                severity=str(f.get("severity", "medium")),
            )
            for f in test_out.failures
        ]
        test = TestResult(
            card_id=card.id,
            suite=test_out.suite,
            executed=test_out.executed,
            passed=test_out.passed,
            failed=test_out.failed,
            skipped=test_out.skipped,
            coverage=test_out.coverage,
            failures=failures,
            evidences=[test_out.evidence_notes],
            recommendation=test_out.recommendation,
        )
        for agent in mission.agents:
            if agent.role in {"testador", "tester"}:
                agent.status = "completed"
                agent.output_summary = test.recommendation[:280]
        mission.progress = 0.88
        mission.updated_at = datetime.utcnow()
        await store.upsert("test_results", test)
        await store.upsert("swarm_missions", mission)
        await store.upsert("task_cards", card)
        await self._audit(card, "run_tests", KanbanColumn.EM_TESTES.value, {
            "passed": test.passed,
            "failed": test.failed,
        })

        await a2a.publish_a2a(
            card,
            "testador",
            (
                f"Testes: {test.passed}/{test.executed} passaram"
                f"{f', {test.failed} falharam' if test.failed else ''}. "
                f"{test.recommendation[:120]}{'…' if len(test.recommendation) > 120 else ''}"
            ),
            to_agent="documentacao" if test.failed == 0 else "desenvolvedor",
            message_type="result" if test.failed == 0 else "handoff",
            pipeline_step="test",
        )

        if test.failed > 0:
            round_n = int(state.get("correction_round") or 0)
            feedback = f"Tests failed ({test.failed}): {test.recommendation}"
            if test.failures:
                feedback += "\nFailures: " + "; ".join(
                    f"{f.name}: {f.message}" for f in test.failures
                )
            # If a live preview is already deployed and most tests pass, ship with residual risk.
            mostly_ok = test.executed > 0 and test.failed < max(1, test.executed // 2)
            if card.preview_url and mostly_ok:
                await self._audit(card, "tests_warning_continue", KanbanColumn.EM_TESTES.value, {
                    "failed": test.failed,
                    "preview_url": card.preview_url,
                })
                return {
                    "card": card.model_dump(mode="json"),
                    "mission": mission.model_dump(mode="json"),
                    "tests": test.model_dump(mode="json"),
                    "error": "",
                }
            if round_n < 1:
                return {
                    "card": card.model_dump(mode="json"),
                    "mission": mission.model_dump(mode="json"),
                    "tests": test.model_dump(mode="json"),
                    "feedback": feedback,
                    "correction_round": round_n,
                    "error": feedback,
                }
            return {
                "card": card.model_dump(mode="json"),
                "error": feedback,
            }
        return {
            "card": card.model_dump(mode="json"),
            "mission": mission.model_dump(mode="json"),
            "tests": test.model_dump(mode="json"),
            "error": "",
        }

    async def _node_document(self, state: SwarmState) -> SwarmState:
        if state.get("error"):
            return state
        store = get_store()
        card = TaskCard.model_validate(state["card"])
        requirements = RequirementSpecification.model_validate(state["requirements"])
        from app.agents.schemas import ImplementationResult
        from app.models.enums import ReviewVerdict as RV

        implementation = ImplementationResult.model_validate(state["implementation"])
        review_raw = state.get("review") or {}
        tests_raw = state.get("tests") or {}
        review = ReviewDecision.model_validate(review_raw) if review_raw else ReviewDecision(
            card_id=card.id,
            decision=RV.APROVADO,
            rationale="Sem revisão detalhada",
        )
        test = TestResult.model_validate(tests_raw) if tests_raw else TestResult(
            card_id=card.id,
            suite="acceptance",
            executed=0,
            passed=0,
            recommendation="",
        )

        req_llm = RequirementsResult(
            objective=requirements.objective,
            context=requirements.context,
            functional=requirements.functional,
            non_functional=requirements.non_functional,
            business_rules=requirements.business_rules,
            constraints=requirements.constraints,
            acceptance_criteria=requirements.acceptance_criteria,
        )
        from app.agents.schemas import ReviewResult as RR
        from app.agents.schemas import TestPlanResult as TR

        docs = await runners.run_documentation(
            card,
            req_llm,
            implementation,
            RR(
                decision=review.decision,
                issues=review.issues,
                severity=review.severity,
                requirements_met=review.requirements_met,
                required_fixes=review.required_fixes,
                rationale=review.rationale,
                confidence=review.confidence,
            ),
            TR(
                suite=test.suite,
                scenarios=[],
                executed=test.executed,
                passed=test.passed,
                failed=test.failed,
                skipped=test.skipped,
                coverage=test.coverage,
                failures=[f.model_dump() for f in test.failures],
                recommendation=test.recommendation,
                evidence_notes="; ".join(test.evidences),
            ),
        )
        card.budget_spent += 12_000
        await self._artifact(
            card,
            "docs",
            "delivery-notes.md",
            docs.summary,
            "documentacao",
            f"artifacts://{card.id}/delivery-notes.md",
            docs.markdown,
        )
        await a2a.publish_a2a(
            card,
            "documentacao",
            f"Notas de entrega geradas: {docs.summary[:200]}{'…' if len(docs.summary) > 200 else ''}",
            message_type="result",
            pipeline_step="document",
        )
        await store.upsert("task_cards", card)
        return {"card": card.model_dump(mode="json"), "documentation": docs.model_dump(mode="json")}

    async def _node_prepare_delivery(self, state: SwarmState) -> SwarmState:
        if state.get("error"):
            return state
        store = get_store()
        card = TaskCard.model_validate(state["card"])
        mission = SwarmMission.model_validate(state["mission"])
        card.column = KanbanColumn.PRONTO_ENTREGA
        card.updated_at = datetime.utcnow()
        mission.progress = 1.0
        mission.status = "awaiting_delivery_approval"
        mission.updated_at = datetime.utcnow()
        await self._move_children(card.id, KanbanColumn.CONCLUIDO, stagger=True)
        approval = HumanApproval(
            card_id=card.id,
            type=ApprovalType.ENTREGA,
            requester="release_manager",
            decision=ApprovalDecision.PENDENTE,
            comment="Entrega gerada por agentes LLM. Aguardando autorização final.",
        )
        await store.upsert("approvals", approval)
        await store.upsert("swarm_missions", mission)
        await store.upsert("task_cards", card)
        await self._audit(card, "prepare_delivery", KanbanColumn.PRONTO_ENTREGA.value)
        await a2a.publish_a2a(
            card,
            "coordenador",
            (
                "Entrega pronta — mini-app em preview e documentação anexada. "
                "Aguardando aprovação final de entrega."
            ),
            message_type="status",
            pipeline_step="prepare_delivery",
        )
        from app.services import project_manager

        try:
            await project_manager.announce(
                card,
                (
                    f"✅ «{card.title}» está pronto para entrega. "
                    "Revise o preview no dock e aprove para concluir."
                ),
                message_type="question",
                pipeline_step="pm_delivery",
            )
        except Exception:
            logger.exception("Nova delivery announce failed")
        return {"card": card.model_dump(mode="json"), "mission": mission.model_dump(mode="json")}

    async def _block_with_ticket(self, card: TaskCard, reason: str) -> TaskCard:
        store = get_store()
        card.column = KanbanColumn.BLOQUEADO
        card.block_reason = reason[:500]
        card.updated_at = datetime.utcnow()
        await self._move_children(card.id, KanbanColumn.BLOQUEADO, stagger=False)
        ticket = SupportTicket(
            category=TicketCategory.BLOQUEIO,
            title=f"Bloqueio: {card.title}",
            description=reason,
            origin="ruflo_swarm",
            severity="high",
            impact="Execução do enxame interrompida",
            card_id=card.id,
            status=TicketStatus.ABERTO,
        )
        missions = await store.list("swarm_missions", {"card_id": card.id})
        if missions:
            mission = SwarmMission.model_validate(missions[-1])
            mission.status = "blocked"
            mission.errors.append(reason[:500])
            mission.updated_at = datetime.utcnow()
            await store.upsert("swarm_missions", mission)
        await store.upsert("tickets", ticket)
        await store.upsert("task_cards", card)
        await self._audit(card, "open_ticket_and_block", KanbanColumn.BLOQUEADO.value, {
            "ticket_id": ticket.id,
        })
        await a2a.publish_a2a(
            card,
            "coordenador",
            f"Enxame bloqueado: {reason[:200]}{'…' if len(reason) > 200 else ''}",
            to_agent="chamados",
            message_type="status",
            pipeline_step="blocked",
        )
        return card

    async def _artifact(
        self,
        card: TaskCard,
        type_: str,
        name: str,
        description: str,
        author: str,
        location: str,
        body: str = "",
    ) -> None:
        store = get_store()
        artifact = WorkArtifact(
            card_id=card.id,
            type=type_,
            name=name,
            description=description,
            author=author,
            location=location,
            hash=f"sha256:{card.id}:{name}",
            evidences=[body[:2000]] if body else [location],
        )
        await store.insert("artifacts", artifact)

    async def _audit(self, card: TaskCard, action: str, state: str, result: dict | None = None) -> None:
        store = get_store()
        event = AuditEvent(
            card_id=card.id,
            actor="ruflo_swarm",
            action=action,
            next_state=state,
            result=result or {},
        )
        await store.insert("audit_events", event)


ruflo = RufloSwarmManager()
