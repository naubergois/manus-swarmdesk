import type {
  AgentCatalogItem,
  CardDetail,
  ChatMessage,
  ChatResponse,
  DashboardMetrics,
  HumanApproval,
  KanbanColumn,
  Project,
  SupportTicket,
  SwarmMission,
  TaskCard,
} from "../types";

const BASE = import.meta.env.VITE_API_URL ?? "/api";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    ...init,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? JSON.stringify(body);
    } catch {
      /* ignore */
    }
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return res.json() as Promise<T>;
}

export const api = {
  health: () => request<{ status: string }>("/health"),
  projects: {
    list: () => request<Project[]>("/projects"),
    create: (name: string, description = "") =>
      request<Project>("/projects", {
        method: "POST",
        body: JSON.stringify({ name, description }),
      }),
    get: (id: string) =>
      request<{ project: Project; boards: { id: string; name: string; project_id: string }[] }>(
        `/projects/${id}`,
      ),
  },
  cards: {
    list: (boardId?: string) =>
      request<TaskCard[]>(boardId ? `/cards?board_id=${boardId}` : "/cards"),
    get: (id: string) => request<CardDetail>(`/cards/${id}`),
    create: (payload: {
      title: string;
      description: string;
      project_id?: string;
      priority?: string;
    }) =>
      request<TaskCard>("/cards", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    transition: (id: string, target: KanbanColumn, reason = "drag") =>
      request<TaskCard>(`/cards/${id}/transition`, {
        method: "POST",
        body: JSON.stringify({ target, reason, actor: "human" }),
      }),
    approve: (id: string, comment = "") =>
      request<HumanApproval>(`/cards/${id}/approve`, {
        method: "POST",
        body: JSON.stringify({ decision: "aprovado", comment, approver: "product_owner" }),
      }),
    reject: (id: string, comment = "") =>
      request<HumanApproval>(`/cards/${id}/reject`, {
        method: "POST",
        body: JSON.stringify({ decision: "reprovado", comment, approver: "product_owner" }),
      }),
    reset: (reseedDemo = true) =>
      request<{ ok: boolean; runtimes_stopped: number; reseeded: boolean }>(
        `/cards/reset?reseed_demo=${reseedDemo}`,
        { method: "POST" },
      ),
  },
  chat: {
    messages: () => request<ChatMessage[]>("/chat/messages"),
    send: (message: string, project_id?: string) =>
      request<ChatResponse>("/chat/messages", {
        method: "POST",
        body: JSON.stringify({ message, project_id }),
      }),
  },
  approvals: {
    list: () => request<HumanApproval[]>("/approvals"),
    decide: (id: string, decision: "aprovado" | "reprovado", comment = "") =>
      request<HumanApproval>(`/approvals/${id}/decide`, {
        method: "POST",
        body: JSON.stringify({ decision, comment, approver: "product_owner" }),
      }),
  },
  agents: {
    list: () => request<AgentCatalogItem[]>("/agents"),
    patch: (id: string, payload: { active?: boolean; preferred_model?: string }) =>
      request<AgentCatalogItem>(`/agents/${id}`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      }),
  },
  swarm: {
    missions: () => request<SwarmMission[]>("/swarm/missions"),
    get: (id: string) => request<SwarmMission>(`/swarm/missions/${id}`),
  },
  tickets: {
    list: () => request<SupportTicket[]>("/tickets"),
    create: (payload: {
      category: string;
      title: string;
      description: string;
      card_id?: string;
      severity?: string;
    }) =>
      request<SupportTicket>("/tickets", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
  },
  dashboard: {
    metrics: () => request<DashboardMetrics>("/dashboard/metrics"),
  },
  runtime: {
    get: (cardId: string) =>
      request<{ card_id: string; preview_url?: string; status?: string; port?: number }>(
        `/runtime/${cardId}`,
      ),
  },
};
