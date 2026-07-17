import { useEffect, useMemo, useState } from "react";
import { api } from "../api/client";
import { agentVisual, roleLabel, roleMeta } from "../agents";
import { Badge, Button } from "../components/ui";
import { useAppStore } from "../store";
import type { AgentCatalogItem } from "../types";

const PAGE_SIZE = 24;

const AUTONOMY_LABEL: Record<number, string> = {
  0: "Analysis",
  1: "Planning",
  2: "Implementation",
  3: "Integration",
  4: "Operations",
};

const CORE_IDS = new Set([
  "supervisor",
  "triagem",
  "requisitos",
  "planejador",
  "arquiteto",
  "coordenador",
  "desenvolvedor",
  "testador",
  "revisor",
  "documentacao",
  "chamados",
]);

type StatusFilter = "all" | "active" | "inactive";
type SortKey = "name" | "success" | "cost" | "role";

function RobotAvatar({ agent, size = "md" }: { agent: AgentCatalogItem; size?: "sm" | "md" }) {
  const visual = agentVisual(agent.id);
  const meta = roleMeta(agent.role);
  const dim = size === "sm" ? "h-10 w-10 text-lg" : "h-12 w-12 text-xl";
  return (
    <div
      className={`${dim} agent-float inline-flex shrink-0 items-center justify-center rounded-2xl border border-white/80 shadow-sm`}
      style={{ background: `${visual.color}18`, color: visual.color }}
      aria-hidden
    >
      {meta.emoji}
    </div>
  );
}

function RobotCard({
  agent,
  onToggle,
}: {
  agent: AgentCatalogItem;
  onToggle: (id: string, active: boolean) => void;
}) {
  const visual = agentVisual(agent.id);
  const isCore = CORE_IDS.has(agent.id);

  return (
    <article
      className="group relative flex flex-col overflow-hidden rounded-2xl border border-[var(--line)] bg-white/90 shadow-[var(--shadow-card)] transition duration-300 hover:-translate-y-0.5 hover:shadow-lg"
      style={{ ["--robot-accent" as string]: visual.color }}
    >
      <div
        className="h-1.5 w-full"
        style={{
          background: `linear-gradient(90deg, ${visual.color}, ${visual.color}55)`,
        }}
      />
      <div className="flex flex-1 flex-col p-4">
        <div className="flex items-start gap-3">
          <RobotAvatar agent={agent} />
          <div className="min-w-0 flex-1">
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0">
                <h2 className="truncate text-lg font-bold tracking-tight text-slate-900">
                  {agent.name}
                </h2>
                <p className="mt-0.5 text-xs font-semibold uppercase tracking-[0.08em] text-slate-500">
                  {roleLabel(agent.role)}
                </p>
              </div>
              <Badge tone={agent.active ? "success" : "neutral"}>
                {agent.active ? "Active" : "Idle"}
              </Badge>
            </div>
          </div>
        </div>

        <p className="mt-3 line-clamp-3 flex-1 text-sm leading-relaxed text-slate-600">
          {agent.description}
        </p>

        <div className="mt-3 flex flex-wrap gap-1.5">
          {isCore ? <Badge tone="accent">Core</Badge> : <Badge tone="info">Specialty</Badge>}
          <Badge tone="info">{agent.preferred_model}</Badge>
          <Badge>{AUTONOMY_LABEL[agent.autonomy_level] ?? `L${agent.autonomy_level}`}</Badge>
        </div>

        <div className="mt-4 grid grid-cols-2 gap-2">
          <div className="rounded-xl bg-slate-50 px-3 py-2">
            <div className="text-[10px] font-semibold uppercase tracking-[0.1em] text-slate-400">
              Success
            </div>
            <div className="mt-0.5 text-base font-bold text-slate-800">
              {Math.round(agent.success_rate * 100)}%
            </div>
            <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-slate-200">
              <div
                className="h-full rounded-full transition-all"
                style={{
                  width: `${Math.round(agent.success_rate * 100)}%`,
                  background: visual.color,
                }}
              />
            </div>
          </div>
          <div className="rounded-xl bg-slate-50 px-3 py-2">
            <div className="text-[10px] font-semibold uppercase tracking-[0.1em] text-slate-400">
              Avg tokens
            </div>
            <div className="mt-0.5 text-base font-bold text-slate-800">
              {agent.avg_cost_tokens.toLocaleString()}
            </div>
            <div className="mt-1 text-[11px] text-slate-400">per mission</div>
          </div>
        </div>

        <div className="mt-3 flex flex-wrap gap-1">
          {agent.tools.slice(0, 4).map((tool) => (
            <span
              key={tool}
              className="rounded-md bg-slate-100 px-1.5 py-0.5 text-[10px] font-semibold text-slate-600"
            >
              {tool}
            </span>
          ))}
          {agent.tools.length > 4 ? (
            <span className="rounded-md bg-slate-100 px-1.5 py-0.5 text-[10px] font-semibold text-slate-500">
              +{agent.tools.length - 4}
            </span>
          ) : null}
        </div>

        <Button
          variant="ghost"
          className="mt-4 w-full opacity-90 transition group-hover:opacity-100"
          onClick={() => onToggle(agent.id, agent.active)}
        >
          {agent.active ? "Deactivate" : "Activate"}
        </Button>
      </div>
    </article>
  );
}

