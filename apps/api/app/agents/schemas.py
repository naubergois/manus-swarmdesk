"""LLM response schemas (subset used for structured generation)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.models.enums import CardType, Priority, ReviewVerdict


class TriageResult(BaseModel):
    title: str = Field(description="Concise task title")
    type: CardType
    priority: Priority
    tags: list[str] = Field(default_factory=list)
    risk: str = Field(description="low|medium|high")
    missing_info: list[str] = Field(default_factory=list)
    summary: str


class RequirementsResult(BaseModel):
    objective: str
    context: str
    functional: list[str]
    non_functional: list[str]
    business_rules: list[str]
    constraints: list[str]
    acceptance_criteria: list[str]
    assumptions: list[str] = Field(default_factory=list)
    out_of_scope: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)


class PlanTaskOut(BaseModel):
    title: str
    agent_role: str = Field(
        description="One of: requisitos, arquiteto, desenvolvedor, testador, revisor, documentacao, devops"
    )
    parallel_group: int = Field(ge=0, description="Tasks with same group can run in parallel")
    depends_on: list[str] = Field(default_factory=list)


class PlanResult(BaseModel):
    objective: str
    strategy: str
    tasks: list[PlanTaskOut]
    required_agents: list[str]
    tools: list[str]
    risks: list[str]
    estimated_effort_hours: float
    completion_criteria: list[str]


class SwarmAgentSpec(BaseModel):
    agent_id: str
    role: str
    subtask: str
    tools: list[str] = Field(default_factory=list)


class SwarmDesign(BaseModel):
    objective: str
    topology: str = "hierarchical"
    agents: list[SwarmAgentSpec]
    allowed_tools: list[str]
    expected_result: str
    consensus_policy: str = "coordinator_merge"
    escalation_policy: str = "open_ticket_or_human"


class ImplementationResult(BaseModel):
    summary: str
    files_changed: list[str]
    design_notes: str
    api_contracts: list[str] = Field(default_factory=list)
    open_risks: list[str] = Field(default_factory=list)
    artifact_markdown: str = Field(description="Markdown describing the implementation proposal")


class ReviewResult(BaseModel):
    decision: ReviewVerdict
    issues: list[str] = Field(default_factory=list)
    severity: str = "low"
    requirements_met: list[str] = Field(default_factory=list)
    required_fixes: list[str] = Field(default_factory=list)
    rationale: str
    confidence: float = Field(ge=0, le=1)


class TestPlanResult(BaseModel):
    suite: str
    scenarios: list[str]
    executed: int
    passed: int
    failed: int
    skipped: int = 0
    coverage: float
    failures: list[dict] = Field(default_factory=list, description="[{name, message, severity}]")
    recommendation: str
    evidence_notes: str


class DocumentationResult(BaseModel):
    title: str
    summary: str
    markdown: str
    residual_risks: list[str] = Field(default_factory=list)


class SupervisorReply(BaseModel):
    reply: str
    suggested_title: str
