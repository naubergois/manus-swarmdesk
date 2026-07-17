import { useEffect } from "react";
import { Link } from "react-router-dom";
import { Badge, EmptyState, Panel, Stat } from "../components/ui";
import { useAppStore } from "../store";

export function SwarmPage() {
  const { missions, cards, refreshAll } = useAppStore();

  useEffect(() => {
    void refreshAll();
    const id = window.setInterval(() => void refreshAll(), 5000);
    return () => window.clearInterval(id);
  }, [refreshAll]);

  const active = missions.filter((m) =>
    ["running", "executing", "awaiting_delivery_approval", "blocked"].includes(m.status),
  );
  const selected = active[0] ?? missions[0];
  const card = selected ? cards.find((c) => c.id === selected.card_id) : null;

  return (
    <div className="space-y-5">
      <header>
        <p className="text-sm font-semibold uppercase tracking-[0.14em] text-[var(--accent)]">
          Ruflo
        </p>
        <h1 className="mt-2 text-4xl font-semibold tracking-tight">Central do enxame</h1>
        <p className="mt-2 max-w-2xl text-[var(--muted)]">
          Topologia hierárquica, agentes ativos, progresso e bloqueios da missão atual.
        </p>
      </header>

      <div className="grid gap-4 sm:grid-cols-3">
        <Stat label="Missões" value={missions.length} />
        <Stat label="Ativas" value={active.length} />
        <Stat
          label="Progresso"
          value={selected ? `${Math.round(selected.progress * 100)}%` : "—"}
        />
      </div>

      {!selected ? (
        <EmptyState
          title="Nenhum enxame formado"
          body="Aprove um cartão em Aguardando aprovação para disparar o enxame de agentes."
        />
      ) : (
        <div className="grid gap-4 xl:grid-cols-[0.9fr_1.1fr]">
          <Panel title="Topologia">
            <div className="space-y-4">
              <div className="rounded-[24px] border border-[var(--line)] bg-[#1c2430] px-5 py-6 text-[#f7f3ea]">
                <div className="text-xs uppercase tracking-[0.12em] text-[#9aa5b5]">Coordenador</div>
                <div className="mt-2 text-2xl font-semibold">coordenador</div>
                <div className="mt-6 grid gap-3 sm:grid-cols-2">
                  {selected.agents
                    .filter((a) => a.role !== "coordenador")
                    .map((agent) => (
                      <div
                        key={`${agent.agent_id}-${agent.subtask}`}
                        className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3"
                      >
                        <div className="font-semibold">{agent.agent_id}</div>
                        <div className="mt-1 text-xs text-[#b7c0cc]">{agent.status}</div>
                      </div>
                    ))}
                </div>
              </div>
              <div className="flex flex-wrap gap-2">
                <Badge tone="accent">{selected.topology}</Badge>
                <Badge>{selected.status}</Badge>
                <Badge tone="info">{selected.consensus_policy}</Badge>
              </div>
              {card ? (
                <Link to={`/cards/${card.id}`} className="text-sm font-semibold text-[var(--accent)]">
                  Cartão: {card.title}
                </Link>
              ) : null}
            </div>
          </Panel>

          <Panel title="Tarefas atribuídas">
            <div className="space-y-3">
              {selected.agents.map((agent) => (
                <div
                  key={`${agent.agent_id}-${agent.subtask}`}
                  className="rounded-2xl border border-[var(--line)] px-4 py-3"
                >
                  <div className="flex items-center justify-between gap-3">
                    <div className="font-semibold">
                      {agent.agent_id} · {agent.role}
                    </div>
                    <Badge tone={agent.status === "completed" ? "accent" : "neutral"}>
                      {agent.status}
                    </Badge>
                  </div>
                  <p className="mt-2 text-sm">{agent.subtask}</p>
                  {agent.output_summary ? (
                    <p className="mt-2 text-sm text-[var(--muted)]">{agent.output_summary}</p>
                  ) : null}
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {agent.tools.map((tool) => (
                      <Badge key={tool} tone="info">
                        {tool}
                      </Badge>
                    ))}
                  </div>
                </div>
              ))}
              {selected.errors.length ? (
                <div className="rounded-2xl bg-[#fecdd3] px-4 py-3 text-sm text-[var(--danger)]">
                  {selected.errors.join(" · ")}
                </div>
              ) : null}
            </div>
          </Panel>
        </div>
      )}

      <Panel title="Todas as missões">
        <div className="space-y-2">
          {missions.map((mission) => (
            <div
              key={mission.id}
              className="flex items-center justify-between rounded-2xl border border-[var(--line)] px-4 py-3"
            >
              <div>
                <div className="font-medium">{mission.objective}</div>
                <div className="text-xs text-[var(--muted)]">{mission.id}</div>
              </div>
              <Badge>{Math.round(mission.progress * 100)}%</Badge>
            </div>
          ))}
        </div>
      </Panel>
    </div>
  );
}
