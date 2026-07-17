import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import { Badge, Button, EmptyState, Panel, priorityTone } from "../components/ui";
import { useAppStore } from "../store";
import { COLUMN_LABELS, type CardDetail } from "../types";

const tabs = [
  "descricao",
  "requisitos",
  "plano",
  "agentes",
  "artefatos",
  "testes",
  "tickets",
  "decisoes",
  "historico",
] as const;

type Tab = (typeof tabs)[number];

export function CardDetailPage() {
  const { id = "" } = useParams();
  const { setToast, refreshAll } = useAppStore();
  const [detail, setDetail] = useState<CardDetail | null>(null);
  const [tab, setTab] = useState<Tab>("descricao");
  const [busy, setBusy] = useState(false);

  async function load() {
    const data = await api.cards.get(id);
    setDetail(data);
  }

  useEffect(() => {
    void load().catch((err) =>
      setToast(err instanceof Error ? err.message : "Falha ao carregar cartão"),
    );
    const timer = window.setInterval(() => void load(), 5000);
    return () => window.clearInterval(timer);
  }, [id]);

  async function decide(kind: "approve" | "reject") {
    setBusy(true);
    try {
      if (kind === "approve") await api.cards.approve(id, "Approved from card detail");
      else await api.cards.reject(id, "Rejected from card detail");
      setToast(kind === "approve" ? "Approval recorded" : "Sent back to refinement");
      await load();
      await refreshAll();
    } catch (err) {
      setToast(err instanceof Error ? err.message : "Approval failed");
    } finally {
      setBusy(false);
    }
  }

  if (!detail) {
    return <EmptyState title="Loading card" body="Fetching requirements, plan, and evidence..." />;
  }

  const { card, requirements, plan, mission, artifacts, tests, reviews, tickets, approvals, timeline } =
    detail;
  const pending = approvals.filter((a) => a.decision === "pendente");

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <Link to="/kanban" className="text-sm font-semibold text-blue-600">
            ← Back to board
          </Link>
          <h1 className="mt-2 text-4xl font-extrabold tracking-tight">{card.title}</h1>
          <div className="mt-3 flex flex-wrap gap-2">
            <Badge tone="info">{COLUMN_LABELS[card.column]}</Badge>
            <Badge tone={priorityTone(card.priority)}>{card.priority}</Badge>
            <Badge>{card.type}</Badge>
            <Badge tone="accent">autonomy {card.autonomy_level}</Badge>
            {card.preview_url ? <Badge tone="success">Live preview</Badge> : null}
          </div>
        </div>
        <div className="flex gap-2">
          {card.preview_url ? (
            <Button
              variant="soft"
              onClick={() => window.open(card.preview_url!, "_blank", "noreferrer")}
            >
              Open live app
            </Button>
          ) : null}
          {pending.length ? (
            <>
              <Button disabled={busy} onClick={() => void decide("approve")}>
                Approve
              </Button>
              <Button variant="danger" disabled={busy} onClick={() => void decide("reject")}>
                Reject
              </Button>
            </>
          ) : null}
        </div>
      </div>

      <div className="flex flex-wrap gap-2">
        {tabs.map((item) => (
          <button
            key={item}
            onClick={() => setTab(item)}
            className={`rounded-full px-4 py-2 text-sm font-semibold capitalize ${
              tab === item
                ? "bg-[var(--accent)] text-white"
                : "border border-[var(--line)] bg-white/70"
            }`}
          >
            {item}
          </button>
        ))}
      </div>

      {card.preview_url ? (
        <Panel
          title="App running"
          action={
            <a
              href={card.preview_url}
              target="_blank"
              rel="noreferrer"
              className="text-sm font-bold text-emerald-700 hover:underline"
            >
              Open ↗
            </a>
          }
        >
          <div className="overflow-hidden rounded-xl border border-emerald-100 bg-slate-100">
            <iframe
              title={`Live preview — ${card.title}`}
              src={card.preview_url}
              className="h-[420px] w-full border-0 bg-white"
              sandbox="allow-scripts allow-same-origin allow-forms allow-popups"
            />
          </div>
          <p className="mt-2 text-xs text-[var(--muted)]">{card.preview_url}</p>
        </Panel>
      ) : null}

      {tab === "descricao" && (
        <Panel title="Descrição">
          <p className="whitespace-pre-wrap leading-relaxed">{card.description}</p>
          {card.block_reason ? (
            <p className="mt-4 rounded-2xl bg-[#fecdd3] px-4 py-3 text-sm text-[var(--danger)]">
              Bloqueio: {card.block_reason}
            </p>
          ) : null}
          <div className="mt-5 grid gap-3 sm:grid-cols-3">
            <Meta label="Tokens" value={`${card.budget_spent.toLocaleString()} / ${card.budget_tokens.toLocaleString()}`} />
            <Meta label="Responsável" value={card.human_owner} />
            <Meta label="Solicitante" value={card.requester} />
          </div>
          <div className="mt-5">
            <h3 className="font-semibold">Critérios de aceitação</h3>
            <ul className="mt-2 list-disc space-y-1 pl-5 text-sm">
              {card.acceptance_criteria.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </div>
        </Panel>
      )}

      {tab === "requisitos" && (
        <Panel title="Requisitos">
          {!requirements ? (
            <EmptyState title="Sem requisitos" body="Ainda não refinados." />
          ) : (
            <div className="space-y-4">
              <p>
                <strong>Objetivo:</strong> {requirements.objective}
              </p>
              <List title="Funcionais" items={requirements.functional} />
              <List title="Não funcionais" items={requirements.non_functional} />
              <List title="Regras de negócio" items={requirements.business_rules} />
              <List title="Fora de escopo" items={requirements.out_of_scope} />
            </div>
          )}
        </Panel>
      )}

      {tab === "plano" && (
        <Panel title="Plano de execução">
          {!plan ? (
            <EmptyState title="Sem plano" body="Aguardando planejamento." />
          ) : (
            <div className="space-y-4">
              <p>{plan.strategy}</p>
              <div className="space-y-2">
                {plan.tasks.map((task) => (
                  <div
                    key={task.id}
                    className="flex items-center justify-between rounded-2xl border border-[var(--line)] px-4 py-3"
                  >
                    <div>
                      <div className="font-medium">{task.title}</div>
                      <div className="text-xs text-[var(--muted)]">
                        {task.agent_role} · grupo {task.parallel_group}
                      </div>
                    </div>
                    <Badge>{task.status}</Badge>
                  </div>
                ))}
              </div>
            </div>
          )}
        </Panel>
      )}

      {tab === "agentes" && (
        <Panel title="Agentes / missão">
          {!mission ? (
            <EmptyState title="Sem missão" body="O enxame ainda não foi formado." />
          ) : (
            <div className="space-y-4">
              <div className="flex flex-wrap gap-2">
                <Badge tone="accent">{mission.topology}</Badge>
                <Badge>{mission.status}</Badge>
                <Badge tone="info">{Math.round(mission.progress * 100)}%</Badge>
              </div>
              {mission.agents.map((agent) => (
                <div
                  key={`${agent.agent_id}-${agent.subtask}`}
                  className="rounded-2xl border border-[var(--line)] px-4 py-3"
                >
                  <div className="font-semibold">
                    {agent.agent_id} · {agent.role}
                  </div>
                  <div className="mt-1 text-sm">{agent.subtask}</div>
                  {agent.output_summary ? (
                    <div className="mt-2 text-sm text-[var(--muted)]">{agent.output_summary}</div>
                  ) : null}
                </div>
              ))}
            </div>
          )}
        </Panel>
      )}

      {tab === "artefatos" && (
        <Panel title="Artefatos">
          {!artifacts.length ? (
            <EmptyState title="Sem artefatos" body="Nada produzido ainda." />
          ) : (
            <div className="space-y-3">
              {artifacts.map((art) => (
                <div key={art.id} className="rounded-2xl border border-[var(--line)] px-4 py-3">
                  <div className="font-semibold">{art.name}</div>
                  <div className="text-sm text-[var(--muted)]">
                    {art.type} · {art.author} · {art.location}
                  </div>
                  <p className="mt-2 text-sm">{art.description}</p>
                </div>
              ))}
            </div>
          )}
        </Panel>
      )}

      {tab === "testes" && (
        <Panel title="Testes e revisão">
          <div className="space-y-4">
            {tests.map((test) => (
              <div key={test.id} className="rounded-2xl border border-[var(--line)] px-4 py-3">
                <div className="font-semibold">{test.suite}</div>
                <div className="mt-1 text-sm">
                  {test.passed}/{test.executed} ok · cobertura {test.coverage}% · falhas {test.failed}
                </div>
                <p className="mt-2 text-sm text-[var(--muted)]">{test.recommendation}</p>
              </div>
            ))}
            {reviews.map((review) => (
              <div key={review.id} className="rounded-2xl border border-[var(--line)] px-4 py-3">
                <div className="flex items-center gap-2">
                  <Badge tone={review.decision === "aprovado" ? "accent" : "danger"}>
                    {review.decision}
                  </Badge>
                  <span className="text-sm">confiança {Math.round(review.confidence * 100)}%</span>
                </div>
                <p className="mt-2 text-sm">{review.rationale}</p>
              </div>
            ))}
            {!tests.length && !reviews.length ? (
              <EmptyState title="Sem testes/revisão" body="Aguardando execução do enxame." />
            ) : null}
          </div>
        </Panel>
      )}

      {tab === "tickets" && (
        <Panel title="Chamados vinculados">
          {!tickets.length ? (
            <EmptyState title="Sem chamados" body="Nenhum bloqueio registrado." />
          ) : (
            <div className="space-y-3">
              {tickets.map((ticket) => (
                <div key={ticket.id} className="rounded-2xl border border-[var(--line)] px-4 py-3">
                  <div className="font-semibold">{ticket.title}</div>
                  <div className="mt-1 flex gap-2">
                    <Badge tone="danger">{ticket.severity}</Badge>
                    <Badge>{ticket.status}</Badge>
                  </div>
                  <p className="mt-2 text-sm">{ticket.description}</p>
                </div>
              ))}
            </div>
          )}
        </Panel>
      )}

      {tab === "decisoes" && (
        <Panel title="Aprovações humanas">
          {!approvals.length ? (
            <EmptyState title="Sem decisões" body="Nenhuma solicitação ainda." />
          ) : (
            <div className="space-y-3">
              {approvals.map((apr) => (
                <div key={apr.id} className="rounded-2xl border border-[var(--line)] px-4 py-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge tone="info">{apr.type}</Badge>
                    <Badge
                      tone={
                        apr.decision === "aprovado"
                          ? "accent"
                          : apr.decision === "reprovado"
                            ? "danger"
                            : "warn"
                      }
                    >
                      {apr.decision}
                    </Badge>
                  </div>
                  <p className="mt-2 text-sm">{apr.comment || "—"}</p>
                </div>
              ))}
            </div>
          )}
        </Panel>
      )}

      {tab === "historico" && (
        <Panel title="Linha do tempo">
          <div className="space-y-3">
            {timeline.map((event) => (
              <div
                key={event.id}
                className="grid gap-1 rounded-2xl border border-[var(--line)] px-4 py-3 sm:grid-cols-[160px_1fr]"
              >
                <div className="text-xs text-[var(--muted)]">
                  {new Date(event.created_at).toLocaleString()}
                </div>
                <div>
                  <div className="font-semibold">
                    {event.action} · {event.actor}
                  </div>
                  <div className="text-sm text-[var(--muted)]">
                    {event.previous_state ?? "—"} → {event.next_state ?? "—"}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </Panel>
      )}
    </div>
  );
}

function Meta({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-[var(--line)] bg-white/60 px-4 py-3">
      <div className="text-xs uppercase tracking-[0.08em] text-[var(--muted)]">{label}</div>
      <div className="mt-1 font-semibold">{value}</div>
    </div>
  );
}

function List({ title, items }: { title: string; items: string[] }) {
  return (
    <div>
      <h3 className="font-semibold">{title}</h3>
      <ul className="mt-2 list-disc space-y-1 pl-5 text-sm">
        {items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </div>
  );
}
