import { useEffect, useMemo, useRef } from "react";
import { agentVisual } from "../agents";
import type { AgentBoardMessage, TaskCard } from "../types";

const TYPE_LABEL: Record<string, string> = {
  status: "status",
  handoff: "handoff",
  question: "pergunta",
  result: "resultado",
};

function formatTime(iso: string) {
  try {
    return new Date(iso).toLocaleTimeString(undefined, {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  } catch {
    return "";
  }
}

function AgentBubble({ agentId, size = "md" }: { agentId: string; size?: "sm" | "md" }) {
  const agent = agentVisual(agentId);
  const dim = size === "sm" ? "h-6 w-6 text-xs" : "h-8 w-8 text-sm";
  return (
    <div
      title={`${agent.name} · ${agent.role}`}
      className={`${dim} agent-float inline-flex shrink-0 items-center justify-center rounded-full border border-white shadow-sm`}
      style={{ background: `${agent.color}22`, color: agent.color }}
    >
      <span aria-hidden>{agent.emoji}</span>
    </div>
  );
}

function MessageRow({
  msg,
  cardTitle,
}: {
  msg: AgentBoardMessage;
  cardTitle?: string;
}) {
  const from = agentVisual(msg.from_agent_id);
  const to = msg.to_agent_id ? agentVisual(msg.to_agent_id) : null;
  const typeLabel = TYPE_LABEL[msg.message_type] ?? msg.message_type;

  return (
    <div className="group rounded-xl border border-slate-100 bg-white/90 p-2.5 shadow-sm transition hover:border-slate-200">
      <div className="flex gap-2">
        <AgentBubble agentId={msg.from_agent_id} size="sm" />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="text-xs font-bold text-slate-800">{from.name}</span>
            <span className="rounded-full bg-slate-100 px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wide text-slate-500">
              {typeLabel}
            </span>
            {to ? (
              <span className="text-[10px] text-slate-400">
                → {to.name}
              </span>
            ) : (
              <span className="text-[10px] text-slate-400">→ board</span>
            )}
            <span className="ml-auto text-[10px] text-slate-400">{formatTime(msg.created_at)}</span>
          </div>
          <p className="mt-1 text-xs leading-relaxed text-slate-700">{msg.content}</p>
          {cardTitle ? (
            <p className="mt-1 truncate text-[10px] font-medium text-blue-600/80">#{cardTitle}</p>
          ) : null}
        </div>
      </div>
    </div>
  );
}

export function BoardChatPanel({
  messages,
  cards,
  filterCardId,
  onFilterCardId,
  loading,
  open,
  onToggle,
}: {
  messages: AgentBoardMessage[];
  cards: TaskCard[];
  filterCardId: string | null;
  onFilterCardId: (id: string | null) => void;
  loading?: boolean;
  open: boolean;
  onToggle: () => void;
}) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const cardById = useMemo(() => new Map(cards.map((c) => [c.id, c])), [cards]);

  const ordered = useMemo(() => {
    const list = filterCardId
      ? messages.filter((m) => m.card_id === filterCardId)
      : messages;
    return [...list].sort(
      (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime(),
    );
  }, [messages, filterCardId]);

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  }, [ordered.length, open]);

  if (!open) {
    return (
      <button
        type="button"
        onClick={onToggle}
        className="flex h-full w-10 shrink-0 flex-col items-center justify-center gap-1 rounded-xl border border-slate-200 bg-white text-[10px] font-bold text-slate-500 shadow-sm transition hover:border-blue-300 hover:text-blue-600"
        title="Abrir painel ao vivo do gestor"
      >
        <span className="text-lg">🤖</span>
        <span className="[writing-mode:vertical-rl] rotate-180">Nova</span>
        {messages.length ? (
          <span className="rounded-full bg-blue-600 px-1.5 py-0.5 text-[9px] text-white">
            {messages.length > 99 ? "99+" : messages.length}
          </span>
        ) : null}
      </button>
    );
  }

  return (
    <aside className="flex h-full w-72 shrink-0 flex-col overflow-hidden rounded-xl border border-slate-200 bg-slate-50/80 shadow-sm lg:w-80">
      <header className="flex shrink-0 items-center justify-between gap-2 border-b border-slate-200 bg-white px-3 py-2">
        <div className="min-w-0">
          <h2 className="text-sm font-extrabold text-slate-900">Nova · Board live</h2>
          <p className="text-[10px] text-slate-500">Gestor e agentes narrando o que acontece</p>
        </div>
        <button
          type="button"
          onClick={onToggle}
          className="rounded-lg px-2 py-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
          title="Recolher"
        >
          ✕
        </button>
      </header>

      <div className="shrink-0 border-b border-slate-200 bg-white px-2 py-1.5">
        <select
          value={filterCardId ?? ""}
          onChange={(e) => onFilterCardId(e.target.value || null)}
          className="w-full rounded-lg border border-slate-200 bg-slate-50 px-2 py-1.5 text-[11px] outline-none ring-blue-500 focus:ring-2"
        >
          <option value="">Todos os cartões</option>
          {cards
            .filter((c) => (c.kind ?? "epic") === "epic" || !c.parent_id)
            .map((c) => (
              <option key={c.id} value={c.id}>
                {c.title}
              </option>
            ))}
        </select>
      </div>

      <div ref={scrollRef} className="min-h-0 flex-1 space-y-2 overflow-y-auto p-2">
        {loading && !ordered.length ? (
          <p className="py-8 text-center text-xs text-slate-400">Carregando mensagens…</p>
        ) : null}
        {!loading && !ordered.length ? (
          <div className="py-8 text-center text-xs text-slate-400">
            <p>Nenhuma mensagem A2A ainda.</p>
            <p className="mt-1">Crie um cartão para ver os agentes conversando.</p>
          </div>
        ) : null}
        {ordered.map((msg) => (
          <MessageRow
            key={msg.id}
            msg={msg}
            cardTitle={cardById.get(msg.card_id)?.title}
          />
        ))}
      </div>
    </aside>
  );
}
