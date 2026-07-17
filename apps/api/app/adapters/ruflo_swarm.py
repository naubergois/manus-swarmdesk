"""Hierarchical swarm execution (Ruflo-style topology) powered by real LLM agents.

Ruflo MCP/CLI is an external harness for Claude Code; this adapter implements the
same control contract inside SwarmDesk using LangChain specialists coordinated
hierarchically by a coordinator design step.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, TypedDict

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
        return mission

    async def execute(self, card: TaskCard) -> TaskCard:
        store = get_store()
        reqs = await store.list("requirements", {"card_id": card.id})
        plans = await store.list("execution_plans", {"card_id": card.id})
        missions = await store.list("swarm_missions", {"card_id": card.id})
        if not reqs or not plans:
            raise RuntimeError("Requirements/plan required before swarm execution")
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

        implementation = await runners.run_developer(card, req_llm, plan)
        card.budget_spent += 48_000
        for agent in mission.agents:
            if agent.role in {"desenvolvedor", "developer", "backend", "frontend"}:
                agent.status = "completed"
                agent.output_summary = implementation.summary[:280]
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
            f"artifacts://{card.id}/implementation.md",
            implementation.artifact_markdown,
        )
        await self._audit(card, "execute_subtasks", KanbanColumn.EM_EXECUCAO.value, {
            "files": implementation.files_changed,
        })
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

        if test.failed > 0:
            round_n = int(state.get("correction_round") or 0)
            feedback = f"Testes falharam ({test.failed}): {test.recommendation}"
            if test.failures:
                feedback += "\nFalhas: " + "; ".join(
                    f"{f.name}: {f.message}" for f in test.failures
                )
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
        return {"card": card.model_dump(mode="json"), "mission": mission.model_dump(mode="json")}

    async def _block_with_ticket(self, card: TaskCard, reason: str) -> TaskCard:
        store = get_store()
        card.column = KanbanColumn.BLOQUEADO
        card.block_reason = reason[:500]
        card.updated_at = datetime.utcnow()
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
