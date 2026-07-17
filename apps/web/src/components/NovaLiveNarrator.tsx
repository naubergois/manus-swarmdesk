import { useEffect, useMemo, useState } from "react";
import { agentVisual } from "../agents";
import type { AgentBoardMessage, BoardLiveState } from "../types";

const MOOD_STYLE: Record<string, { bar: string; pill: string; label: string }> = {
  idle: {
    bar: "from-slate-100 via-white to-blue-50",
    pill: "bg-slate-200 text-slate-700",
    label: "em espera",
  },
  busy: {
    bar: "from-sky-100 via-white to-indigo-50",
    pill: "bg-blue-600 text-white",
    label: "gerenciando",
  },
  blocked: {
    bar: "from-rose-100 via-white to-amber-50",
    pill: "bg-rose-600 text-white",
    label: "bloqueio",
  },
  celebrate: {
    bar: "from-emerald-100 via-white to-cyan-50",
    pill: "bg-emerald-600 text-white",
    label: "live",
  },
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

function SpeakBubble({
  agentId,
  text,
  pulse,
}: {
  agentId: string;
  text: string;
  pulse?: boolean;
}) {
  const agent = agentVisual(agentId);
  return (
    <div
      className={`nova-speak flex min-w-0 flex-1 items-start gap-2.5 rounded-2xl border border-white/80 bg-white/90 px-3 py-2 shadow-sm ${
        pulse ? "nova-speak-pulse" : ""
      }`}
    >
      <div
        className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-white text-base shadow-sm"
        style={{ background: `${agent.color}22`, color: agent.color }}
        title={`${agent.name} · ${agent.role}`}
      >
        <span aria-hidden>{agent.emoji}</span>
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="text-xs font-extrabold text-slate-900">{agent.name}</span>
          <span className="text-[10px] font-semibold uppercase tracking-wide text-slate-400">
            {agent.role}
          </span>
        </div>
        <p className="mt-0.5 text-sm leading-snug text-slate-700">{text}</p>
      </div>
    </div>
  );
}

function TickItem({ msg }: { msg: AgentBoardMessage }) {
  const agent = agentVisual(msg.from_agent_id);
  return (
    <div className="nova-tick flex shrink-0 items-center gap-1.5 rounded-full border border-slate-200/80 bg-white/80 px-2.5 py-1 text-[11px] shadow-sm">
      <span aria-hidden style={{ color: agent.color }}>
        {agent.emoji}
      </span>
      <span className="max-w-[220px] truncate font-medium text-slate-700">{msg.content}</span>
      <span className="text-[9px] text-slate-400">{formatTime(msg.created_at)}</span>
    </div>
  );
}

export function NovaLiveNarrator({
  live,
  onFocusCard,
}: {
  live: BoardLiveState | null;
  onFocusCard?: (cardId: string | null) => void;
}) {
  const [tickIndex, setTickIndex] = useState(0);
  const mood = MOOD_STYLE[live?.mood ?? "idle"] ?? MOOD_STYLE.idle;
  const recent = live?.recent ?? [];
  const headlineMsg = recent[0] ?? null;
  const speakAgent = headlineMsg?.from_agent_id ?? live?.speaking_agent_id ?? "supervisor";
  const speakText =
    headlineMsg?.content ??
    live?.headline ??
    "Sou a Nova — gestora deste board. Assim que algo acontecer, eu narro aqui.";

  const ticker = useMemo(() => recent.slice(0, 8), [recent]);

  useEffect(() => {
    if (ticker.length <= 1) return;
    const id = window.setInterval(() => {
      setTickIndex((i) => (i + 1) % ticker.length);
    }, 3200);
    return () => window.clearInterval(id);
  }, [ticker.length]);

  useEffect(() => {
    setTickIndex(0);
  }, [ticker[0]?.id]);

  return (
    <section
      className={`nova-narrator shrink-0 overflow-hidden rounded-2xl border border-slate-200/90 bg-gradient-to-r ${mood.bar} shadow-sm`}
      aria-live="polite"
    >
      <div className="flex flex-wrap items-center gap-2 border-b border-slate-200/60 px-3 py-2">
        <div className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-blue-600 text-sm text-white shadow agent-working">
            🤖
          </div>
          <div>
            <h2 className="text-sm font-extrabold tracking-tight text-slate-900">
              Nova · Gestor de Projetos
            </h2>
            <p className="text-[10px] font-medium text-slate-500">
              Narra e gerencia tudo que acontece no board
            </p>
          </div>
        </div>
        <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide ${mood.pill}`}>
          {mood.label}
        </span>
        <div className="ml-auto flex flex-wrap gap-1">
          {(live?.lane_counts ?? []).map((lane) => (
            <span
              key={lane.id}
              className="rounded-md bg-white/80 px-1.5 py-0.5 text-[10px] font-bold text-slate-600 shadow-sm"
            >
              {lane.label} {lane.count}
            </span>
          ))}
        </div>
      </div>

      <div className="flex flex-col gap-2 px-3 py-2.5 sm:flex-row sm:items-stretch">
        <SpeakBubble agentId={speakAgent} text={speakText} pulse={live?.mood === "busy"} />
        <div className="flex w-full shrink-0 flex-col justify-between gap-1.5 sm:w-56 lg:w-64">
          <p className="text-[11px] leading-relaxed text-slate-600">{live?.briefing ?? "Carregando briefing…"}</p>
          {live?.focus_card_id ? (
            <button
              type="button"
              onClick={() => onFocusCard?.(live.focus_card_id)}
              className="rounded-lg border border-blue-200 bg-blue-50 px-2 py-1.5 text-left text-[11px] font-bold text-blue-700 transition hover:border-blue-400 hover:bg-blue-100"
            >
              Foco → {live.focus_card_title ?? live.focus_card_id}
            </button>
          ) : null}
        </div>
      </div>

      {ticker.length ? (
        <div className="nova-ticker-track flex gap-2 overflow-hidden border-t border-slate-200/60 bg-white/40 px-3 py-2">
          <div
            key={ticker[tickIndex % ticker.length]?.id ?? tickIndex}
            className="nova-ticker-slide flex gap-2"
          >
            {ticker.map((msg) => (
              <TickItem key={msg.id} msg={msg} />
            ))}
          </div>
        </div>
      ) : null}
    </section>
  );
}
