import { useEffect } from "react";
import { Link } from "react-router-dom";
import { Badge, Panel, Stat } from "../components/ui";
import { useAppStore } from "../store";
import { COLUMN_LABELS } from "../types";

export function DashboardPage() {
  const { metrics, cards, refreshAll, loading } = useAppStore();

  useEffect(() => {
    void refreshAll();
    const id = window.setInterval(() => void refreshAll(), 8000);
    return () => window.clearInterval(id);
  }, [refreshAll]);

  const running = cards.filter((c) =>
    ["em_execucao", "em_revisao", "em_testes", "pronto_enxame"].includes(c.column),
  );
  const blocked = cards.filter((c) => c.column === "bloqueado");
  const liveApps = cards.filter((c) => Boolean(c.preview_url));

  return (
    <div className="space-y-6">
      <header className="max-w-3xl">
        <p className="text-sm font-bold uppercase tracking-[0.14em] text-blue-600">Operations</p>
        <h1 className="mt-2 text-4xl font-extrabold tracking-tight sm:text-5xl">Mankiu</h1>
        <p className="mt-3 text-base text-slate-500">
          Executive view of the multi-agent software factory — builds, blockers, live apps, and cost.
        </p>
      </header>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Stat label="Building" value={metrics?.in_execution ?? 0} hint="Active swarm cards" />
        <Stat label="Blocked" value={metrics?.blocked ?? 0} hint="External dependencies" />
        <Stat label="Live apps" value={liveApps.length} hint="Deployed previews" />
        <Stat
          label="Est. cost"
          value={`$${(metrics?.total_cost_usd ?? 0).toFixed(2)}`}
          hint={`${(metrics?.total_tokens ?? 0).toLocaleString()} tokens`}
        />
      </div>

      <div className="grid gap-4 xl:grid-cols-[1.2fr_0.8fr]">
        <Panel title="Operational queue" action={loading ? <Badge>Refreshing</Badge> : null}>
          <div className="space-y-3">
            {[...running, ...blocked].slice(0, 8).map((card) => (
              <Link
                key={card.id}
                to={`/cards/${card.id}`}
                className="flex items-start justify-between gap-3 rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 transition hover:border-blue-300"
              >
                <div>
                  <div className="font-bold">{card.title}</div>
                  <div className="mt-1 text-sm text-slate-500">
                    {COLUMN_LABELS[card.column]} ·{" "}
                    {card.agents.slice(0, 3).join(", ") || "no agents yet"}
                  </div>
                </div>
                <Badge tone={card.column === "bloqueado" ? "danger" : "accent"}>
                  {card.priority}
                </Badge>
              </Link>
            ))}
            {!running.length && !blocked.length ? (
              <p className="text-sm text-slate-500">No tasks in progress right now.</p>
            ) : null}
          </div>
        </Panel>

        <Panel title="Agent performance">
          <div className="space-y-3">
            {(metrics?.agent_performance ?? []).slice(0, 8).map((agent) => (
              <div key={agent.id} className="flex items-center justify-between gap-3">
                <div>
                  <div className="font-semibold">{agent.name}</div>
                  <div className="text-xs text-slate-500">
                    {agent.avg_cost_tokens.toLocaleString()} avg tokens
                  </div>
                </div>
                <div className="text-right">
                  <div className="font-bold text-blue-600">
                    {Math.round(agent.success_rate * 100)}%
                  </div>
                  <div className="text-xs text-slate-500">{agent.active ? "active" : "off"}</div>
                </div>
              </div>
            ))}
          </div>
        </Panel>
      </div>
    </div>
  );
}
