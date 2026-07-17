export type KanbanColumn =
  | "entrada"
  | "triagem"
  | "refinamento"
  | "aguardando_aprovacao"
  | "pronto_enxame"
  | "em_execucao"
  | "em_revisao"
  | "em_testes"
  | "aguardando_decisao"
  | "pronto_entrega"
  | "concluido"
  | "bloqueado"
  | "cancelado";

export type CardType =
  | "nova_funcionalidade"
  | "correcao"
  | "incidente"
  | "suporte"
  | "melhoria"
  | "refatoracao"
  | "documentacao"
  | "pesquisa"
  | "integracao"
  | "infraestrutura"
  | "dependencia"
  | "requisitos"
  | "poc"
  | "testes"
  | "revisao"
  | "implantacao";

export type Priority = "baixa" | "media" | "alta" | "critica";

export type CardKind = "epic" | "work";

export interface TaskCard {
  id: string;
  title: string;
  description: string;
  type: CardType;
  project_id: string;
  board_id: string;
  priority: Priority;
  requester: string;
  human_owner: string;
  column: KanbanColumn;
  kind?: CardKind;
  parent_id?: string | null;
  plan_task_id?: string | null;
  tags: string[];
  due_date: string | null;
  dependencies: string[];
  acceptance_criteria: string[];
  autonomy_level: number;
  budget_tokens: number;
  budget_spent: number;
  agents: string[];
  subtasks: string[];
  block_reason: string | null;
  preview_url: string | null;
  runtime_status: string | null;
  runtime_port: number | null;
  created_at: string;
  updated_at: string;
}

export interface RequirementSpecification {
  id: string;
  card_id: string;
  objective: string;
  context: string;
  functional: string[];
  non_functional: string[];
  business_rules: string[];
  constraints: string[];
  acceptance_criteria: string[];
  assumptions: string[];
  out_of_scope: string[];
  open_questions: string[];
  created_at: string;
}

export interface PlanTask {
  id: string;
  title: string;
  agent_role: string;
  parallel_group: number;
  depends_on: string[];
  status: string;
}

export interface ExecutionPlan {
  id: string;
  card_id: string;
  objective: string;
  strategy: string;
  tasks: PlanTask[];
  required_agents: string[];
  tools: string[];
  risks: string[];
  estimated_effort_hours: number;
  completion_criteria: string[];
  created_at: string;
}

export interface AgentAssignment {
  agent_id: string;
  role: string;
  subtask: string;
  inputs: string[];
  tools: string[];
  status: string;
  output_summary: string | null;
}

export interface SwarmMission {
  id: string;
  card_id: string;
  objective: string;
  topology: string;
  agents: AgentAssignment[];
  allowed_tools: string[];
  limits: Record<string, unknown>;
  consensus_policy: string;
  escalation_policy: string;
  expected_result: string;
  progress: number;
  status: string;
  errors: string[];
  created_at: string;
  updated_at: string;
}

export interface WorkArtifact {
  id: string;
  card_id: string;
  type: string;
  name: string;
  description: string;
  author: string;
  version: string;
  location: string;
  hash: string;
  evidences: string[];
  created_at: string;
}

export interface TestResult {
  id: string;
  card_id: string;
  suite: string;
  environment: string;
  executed: number;
  passed: number;
  failed: number;
  skipped: number;
  coverage: number;
  failures: { name: string; message: string; severity: string }[];
  evidences: string[];
  recommendation: string;
  created_at: string;
}

export interface ReviewDecision {
  id: string;
  card_id: string;
  decision: string;
  issues: string[];
  severity: string;
  requirements_met: string[];
  required_fixes: string[];
  rationale: string;
  confidence: number;
  reviewer: string;
  created_at: string;
}