export function AgentsPage() {
  const setToast = useAppStore((s) => s.setToast);
  const [agents, setAgents] = useState<AgentCatalogItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [role, setRole] = useState("all");
  const [status, setStatus] = useState<StatusFilter>("all");
  const [sort, setSort] = useState<SortKey>("name");
  const [page, setPage] = useState(1);

  useEffect(() => {
    let alive = true;
    async function loadAgents() {
      setLoading(true);
      setError(null);
      try {
        const catalog = await api.agents.list();
        if (alive) setAgents(catalog);
      } catch (err) {
        if (alive) setError(err instanceof Error ? err.message : "Failed to load robots");
      } finally {
        if (alive) setLoading(false);
      }
    }
    void loadAgents();
    return () => {
      alive = false;
    };
  }, []);

  useEffect(() => {
    setPage(1);
  }, [query, role, status, sort]);

  const roles = useMemo(() => {
    const set = new Set(agents.map((a) => a.role));
    return Array.from(set).sort((a, b) => roleLabel(a).localeCompare(roleLabel(b)));
  }, [agents]);

  const stats = useMemo(() => {
    const active = agents.filter((a) => a.active).length;
    const avgSuccess =
      agents.length === 0
        ? 0
        : Math.round(
            (agents.reduce((sum, a) => sum + a.success_rate, 0) / agents.length) * 100,
          );
    const specialties = agents.filter((a) => !CORE_IDS.has(a.id)).length;
    return { total: agents.length, active, avgSuccess, specialties };
  }, [agents]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    const list = agents.filter((agent) => {
      if (role !== "all" && agent.role !== role) return false;
      if (status === "active" && !agent.active) return false;
      if (status === "inactive" && agent.active) return false;
      if (!q) return true;
      return (
        agent.name.toLowerCase().includes(q) ||
        agent.role.toLowerCase().includes(q) ||
        agent.description.toLowerCase().includes(q) ||
        agent.preferred_model.toLowerCase().includes(q) ||
        agent.tools.some((t) => t.toLowerCase().includes(q))
      );
    });

    list.sort((a, b) => {
      if (sort === "success") return b.success_rate - a.success_rate;
      if (sort === "cost") return a.avg_cost_tokens - b.avg_cost_tokens;
      if (sort === "role") return roleLabel(a.role).localeCompare(roleLabel(b.role));
      // Core robots first, then name
      const ac = CORE_IDS.has(a.id) ? 0 : 1;
      const bc = CORE_IDS.has(b.id) ? 0 : 1;
      if (ac !== bc) return ac - bc;
      return a.name.localeCompare(b.name);
    });
    return list;
  }, [agents, query, role, status, sort]);

  const pageCount = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const pageItems = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  async function toggle(id: string, active: boolean) {
    try {
      const updated = await api.agents.patch(id, { active: !active });
      setAgents((current) => current.map((agent) => (agent.id === id ? updated : agent)));
      setToast(!active ? "Robot activated" : "Robot deactivated");
    } catch (err) {
      setToast(err instanceof Error ? err.message : "Failed to update robot");
    }
  }

  return (
    <div className="space-y-6">
      <header className="relative overflow-hidden rounded-3xl border border-slate-200/80 bg-[linear-gradient(135deg,#f8fafc_0%,#eef6ff_48%,#f1f5f9_100%)] px-5 py-6 shadow-[var(--shadow-card)] sm:px-7 sm:py-8">
        <div
          className="pointer-events-none absolute -right-16 -top-20 h-56 w-56 rounded-full opacity-40 blur-3xl"
          style={{ background: "radial-gradient(circle,#93c5fd,transparent 70%)" }}
        />
        <div
          className="pointer-events-none absolute -bottom-24 left-1/3 h-48 w-48 rounded-full opacity-30 blur-3xl"
          style={{ background: "radial-gradient(circle,#67e8f9,transparent 70%)" }}
        />
        <div className="relative">
          <p className="text-xs font-bold uppercase tracking-[0.16em] text-blue-600">
            Robot catalog
          </p>
          <h1 className="mt-2 max-w-2xl text-3xl font-extrabold tracking-tight text-slate-900 sm:text-4xl">
            Swarm robots ready for every specialty
          </h1>
          <p className="mt-2 max-w-2xl text-sm leading-relaxed text-slate-600 sm:text-base">
            Browse hundreds of English-ready example robots — from core delivery leads to niche
            specialists in frontend, security, DevOps, ML, and more.
          </p>

          <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {[
              { label: "Robots", value: stats.total },
              { label: "Active", value: stats.active },
              { label: "Specialties", value: stats.specialties },
              { label: "Avg success", value: `${stats.avgSuccess}%` },
            ].map((item) => (
              <div
                key={item.label}
                className="rounded-2xl border border-white/70 bg-white/70 px-4 py-3 backdrop-blur"
              >
                <div className="text-[11px] font-semibold uppercase tracking-[0.1em] text-slate-400">
                  {item.label}
                </div>
                <div className="mt-1 text-2xl font-extrabold tracking-tight text-slate-900">
                  {item.value}
                </div>
              </div>
            ))}
          </div>
        </div>
      </header>

      <section className="sticky top-0 z-10 -mx-1 space-y-3 rounded-2xl border border-slate-200 bg-white/95 p-3 shadow-sm backdrop-blur sm:p-4">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center">
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search robots, roles, tools, models…"
            className="w-full flex-1 rounded-xl border border-slate-200 bg-slate-50 px-3.5 py-2.5 text-sm outline-none ring-blue-500 transition focus:bg-white focus:ring-2"
          />
          <div className="flex flex-wrap gap-2">
            <select
              value={role}
              onChange={(e) => setRole(e.target.value)}
              className="rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm font-semibold text-slate-700 outline-none ring-blue-500 focus:ring-2"
            >
              <option value="all">All roles</option>
              {roles.map((r) => (
                <option key={r} value={r}>
                  {roleLabel(r)}
                </option>
              ))}
            </select>
            <select
              value={status}
              onChange={(e) => setStatus(e.target.value as StatusFilter)}
              className="rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm font-semibold text-slate-700 outline-none ring-blue-500 focus:ring-2"
            >
              <option value="all">All statuses</option>
              <option value="active">Active only</option>
              <option value="inactive">Idle only</option>
            </select>
            <select
              value={sort}
              onChange={(e) => setSort(e.target.value as SortKey)}
              className="rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm font-semibold text-slate-700 outline-none ring-blue-500 focus:ring-2"
            >
              <option value="name">Sort: name</option>
              <option value="role">Sort: role</option>
              <option value="success">Sort: success</option>
              <option value="cost">Sort: tokens</option>
            </select>
          </div>
        </div>
        <div className="flex flex-wrap items-center justify-between gap-2 text-xs font-semibold text-slate-500">
          <span>
            Showing {pageItems.length} of {filtered.length} robots
            {filtered.length !== agents.length ? ` (filtered from ${agents.length})` : ""}
          </span>
          <div className="flex flex-wrap gap-1.5">
            {roles.slice(0, 8).map((r) => {
              const meta = roleMeta(r);
              const selected = role === r;
              return (
                <button
                  key={r}
                  type="button"
                  onClick={() => setRole(selected ? "all" : r)}
                  className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 transition ${
                    selected
                      ? "bg-blue-600 text-white"
                      : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                  }`}
                >
                  <span aria-hidden>{meta.emoji}</span>
                  {meta.label}
                </button>
              );
            })}
          </div>
        </div>
      </section>

      {loading ? (
        <div className="rounded-2xl border border-slate-200 bg-white/80 px-6 py-16 text-center shadow-sm">
          <h3 className="text-lg font-bold text-slate-800">Loading robot catalog...</h3>
          <p className="mt-2 text-sm text-slate-500">Fetching the latest swarm specialists.</p>
        </div>
      ) : null}

      {error ? (
        <div className="rounded-2xl border border-rose-200 bg-rose-50 px-6 py-5 text-rose-700">
          <h3 className="font-bold">Could not load robots</h3>
          <p className="mt-1 text-sm">{error}</p>
        </div>
      ) : null}

      {!loading && !error && pageItems.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-slate-200 bg-white/70 px-6 py-16 text-center">
          <h3 className="text-lg font-bold text-slate-800">No robots match</h3>
          <p className="mt-2 text-sm text-slate-500">Try a different search or clear the filters.</p>
          <Button
            variant="soft"
            className="mt-4"
            onClick={() => {
              setQuery("");
              setRole("all");
              setStatus("all");
            }}
          >
            Clear filters
          </Button>
        </div>
      ) : !loading && !error ? (
        <div className="robot-catalog-grid grid gap-4 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
          {pageItems.map((agent) => (
            <RobotCard key={agent.id} agent={agent} onToggle={toggle} />
          ))}
        </div>
      ) : null}

      {!loading && !error && pageCount > 1 ? (
        <footer className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-slate-200 bg-white px-4 py-3">
          <span className="text-sm font-semibold text-slate-500">
            Page {page} of {pageCount}
          </span>
          <div className="flex gap-2">
            <Button
              variant="ghost"
              disabled={page <= 1}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
            >
              Previous
            </Button>
            <Button
              variant="ghost"
              disabled={page >= pageCount}
              onClick={() => setPage((p) => Math.min(pageCount, p + 1))}
            >
              Next
            </Button>
          </div>
        </footer>
      ) : null}
    </div>
  );
}
