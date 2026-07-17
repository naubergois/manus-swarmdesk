from datetime import datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from app.models.enums import (
    ApprovalDecision,
    ApprovalType,
    AutonomyLevel,
    CardType,
    KanbanColumn,
    Priority,
    ReviewVerdict,
    TicketCategory,
    TicketStatus,
)


def new_id(prefix: str = "") -> str:
    value = uuid4().hex[:12]
    return f"{prefix}{value}" if prefix else value


class TaskCard(BaseModel):
    id: str = Field(default_factory=lambda: new_id("card_"))
    title: str
    description: str
    type: CardType = CardType.NOVA_FUNCIONALIDADE
    project_id: str
    board_id: str
    priority: Priority = Priority.MEDIA
    requester: str = "usuario"
    human_owner: str = "product_owner"
    column: KanbanColumn = KanbanColumn.ENTRADA
    kind: str = "epic"  # epic | work
    parent_id: str | None = None
    plan_task_id: str | None = None
    tags: list[str] = Field(default_factory=list)
    due_date: datetime | None = None
    dependencies: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    autonomy_level: AutonomyLevel = AutonomyLevel.IMPLEMENTACAO
    budget_tokens: int = 250_000
    budget_spent: int = 0
    agents: list[str] = Field(default_factory=list)
    subtasks: list[str] = Field(default_factory=list)
    block_reason: str | None = None
    preview_url: str | None = None
    runtime_status: str | None = None
    runtime_port: int | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class RequirementSpecification(BaseModel):
    id: str = Field(default_factory=lambda: new_id("req_"))
    card_id: str
    objective: str
    context: str
    functional: list[str] = Field(default_factory=list)
    non_functional: list[str] = Field(default_factory=list)
    business_rules: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    out_of_scope: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class PlanTask(BaseModel):
    id: str = Field(default_factory=lambda: new_id("pt_"))
    title: str
    agent_role: str
    parallel_group: int = 0
    depends_on: list[str] = Field(default_factory=list)
    status: str = "pending"


class ExecutionPlan(BaseModel):
    id: str = Field(default_factory=lambda: new_id("plan_"))
    card_id: str
    objective: str
    strategy: str
    tasks: list[PlanTask] = Field(default_factory=list)
    required_agents: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    estimated_effort_hours: float = 8.0
    completion_criteria: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class AgentAssignment(BaseModel):
    agent_id: str
    role: str
    subtask: str
    inputs: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    status: str = "assigned"
    output_summary: str | None = None


class SwarmMission(BaseModel):
    id: str = Field(default_factory=lambda: new_id("mission_"))
    card_id: str
    objective: str
    topology: str = "hierarchical"
    agents: list[AgentAssignment] = Field(default_factory=list)
    allowed_tools: list[str] = Field(default_factory=list)
    limits: dict[str, Any] = Field(default_factory=dict)
    consensus_policy: str = "coordinator_merge"
    escalation_policy: str = "open_ticket_or_human"
    expected_result: str = ""
    progress: float = 0.0
    status: str = "pending"
    errors: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class WorkArtifact(BaseModel):
    id: str = Field(default_factory=lambda: new_id("art_"))
    card_id: str
    type: str
    name: str
    description: str
    author: str
    version: str = "1.0.0"
    location: str
    hash: str = ""
    evidences: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class TestFailure(BaseModel):
    name: str
    message: str
    severity: str = "medium"


class TestResult(BaseModel):
    id: str = Field(default_factory=lambda: new_id("test_"))
    card_id: str
    suite: str
    environment: str = "isolated"
    executed: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    coverage: float = 0.0
    failures: list[TestFailure] = Field(default_factory=list)
    evidences: list[str] = Field(default_factory=list)
    recommendation: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ReviewDecision(BaseModel):
    id: str = Field(default_factory=lambda: new_id("rev_"))
    card_id: str
    decision: ReviewVerdict
    issues: list[str] = Field(default_factory=list)
    severity: str = "low"
    requirements_met: list[str] = Field(default_factory=list)
    required_fixes: list[str] = Field(default_factory=list)
    rationale: str = ""
    confidence: float = 0.8
    reviewer: str = "revisor"
    created_at: datetime = Field(default_factory=datetime.utcnow)