export interface SupportTicket {
  id: string;
  category: string;
  title: string;
  description: string;
  origin: string;
  severity: string;
  impact: string;
  evidences: string[];
  system: string;
  card_id: string | null;
  owner: string;
  due_date: string | null;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface HumanApproval {
  id: string;
  card_id: string;
  type: string;
  requester: string;
  approver: string | null;
  decision: string;
  comment: string;
  limitations: string[];
  created_at: string;
  decided_at: string | null;
}

export interface AuditEvent {
  id: string;
  execution_id: string | null;
  card_id: string | null;
  actor: string;
  action: string;
  previous_state: string | null;
  next_state: string | null;
  input_data: Record<string, unknown>;
  result: Record<string, unknown>;
  correlation_id: string | null;
  created_at: string;
}

export interface AgentCatalogItem {
  id: string;
  name: string;
  role: string;
  description: string;
  version: string;
  preferred_model: string;
  tools: string[];
  task_types: CardType[];
  autonomy_level: number;
  active: boolean;
  success_rate: number;
  avg_cost_tokens: number;
  system_prompt: string;
}

export interface Project {
  id: string;
  name: string;
  description: string;
  default_autonomy: number;
  git_provider: string;
  ticket_provider: string;
  created_at: string;
}

export interface ChatMessage {
  id: string;
  role: string;
  content: string;
  card_id: string | null;
  created_at: string;
}

export interface ChatResponse {
  reply: string;
  card: TaskCard | null;
  messages: ChatMessage[];
}

export interface CardDetail {
  card: TaskCard;
  requirements: RequirementSpecification | null;
  plan: ExecutionPlan | null;
  mission: SwarmMission | null;
  artifacts: WorkArtifact[];
  tests: TestResult[];
  reviews: ReviewDecision[];
  tickets: SupportTicket[];
  approvals: HumanApproval[];
  timeline: AuditEvent[];
}

export interface DashboardMetrics {
  in_execution: number;
  blocked: number;
  recent_deliveries: number;
  open_incidents: number;
  success_rate: number;
  avg_cycle_hours: number;
  total_tokens: number;
  total_cost_usd: number;
  agent_performance: {
    id: string;
    name: string;
    success_rate: number;
    avg_cost_tokens: number;
    active: boolean;
  }[];
}

export const COLUMN_LABELS: Record<KanbanColumn, string> = {
  entrada: "Inbox",
  triagem: "AI Triage",
  refinamento: "Refining",
  aguardando_aprovacao: "Awaiting Approval",
  pronto_enxame: "Ready for Swarm",
  em_execucao: "Building",
  em_revisao: "Code Review",
  em_testes: "Testing",
  aguardando_decisao: "Needs Decision",
  pronto_entrega: "Ready to Ship",
  concluido: "Live",
  bloqueado: "Blocked",
  cancelado: "Cancelled",
};

/** Ultra-short status chip inside merged board lanes. */
export const COLUMN_SHORT_LABELS: Record<KanbanColumn, string> = {
  entrada: "Inbox",
  triagem: "Triage",
  refinamento: "Refine",
  aguardando_aprovacao: "Approve",
  pronto_enxame: "Ready",
  em_execucao: "Build",
  em_revisao: "Review",
  em_testes: "Test",
  aguardando_decisao: "Decide",
  pronto_entrega: "Ship",
  concluido: "Live",
  bloqueado: "Block",
  cancelado: "Cancel",
};

export const COLUMN_COLORS: Record<KanbanColumn, string> = {
  entrada: "#94a3b8",
  triagem: "#06b6d4",
  refinamento: "#8b5cf6",
  aguardando_aprovacao: "#f59e0b",
  pronto_enxame: "#6366f1",
  em_execucao: "#2563eb",
  em_revisao: "#ec4899",
  em_testes: "#10b981",
  aguardando_decisao: "#f97316",
  pronto_entrega: "#0ea5e9",
  concluido: "#059669",
  bloqueado: "#e11d48",
  cancelado: "#64748b",
};

export const KANBAN_COLUMNS: KanbanColumn[] = [
  "entrada",
  "triagem",
  "refinamento",
  "aguardando_aprovacao",
  "pronto_enxame",
  "em_execucao",
  "em_revisao",
  "em_testes",
  "aguardando_decisao",
  "pronto_entrega",
  "concluido",
  "bloqueado",
  "cancelado",
];

/** Simplified board lanes — similar pipeline stages are grouped for readability. */
export type BoardLaneId =
  | "inbox"
  | "approve"
  | "build"
  | "qa"
  | "live"
  | "parked";

export type BoardLane = {
  id: BoardLaneId;
  label: string;
  color: string;
  columns: KanbanColumn[];
  /** Default target when dropping a card into this lane. */
  dropTarget: KanbanColumn;
};

export const BOARD_LANES: BoardLane[] = [
  {
    id: "inbox",
    label: "Inbox",
    color: "#64748b",
    columns: ["entrada", "triagem", "refinamento"],
    dropTarget: "entrada",
  },
  {
    id: "approve",
    label: "Approve",
    color: "#f59e0b",
    columns: ["aguardando_aprovacao", "aguardando_decisao"],
    dropTarget: "aguardando_aprovacao",
  },
  {
    id: "build",
    label: "Build",
    color: "#2563eb",
    columns: ["pronto_enxame", "em_execucao"],
    dropTarget: "em_execucao",
  },
  {
    id: "qa",
    label: "QA",
    color: "#10b981",
    columns: ["em_revisao", "em_testes"],
    dropTarget: "em_revisao",
  },
  {
    id: "live",
    label: "Live",
    color: "#059669",
    columns: ["pronto_entrega", "concluido"],
    dropTarget: "concluido",
  },
  {
    id: "parked",
    label: "Parked",
    color: "#e11d48",
    columns: ["bloqueado", "cancelado"],
    dropTarget: "bloqueado",
  },
];

export function laneForColumn(column: KanbanColumn): BoardLane {
  return BOARD_LANES.find((lane) => lane.columns.includes(column)) ?? BOARD_LANES[0];
}

/** Prefer a valid transition into the lane; fall back to the lane default. */
export function resolveLaneDropTarget(
  from: KanbanColumn,
  lane: BoardLane,
  allowed: Partial<Record<KanbanColumn, KanbanColumn[]>>,
): KanbanColumn {
  const options = allowed[from] ?? [];
  const hit = lane.columns.find((col) => options.includes(col));
  return hit ?? lane.dropTarget;
}
