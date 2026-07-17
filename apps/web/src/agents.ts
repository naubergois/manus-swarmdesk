export type AgentVisual = {
  id: string;
  name: string;
  role: string;
  emoji: string;
  color: string;
  blurb: string;
};

const ROLE_META: Record<string, { label: string; emoji: string; color: string }> = {
  supervisor: { label: "Supervisor", emoji: "🤖", color: "#2563eb" },
  triagem: { label: "Triage", emoji: "🛰️", color: "#0891b2" },
  requisitos: { label: "Requirements", emoji: "📋", color: "#7c3aed" },
  planejador: { label: "Planner", emoji: "🗺️", color: "#0ea5e9" },
  arquiteto: { label: "Architect", emoji: "🏗️", color: "#0f766e" },
  coordenador: { label: "Swarm Lead", emoji: "🧠", color: "#4f46e5" },
  desenvolvedor: { label: "Developer", emoji: "🛠️", color: "#ea580c" },
  testador: { label: "Tester", emoji: "🧪", color: "#059669" },
  revisor: { label: "Reviewer", emoji: "🔎", color: "#db2777" },
  documentacao: { label: "Docs", emoji: "✍️", color: "#64748b" },
  chamados: { label: "Tickets", emoji: "🚨", color: "#e11d48" },
  frontend: { label: "Frontend", emoji: "✨", color: "#8b5cf6" },
  backend: { label: "Backend", emoji: "⚙️", color: "#0284c7" },
  fullstack: { label: "Full-stack", emoji: "🧩", color: "#d97706" },
  mobile: { label: "Mobile", emoji: "📱", color: "#06b6d4" },
  qa: { label: "QA", emoji: "🧪", color: "#10b981" },
  security: { label: "Security", emoji: "🛡️", color: "#dc2626" },
  devops: { label: "DevOps", emoji: "🚀", color: "#475569" },
  data: { label: "Data", emoji: "📊", color: "#0d9488" },
  ml: { label: "ML", emoji: "🧬", color: "#7c3aed" },
  design: { label: "Design", emoji: "🎨", color: "#ec4899" },
  docs: { label: "Docs", emoji: "📚", color: "#64748b" },
  support: { label: "Support", emoji: "💬", color: "#f59e0b" },
  product: { label: "Product", emoji: "🎯", color: "#2563eb" },
  research: { label: "Research", emoji: "🔬", color: "#6366f1" },
  performance: { label: "Performance", emoji: "⚡", color: "#eab308" },
  integration: { label: "Integration", emoji: "🔗", color: "#14b8a6" },
};

const PALETTE = [
  "#2563eb",
  "#0891b2",
  "#7c3aed",
  "#0f766e",
  "#4f46e5",
  "#ea580c",
  "#db2777",
  "#059669",
  "#e11d48",
  "#d97706",
  "#0284c7",
  "#8b5cf6",
];

export const AGENT_ROBOTS: AgentVisual[] = [
  {
    id: "supervisor",
    name: "Nova",
    role: "Supervisor",
    emoji: "🤖",
    color: "#2563eb",
    blurb: "Owns the delivery flow end-to-end",
  },
  {
    id: "triagem",
    name: "Scout",
    role: "Triage",
    emoji: "🛰️",
    color: "#0891b2",
    blurb: "Classifies demand and missing info",
  },
  {
    id: "requisitos",
    name: "Spec",
    role: "Requirements",
    emoji: "📋",
    color: "#7c3aed",
    blurb: "Writes acceptance criteria",
  },
  {
    id: "planejador",
    name: "Map",
    role: "Planner",
    emoji: "🗺️",
    color: "#0ea5e9",
    blurb: "Breaks builds into swarm tasks",
  },
  {
    id: "arquiteto",
    name: "Atlas",
    role: "Architect",
    emoji: "🏗️",
    color: "#0f766e",
    blurb: "Shapes components and interfaces",
  },
  {
    id: "coordenador",
    name: "Hive",
    role: "Swarm Lead",
    emoji: "🧠",
    color: "#4f46e5",
    blurb: "Forms and directs the agent swarm",
  },
  {
    id: "desenvolvedor",
    name: "Forge",
    role: "Developer",
    emoji: "🛠️",
    color: "#ea580c",
    blurb: "Builds and deploys the mini-app",
  },
  {
    id: "revisor",
    name: "Lens",
    role: "Reviewer",
    emoji: "🔎",
    color: "#db2777",
    blurb: "Independent quality review",
  },
  {
    id: "testador",
    name: "Pulse",
    role: "Tester",
    emoji: "🧪",
    color: "#059669",
    blurb: "Runs acceptance checks",
  },
  {
    id: "documentacao",
    name: "Quill",
    role: "Docs",
    emoji: "✍️",
    color: "#64748b",
    blurb: "Publishes delivery notes",
  },
  {
    id: "chamados",
    name: "Beacon",
    role: "Tickets",
    emoji: "🚨",
    color: "#e11d48",
    blurb: "Opens blockers and incidents",
  },
];

function hashHue(value: string): number {
  let hash = 0;
  for (let i = 0; i < value.length; i += 1) {
    hash = (hash * 31 + value.charCodeAt(i)) >>> 0;
  }
  return hash;
}

export function roleLabel(role: string): string {
  return ROLE_META[role]?.label ?? role.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export function roleMeta(role: string): { label: string; emoji: string; color: string } {
  if (ROLE_META[role]) return ROLE_META[role];
  const color = PALETTE[hashHue(role) % PALETTE.length];
  return { label: roleLabel(role), emoji: "🤖", color };
}

export function agentVisual(id: string): AgentVisual {
  const featured = AGENT_ROBOTS.find(
    (a) => a.id === id || a.role.toLowerCase() === id.toLowerCase(),
  );
  if (featured) return featured;

  const roleKey = id.includes("_") ? id.split("_")[0] : id;
  const meta = roleMeta(roleKey);
  const color = PALETTE[hashHue(id) % PALETTE.length] ?? meta.color;
  return {
    id,
    name: id
      .split("_")
      .slice(1)
      .join(" ")
      .replace(/\b\w/g, (c) => c.toUpperCase()) || id,
    role: meta.label,
    emoji: meta.emoji,
    color,
    blurb: `${meta.label} specialist agent`,
  };
}

export const SOFTWARE_TEMPLATES = [
  {
    title: "Todo Mini App",
    description:
      "Build a complete single-page Todo app with add/complete/delete, local persistence, clean UI, and a runnable preview.",
  },
  {
    title: "Notes Pad",
    description:
      "Build a complete notes web app: create, edit, search notes, autosave in localStorage, modern UI, deploy a live preview.",
  },
  {
    title: "JSON Echo API + UI",
    description:
      "Build a tiny full-stack tool: POST /echo API and a simple UI that sends JSON and shows the response. Make it runnable.",
  },
  {
    title: "Bookmark Board",
    description:
      "Build a complete bookmark manager: save links with titles/tags, filter by tag, persist locally, ship a working preview.",
  },
  {
    title: "Pomodoro Timer",
    description:
      "Build a complete Pomodoro timer web app with start/pause/reset, session history, and a polished runnable UI.",
  },
];