class SupportTicket(BaseModel):
    id: str = Field(default_factory=lambda: new_id("tkt_"))
    category: TicketCategory
    title: str
    description: str
    origin: str = "agent"
    severity: str = "medium"
    impact: str = ""
    evidences: list[str] = Field(default_factory=list)
    system: str = "swarmdesk"
    card_id: str | None = None
    owner: str = "ops"
    due_date: datetime | None = None
    status: TicketStatus = TicketStatus.ABERTO
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class HumanApproval(BaseModel):
    id: str = Field(default_factory=lambda: new_id("apr_"))
    card_id: str
    type: ApprovalType
    requester: str = "supervisor"
    approver: str | None = None
    decision: ApprovalDecision = ApprovalDecision.PENDENTE
    comment: str = ""
    limitations: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    decided_at: datetime | None = None


class AuditEvent(BaseModel):
    id: str = Field(default_factory=lambda: new_id("aud_"))
    execution_id: str | None = None
    card_id: str | None = None
    actor: str
    action: str
    previous_state: str | None = None
    next_state: str | None = None
    input_data: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] = Field(default_factory=dict)
    correlation_id: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class AgentCatalogItem(BaseModel):
    id: str
    name: str
    role: str
    description: str
    version: str = "1.0.0"
    preferred_model: str = "gpt-4.1-mini"
    tools: list[str] = Field(default_factory=list)
    task_types: list[CardType] = Field(default_factory=list)
    autonomy_level: AutonomyLevel = AutonomyLevel.IMPLEMENTACAO
    active: bool = True
    success_rate: float = 0.9
    avg_cost_tokens: int = 12_000
    system_prompt: str = ""


class Project(BaseModel):
    id: str = Field(default_factory=lambda: new_id("proj_"))
    name: str
    description: str = ""
    default_autonomy: AutonomyLevel = AutonomyLevel.IMPLEMENTACAO
    git_provider: str = "github"
    ticket_provider: str = "internal"
    created_at: datetime = Field(default_factory=datetime.utcnow)


class KanbanBoard(BaseModel):
    id: str = Field(default_factory=lambda: new_id("board_"))
    project_id: str
    name: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ChatMessage(BaseModel):
    id: str = Field(default_factory=lambda: new_id("msg_"))
    role: str
    content: str
    card_id: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ChatRequest(BaseModel):
    message: str
    project_id: str | None = None


class ChatResponse(BaseModel):
    reply: str
    card: TaskCard | None = None
    messages: list[ChatMessage] = Field(default_factory=list)


class TransitionRequest(BaseModel):
    target: KanbanColumn
    reason: str = "manual"
    actor: str = "human"


class ApprovalAction(BaseModel):
    decision: ApprovalDecision
    comment: str = ""
    approver: str = "product_owner"


class CreateCardRequest(BaseModel):
    title: str
    description: str
    project_id: str | None = None
    type: CardType = CardType.NOVA_FUNCIONALIDADE
    priority: Priority = Priority.MEDIA
    autonomy_level: AutonomyLevel = AutonomyLevel.IMPLEMENTACAO


class CreateProjectRequest(BaseModel):
    name: str
    description: str = ""


class CreateTicketRequest(BaseModel):
    category: TicketCategory
    title: str
    description: str
    card_id: str | None = None
    severity: str = "medium"


class DashboardMetrics(BaseModel):
    in_execution: int
    blocked: int
    recent_deliveries: int
    open_incidents: int
    success_rate: float
    avg_cycle_hours: float
    total_tokens: int
    total_cost_usd: float
    agent_performance: list[dict[str, Any]] = Field(default_factory=list)


class CardDetail(BaseModel):
    card: TaskCard
    requirements: RequirementSpecification | None = None
    plan: ExecutionPlan | None = None
    mission: SwarmMission | None = None
    artifacts: list[WorkArtifact] = Field(default_factory=list)
    tests: list[TestResult] = Field(default_factory=list)
    reviews: list[ReviewDecision] = Field(default_factory=list)
    tickets: list[SupportTicket] = Field(default_factory=list)
    approvals: list[HumanApproval] = Field(default_factory=list)
    timeline: list[AuditEvent] = Field(default_factory=list)
