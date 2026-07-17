"""Real agent runners — each call invokes the configured LLM."""

from __future__ import annotations

from app.agents.schemas import (
    DocumentationResult,
    ImplementationResult,
    PlanResult,
    RequirementsResult,
    ReviewResult,
    SupervisorReply,
    SwarmDesign,
    TestPlanResult,
    TriageResult,
)
from app.llm import structured_invoke
from app.models.contracts import TaskCard


async def run_triage(card: TaskCard) -> TriageResult:
    return await structured_invoke(
        TriageResult,
        system=(
            "You are the Triage agent for Manus SwarmDesk. "
            "Classify software demands for a Kanban multi-agent factory. "
            "Be precise; prefer Portuguese for summary/title if the input is Portuguese."
        ),
        human=(
            f"Title: {card.title}\n"
            f"Description:\n{card.description}\n\n"
            "Return structured triage."
        ),
    )


async def run_requirements(card: TaskCard, triage: TriageResult | None = None) -> RequirementsResult:
    extra = ""
    if triage:
        extra = f"\nTriage summary: {triage.summary}\nType: {triage.type}\nPriority: {triage.priority}\n"
    return await structured_invoke(
        RequirementsResult,
        system=(
            "You are the Requirements Analyst for Manus SwarmDesk. "
            "Produce complete functional/non-functional requirements and testable acceptance criteria. "
            "Write in the same language as the demand."
        ),
        human=f"Demand:\n{card.title}\n{card.description}\n{extra}",
    )


async def run_planner(card: TaskCard, requirements: RequirementsResult) -> PlanResult:
    return await structured_invoke(
        PlanResult,
        system=(
            "You are the Planner agent. Decompose the demand into executable tasks "
            "with parallel groups and required agent roles for a hierarchical swarm."
        ),
        human=(
            f"Title: {card.title}\nDescription: {card.description}\n"
            f"Objective: {requirements.objective}\n"
            f"Acceptance: {requirements.acceptance_criteria}\n"
            f"Functional: {requirements.functional}\n"
            "Produce an execution plan."
        ),
    )


async def run_swarm_design(card: TaskCard, plan: PlanResult) -> SwarmDesign:
    return await structured_invoke(
        SwarmDesign,
        system=(
            "You are the Swarm Coordinator (Ruflo-style hierarchical topology). "
            "Select only needed specialist agents and assign concrete subtasks."
        ),
        human=(
            f"Card: {card.title}\nPlan strategy: {plan.strategy}\n"
            f"Tasks: {[t.model_dump() for t in plan.tasks]}\n"
            f"Required agents hint: {plan.required_agents}\n"
            "Design the swarm mission."
        ),
    )


async def run_developer(card: TaskCard, requirements: RequirementsResult, plan: PlanResult) -> ImplementationResult:
    return await structured_invoke(
        ImplementationResult,
        system=(
            "You are Forge, the Developer robot in Manus SwarmDesk. "
            "Build a COMPLETE small software product that can run immediately. "
            "Prefer a polished single-page HTML+CSS+JS app (app_kind=static, entrypoint=index.html) "
            "unless the demand clearly needs a Python API (app_kind=fastapi, entrypoint=main.py). "
            "Return FULL file contents in app_files — not stubs, not placeholders. "
            "The UI must be modern, usable, and self-contained. "
            "Write all user-facing text in English."
        ),
        human=(
            f"Title: {card.title}\nDescription: {card.description}\n"
            f"Objective: {requirements.objective}\n"
            f"Functional: {requirements.functional}\n"
            f"Acceptance: {requirements.acceptance_criteria}\n"
            f"Plan tasks: {[t.title for t in plan.tasks]}\n"
            "Produce a complete runnable mini-app with full source in app_files."
        ),
    )


async def run_reviewer(
    card: TaskCard,
    requirements: RequirementsResult,
    implementation: ImplementationResult,
) -> ReviewResult:
    return await structured_invoke(
        ReviewResult,
        system=(
            "You are an independent Code Reviewer. You did NOT author the implementation. "
            "Evaluate adherence to requirements and quality. Be strict but fair."
        ),
        human=(
            f"Requirements acceptance: {requirements.acceptance_criteria}\n"
            f"Functional: {requirements.functional}\n"
            f"Implementation summary: {implementation.summary}\n"
            f"Files: {implementation.files_changed}\n"
            f"Design notes: {implementation.design_notes}\n"
            f"Artifact:\n{implementation.artifact_markdown[:6000]}\n"
            "Return a review decision."
        ),
    )


async def run_tester(
    card: TaskCard,
    requirements: RequirementsResult,
    implementation: ImplementationResult,
) -> TestPlanResult:
    return await structured_invoke(
        TestPlanResult,
        system=(
            "You are the Test agent. Design and simulate an acceptance test suite against the "
            "implementation proposal and acceptance criteria. Report realistic pass/fail counts."
        ),
        human=(
            f"Acceptance criteria: {requirements.acceptance_criteria}\n"
            f"Implementation: {implementation.summary}\n"
            f"API contracts: {implementation.api_contracts}\n"
            f"Artifact excerpt:\n{implementation.artifact_markdown[:4000]}\n"
            "Produce structured test results."
        ),
    )


async def run_documentation(
    card: TaskCard,
    requirements: RequirementsResult,
    implementation: ImplementationResult,
    review: ReviewResult,
    tests: TestPlanResult,
) -> DocumentationResult:
    return await structured_invoke(
        DocumentationResult,
        system=(
            "You are the Documentation agent. Produce delivery documentation consolidating "
            "requirements, implementation, review, and tests."
        ),
        human=(
            f"Title: {card.title}\nObjective: {requirements.objective}\n"
            f"Implementation: {implementation.summary}\n"
            f"Review: {review.decision} — {review.rationale}\n"
            f"Tests: {tests.passed}/{tests.executed} passed, coverage {tests.coverage}\n"
            "Write the delivery notes in markdown."
        ),
    )


async def run_supervisor_reply(user_message: str, card_title: str, column: str, card_type: str, priority: str) -> SupervisorReply:
    return await structured_invoke(
        SupervisorReply,
        system=(
            "You are the Supervisor of Manus SwarmDesk. Explain clearly what happened "
            "and the next human step. Use the user's language. "
            "Never claim the app was built or work cards were created unless the column "
            "is beyond awaiting approval — the swarm only runs after human scope approval."
        ),
        human=(
            f"User said: {user_message}\n"
            f"Created card: {card_title}\nColumn: {column}\nType: {card_type}\nPriority: {priority}\n"
            "Write a short assistant reply and a polished suggested_title. "
            "If column is aguardando_aprovacao, tell the user to approve scope before any app build."
        ),
    )
