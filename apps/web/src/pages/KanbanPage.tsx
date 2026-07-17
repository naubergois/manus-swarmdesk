import {
  DndContext,
  DragOverlay,
  PointerSensor,
  useDraggable,
  useDroppable,
  useSensor,
  useSensors,
  type DragEndEvent,
  type DragStartEvent,
} from "@dnd-kit/core";
import { CSS } from "@dnd-kit/utilities";
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { AGENT_ROBOTS, SOFTWARE_TEMPLATES, agentVisual } from "../agents";
import { api } from "../api/client";
import { BoardChatPanel } from "../components/BoardChatPanel";
import { Badge, Button, PRIORITY_LABEL, priorityTone } from "../components/ui";
import { playRobotCheer } from "../lib/robotCheer";
import { useAppStore } from "../store";
import {
  BOARD_LANES,
  COLUMN_LABELS,
  COLUMN_SHORT_LABELS,
  laneForColumn,
  resolveLaneDropTarget,
  type BoardLane,
  type BoardLaneId,
  type AgentBoardMessage,
  type KanbanColumn,
  type TaskCard,
} from "../types";

const WORKING_COLUMNS = new Set<KanbanColumn>([
  "triagem",
  "refinamento",
  "pronto_enxame",
  "em_execucao",
  "em_revisao",
  "em_testes",
]);

const RUNNING_SWARM_STATUSES = ["running", "coordinating", "executing"];

const SWARM_CARD_COLUMNS = new Set<KanbanColumn>([
  "pronto_enxame",
  "em_execucao",
  "em_revisao",
  "em_testes",
  "bloqueado",
  "aguardando_aprovacao",
]);

/** Mirrors backend ALLOWED transitions for smarter lane drops. */
const ALLOWED: Partial<Record<KanbanColumn, KanbanColumn[]>> = {
  entrada: ["triagem", "cancelado"],
  triagem: ["refinamento", "aguardando_decisao", "cancelado"],
  refinamento: ["aguardando_aprovacao", "aguardando_decisao", "cancelado"],
  aguardando_aprovacao: ["pronto_enxame", "refinamento", "cancelado"],
  pronto_enxame: ["em_execucao", "bloqueado", "cancelado"],
  em_execucao: ["em_revisao", "bloqueado", "aguardando_decisao", "cancelado"],
  em_revisao: ["em_testes", "em_execucao", "aguardando_decisao"],
  em_testes: ["pronto_entrega", "em_execucao", "bloqueado"],
  aguardando_decisao: ["refinamento", "em_execucao", "pronto_enxame", "cancelado", "bloqueado"],
  pronto_entrega: ["concluido", "em_execucao", "cancelado"],
  bloqueado: ["em_execucao", "aguardando_decisao", "cancelado"],
  concluido: [],
  cancelado: [],
};

function AgentAvatar({
  id,
  working = false,
  celebrating = false,
  motionDelayMs = 0,
  size = "md",
}: {
  id: string;
  working?: boolean;
  celebrating?: boolean;
  motionDelayMs?: number;
  size?: "sm" | "md";
}) {
  const agent = agentVisual(id);
  const dim = size === "sm" ? "h-6 w-6 text-xs" : "h-8 w-8 text-sm";
  const motion = celebrating
    ? "agent-celebrate"
    : working
      ? "agent-working"
      : "agent-float";
  return (
    <div
      title={`${agent.name} · ${agent.role}`}
      className={`${dim} ${motion} inline-flex items-center justify-center rounded-full border border-white text-center shadow-sm`}
      style={{
        background: `${agent.color}22`,
        color: agent.color,
        animationDelay: `${motionDelayMs}ms`,
      }}
    >
      <span aria-hidden>{agent.emoji}</span>
    </div>
  );
}

function DroppableLane({
  lane,
  cards,
  allCards,
  selectedIds,
  celebrating,
  onToggleSelect,
  onDelete,
}: {
  lane: BoardLane;
  cards: TaskCard[];
  allCards: TaskCard[];
  selectedIds: Set<string>;
  celebrating: boolean;
  onToggleSelect: (id: string) => void;
  onDelete: (card: TaskCard) => void;
}) {
  const { setNodeRef, isOver } = useDroppable({ id: lane.id });
  return (
    <div
      ref={setNodeRef}
      className={`flex min-h-0 min-w-0 flex-col rounded-2xl bg-[var(--board)]/90 transition ${
        isOver ? "ring-2 ring-blue-500 ring-offset-1" : ""
      }`}
    >
      <div className="flex shrink-0 items-center justify-between gap-2 px-3 py-2.5">
        <div className="flex min-w-0 items-center gap-2">
          <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: lane.color }} />
          <h3 className="truncate text-sm font-bold text-slate-700">{lane.label}</h3>
        </div>
        <span className="shrink-0 rounded-lg bg-white px-2 py-0.5 text-xs font-bold text-slate-500 shadow-sm">
          {cards.length}
        </span>
      </div>
      <div className="flex min-h-0 flex-1 flex-col gap-2 overflow-y-auto px-2 pb-2">
        {cards.map((card) => (
          <DraggableCard
            key={card.id}
            card={card}
            allCards={allCards}
            selected={selectedIds.has(card.id)}
            celebrating={celebrating}
            onToggleSelect={onToggleSelect}
            onDelete={onDelete}
          />
        ))}
      </div>
    </div>
  );
}

function DraggableCard({
  card,
  allCards,
  selected,
  celebrating,
  onToggleSelect,
  onDelete,
}: {
  card: TaskCard;
  allCards: TaskCard[];
  selected: boolean;
  celebrating: boolean;
  onToggleSelect: (id: string) => void;
  onDelete: (card: TaskCard) => void;
}) {
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id: card.id,
  });
  const style = {
    transform: CSS.Translate.toString(transform),
    opacity: isDragging ? 0.4 : 1,
  };
  return (
    <div ref={setNodeRef} style={style} {...listeners} {...attributes}>
      <CardBody
        card={card}
        allCards={allCards}
        selected={selected}
        celebrating={celebrating}
        onToggleSelect={onToggleSelect}
        onDelete={onDelete}
      />
    </div>
  );
}

function CardBody({
  card,
  allCards = [],
  compact = false,
  selected = false,
  celebrating = false,
  onToggleSelect,
  onDelete,
}: {
  card: TaskCard;
  allCards?: TaskCard[];
  compact?: boolean;
  selected?: boolean;
  celebrating?: boolean;
  onToggleSelect?: (id: string) => void;
  onDelete?: (card: TaskCard) => void;
}) {
  const working = WORKING_COLUMNS.has(card.column);
  const kind = card.kind ?? (card.parent_id ? "work" : "epic");
  const parent = card.parent_id ? allCards.find((c) => c.id === card.parent_id) : undefined;
  const children =
    kind === "epic"
      ? allCards
          .filter((c) => c.parent_id === card.id)
          .sort((a, b) => a.created_at.localeCompare(b.created_at))
      : [];
  const plannedTitles =
    kind === "epic" && !children.length
      ? card.subtasks.filter((t) => t.trim().length > 0)
      : [];
  const agents = card.agents.length ? card.agents : working ? ["desenvolvedor"] : [];
  const visibleTags = card.tags.filter((t) => t !== "epic" && t !== "work").slice(0, 2);

  return (
    <div
      className={`group board-card-enter rounded-xl border bg-white shadow-[var(--shadow-card)] transition hover:-translate-y-0.5 hover:shadow-md ${
        compact ? "p-2" : "p-3"
      } ${
        selected
          ? "border-rose-300 ring-2 ring-rose-300"
          : kind === "epic"
            ? "border-indigo-200/90 hover:border-indigo-300"
            : "border-slate-200/80 hover:border-blue-200"
      }`}
    >
      <div className="mb-1.5 flex flex-wrap items-center gap-1">
        {onToggleSelect ? (
          <input
            type="checkbox"
            checked={selected}
            onChange={() => onToggleSelect(card.id)}
            onPointerDown={(e) => e.stopPropagation()}
            title="Select for bulk delete"
            className="h-3.5 w-3.5 accent-rose-600"
          />
        ) : null}
        <Badge tone={kind === "epic" ? "accent" : "neutral"}>
          {kind === "epic" ? "Epic" : "Work"}
        </Badge>
        <Badge tone={priorityTone(card.priority)}>
          {PRIORITY_LABEL[card.priority] ?? card.priority}
        </Badge>
        <Badge tone="info">{COLUMN_SHORT_LABELS[card.column]}</Badge>
        {onDelete ? (
          <button
            type="button"
            onClick={() => onDelete(card)}
            onPointerDown={(e) => e.stopPropagation()}
            title="Delete card"
            className="ml-auto rounded-md px-1 text-sm leading-none text-slate-300 opacity-0 transition hover:bg-rose-50 hover:text-rose-600 group-hover:opacity-100"
          >
            ✕
          </button>
        ) : null}
      </div>
      <Link
        to={`/cards/${card.id}`}
        className={`block font-bold leading-snug text-slate-900 hover:text-blue-600 ${
          compact ? "line-clamp-2 text-xs" : "text-sm"
        }`}
        onPointerDown={(e) => e.stopPropagation()}
      >
        {card.title}
      </Link>
      {parent ? (
        <p className="mt-1 text-[11px] font-semibold text-indigo-600/80">↳ {parent.title}</p>
      ) : null}
      {!compact ? (
        <p className="mt-2 line-clamp-2 text-xs leading-relaxed text-slate-500">
          {card.description}
        </p>
      ) : null}

      {agents.length ? (
        <div className="mt-2.5 flex items-center justify-between gap-2">
          <div
            className={`flex flex-wrap items-center ${
              working ? "gap-2 agent-row-spreading" : "gap-1.5"
            }`}
          >
            {agents.slice(0, 4).map((id, i) => (
              <AgentAvatar
                key={id}
                id={id}
                working={working}
                celebrating={celebrating}
                motionDelayMs={i * (working ? 220 : 90)}
                size="sm"
              />
            ))}
          </div>
          {working ? (
            <span className="shrink-0 text-[10px] font-bold uppercase tracking-wide text-blue-600">
              Building
            </span>
          ) : null}
        </div>
      ) : null}

      {!compact && (children.length || plannedTitles.length) ? (
        <div className="mt-2.5 space-y-1.5 border-t border-dashed border-slate-200/90 pt-2">
          <p className="text-[10px] font-bold uppercase tracking-wide text-slate-400">
            {children.length
              ? `Work · ${children.length}`
              : `Planned · ${plannedTitles.length}`}
          </p>
          <div className="flex flex-col gap-1.5">
            {children.length
              ? children.slice(0, 5).map((child, i) => {
                  const childWorking = WORKING_COLUMNS.has(child.column);
                  const childAgent = child.agents[0];
                  return (
                    <Link
                      key={child.id}
                      to={`/cards/${child.id}`}
                      onPointerDown={(e) => e.stopPropagation()}
                      className={`board-subcard flex items-center gap-1.5 rounded-lg border bg-slate-50/90 px-2 py-1.5 transition hover:border-blue-200 hover:bg-white ${
                        childWorking
                          ? "border-blue-200 shadow-sm"
                          : child.column === "concluido" || child.column === "pronto_entrega"
                            ? "border-emerald-200"
                            : "border-slate-200/80"
                      }`}
                      style={{ animationDelay: `${i * 120}ms` }}
                    >
                      {childAgent ? (
                        <AgentAvatar
                          id={childAgent}
                          working={childWorking}
                          motionDelayMs={i * 180}
                          size="sm"
                        />
                      ) : (
                        <span className="inline-flex h-6 w-6 items-center justify-center rounded-full bg-slate-200 text-[10px] font-bold text-slate-500">
                          {i + 1}
                        </span>
                      )}
                      <span className="min-w-0 flex-1 truncate text-[11px] font-semibold text-slate-700">
                        {child.title}
                      </span>
                      <Badge tone={childWorking ? "info" : "neutral"}>
                        {COLUMN_SHORT_LABELS[child.column]}
                      </Badge>
                    </Link>
                  );
                })
              : plannedTitles.slice(0, 5).map((title, i) => (
                  <div
                    key={`${card.id}-planned-${i}`}
                    className="board-subcard flex items-center gap-1.5 rounded-lg border border-indigo-100 bg-indigo-50/60 px-2 py-1.5"
                    style={{ animationDelay: `${i * 120}ms` }}
                  >
                    <span className="inline-flex h-6 w-6 items-center justify-center rounded-full bg-indigo-100 text-[10px] font-bold text-indigo-600">
                      {i + 1}
                    </span>
                    <span className="min-w-0 flex-1 truncate text-[11px] font-semibold text-slate-700">
                      {title}
                    </span>
                    <Badge tone="accent">Planned</Badge>
                  </div>
                ))}
            {(children.length > 5 || plannedTitles.length > 5) ? (
              <p className="px-1 text-[10px] font-semibold text-slate-400">
                +
                {(children.length || plannedTitles.length) - 5} more work items
              </p>
            ) : null}
          </div>
        </div>
      ) : null}

      <div className="mt-2 flex flex-wrap items-center gap-1">
        {visibleTags.map((tag) => (
          <Badge key={tag} tone="neutral">
            {tag}
          </Badge>
        ))}
        {card.preview_url ? (
          <span className="inline-flex items-center rounded-md bg-emerald-50 px-1.5 py-0.5 text-[10px] font-bold text-emerald-700">
            Live app
          </span>
        ) : null}
        {card.block_reason ? <Badge tone="danger">Blocked</Badge> : null}
      </div>
    </div>
  );
}

function LiveAppDock({
  apps,
  selectedId,
  onSelect,
}: {
  apps: TaskCard[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}) {
  const selected = apps.find((c) => c.id === selectedId) ?? apps[0] ?? null;
  if (!selected?.preview_url) return null;

  return (
    <section className="flex min-h-0 flex-[0_0_38%] flex-col overflow-hidden rounded-xl border border-emerald-200 bg-white shadow-[var(--shadow-card)]">
      <div className="flex shrink-0 flex-wrap items-center justify-between gap-2 border-b border-emerald-100 bg-emerald-50/80 px-3 py-2">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className="relative flex h-2 w-2">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-500" />
            </span>
            <h2 className="truncate text-sm font-extrabold text-emerald-900">
              App running — {selected.title}
            </h2>
          </div>
          <p className="mt-0.5 truncate text-[11px] text-emerald-700/80">{selected.preview_url}</p>
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          {apps.map((app) => (
            <button
              key={app.id}
              type="button"
              onClick={() => onSelect(app.id)}
              className={`rounded-lg px-2 py-1 text-[11px] font-bold transition ${
                app.id === selected.id
                  ? "bg-emerald-600 text-white"
                  : "bg-white text-emerald-800 ring-1 ring-emerald-200 hover:bg-emerald-100"
              }`}
            >
              {app.title.length > 18 ? `${app.title.slice(0, 18)}…` : app.title}
            </button>
          ))}
          <a
            href={selected.preview_url}
            target="_blank"
            rel="noreferrer"
            className="rounded-lg bg-white px-2 py-1 text-[11px] font-bold text-emerald-800 ring-1 ring-emerald-200 hover:bg-emerald-100"
          >
            Open ↗
          </a>
        </div>
      </div>
      <div className="relative min-h-0 flex-1 bg-slate-100">
        <iframe
          key={selected.preview_url}
          title={`Live preview — ${selected.title}`}
          src={selected.preview_url}
          className="absolute inset-0 h-full w-full border-0 bg-white"
          sandbox="allow-scripts allow-same-origin allow-forms allow-popups"
        />
      </div>
    </section>
  );
}

export function KanbanPage() {
  const { cards, setCards, refreshAll, setToast, agents, missions } = useAppStore();
  const [activeId, setActiveId] = useState<string | null>(null);
  const [filter, setFilter] = useState("");
  const [modalOpen, setModalOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [draftSubtasks, setDraftSubtasks] = useState<string[]>([]);
  const [selectedLiveId, setSelectedLiveId] = useState<string | null>(null);
  const [resetOpen, setResetOpen] = useState(false);
  const [resetting, setResetting] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [deleteTarget, setDeleteTarget] = useState<TaskCard[] | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [swarmBusy, setSwarmBusy] = useState<"start" | "stop" | null>(null);
  const [celebrating, setCelebrating] = useState(false);
  const [chatOpen, setChatOpen] = useState(true);
  const [a2aMessages, setA2aMessages] = useState<AgentBoardMessage[]>([]);
  const [chatFilterCardId, setChatFilterCardId] = useState<string | null>(null);
  const [chatLoading, setChatLoading] = useState(false);
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 8 } }));

  useEffect(() => {
    if (!celebrating) return;
    const timer = window.setTimeout(() => setCelebrating(false), 2800);
    return () => window.clearTimeout(timer);
  }, [celebrating]);

  const activeMission = useMemo(() => {
    const running = missions.find((m) => RUNNING_SWARM_STATUSES.includes(m.status));
    if (running) return running;
    const buildingCardIds = new Set(
      cards.filter((c) => WORKING_COLUMNS.has(c.column)).map((c) => c.id),
    );
    return (
      missions.find((m) => buildingCardIds.has(m.card_id)) ??
      missions.find((m) =>
        ["awaiting_delivery_approval", "blocked", "stopped", "failed"].includes(m.status),
      ) ??
      missions[0] ??
      null
    );
  }, [missions, cards]);

  const swarmTargetCard = useMemo(() => {
    if (activeMission) {
      const linked = cards.find((c) => c.id === activeMission.card_id);
      if (linked) return linked;
    }
    return (
      cards.find(
        (c) =>
          (c.kind ?? (c.parent_id ? "work" : "epic")) === "epic" &&
          SWARM_CARD_COLUMNS.has(c.column),
      ) ?? null
    );
  }, [activeMission, cards]);

  const canStopSwarm = activeMission
    ? RUNNING_SWARM_STATUSES.includes(activeMission.status)
    : Boolean(
        swarmTargetCard &&
          ["pronto_enxame", "em_execucao", "em_revisao", "em_testes"].includes(
            swarmTargetCard.column,
          ),
      );
  const canStartSwarm = activeMission
    ? !RUNNING_SWARM_STATUSES.includes(activeMission.status)
    : Boolean(swarmTargetCard);

  const filtered = useMemo(() => {
    const q = filter.trim().toLowerCase();
    if (!q) return cards;
    return cards.filter(
      (c) =>
        c.title.toLowerCase().includes(q) ||
        c.description.toLowerCase().includes(q) ||
        c.tags.some((t) => t.toLowerCase().includes(q)),
    );
  }, [cards, filter]);

  const byLane = useMemo(() => {
    const map = Object.fromEntries(BOARD_LANES.map((l) => [l.id, [] as TaskCard[]])) as Record<
      BoardLaneId,
      TaskCard[]
    >;
    for (const card of filtered) {
      // Nest work items under their epic — do not also show them as top-level cards.
      if (card.parent_id) continue;
      map[laneForColumn(card.column).id].push(card);
    }
    return map;
  }, [filtered]);

  const liveApps = useMemo(() => {
    const withPreview = cards.filter((c) => Boolean(c.preview_url));
    const epics = withPreview.filter((c) => (c.kind ?? "epic") === "epic" || !c.parent_id);
    return epics.length ? epics : withPreview;
  }, [cards]);

  const activeCard = cards.find((c) => c.id === activeId) ?? null;
  const building = cards.filter((c) => WORKING_COLUMNS.has(c.column)).length;
  const isBusy = building > 0;
  const boardId = cards[0]?.board_id ?? null;

  async function refreshA2aMessages() {
    if (!boardId) {
      setA2aMessages([]);
      return;
    }
    setChatLoading(true);
    try {
      const msgs = await api.boardChat.messages({ board_id: boardId, limit: 120 });
      setA2aMessages(msgs);
    } catch {
      /* keep last messages on transient errors */
    } finally {
      setChatLoading(false);
    }
  }

  useEffect(() => {
    void refreshAll();
    const intervalMs = isBusy ? 900 : 4000;
    const id = window.setInterval(() => void refreshAll(), intervalMs);
    return () => window.clearInterval(id);
  }, [refreshAll, isBusy]);

  useEffect(() => {
    void refreshA2aMessages();
    const intervalMs = isBusy ? 900 : 4000;
    const id = window.setInterval(() => void refreshA2aMessages(), intervalMs);
    return () => window.clearInterval(id);
  }, [boardId, isBusy]);

  useEffect(() => {
    if (!liveApps.length) {
      setSelectedLiveId(null);
      return;
    }
    if (!selectedLiveId || !liveApps.some((c) => c.id === selectedLiveId)) {
      setSelectedLiveId(liveApps[0].id);
    }
  }, [liveApps, selectedLiveId]);

  async function onDragEnd(event: DragEndEvent) {
    setActiveId(null);
    const cardId = String(event.active.id);
    const laneId = event.over?.id as BoardLaneId | undefined;
    const lane = BOARD_LANES.find((l) => l.id === laneId);
    if (!lane) return;

    const card = cards.find((c) => c.id === cardId);
    if (!card) return;
    if (laneForColumn(card.column).id === lane.id) return;

    const target = resolveLaneDropTarget(card.column, lane, ALLOWED);
    if (target === card.column) return;

    const previous = cards;
    setCards(cards.map((c) => (c.id === cardId ? { ...c, column: target } : c)));
    try {
      const reason = target === "bloqueado" ? "Moved to Parked from board" : undefined;
      const updated = await api.cards.transition(cardId, target, reason);
      setCards(previous.map((c) => (c.id === cardId ? updated : c)));
      setToast(`Moved to ${lane.label} (${COLUMN_LABELS[target]})`);
      await refreshAll();
    } catch (err) {
      setCards(previous);
      setToast(err instanceof Error ? err.message : "Invalid transition");
    }
  }

  function closeCreateModal() {
    setModalOpen(false);
    setCreating(false);
  }

  async function createCard() {
    if (!title.trim()) return;
    setCreating(true);
    try {
      await api.cards.create({
        title: title.trim(),
        description:
          description.trim() ||
          `${title.trim()}\n\nBuild a complete small software product and deploy a live preview.`,
        subtasks: draftSubtasks,
      });
      setTitle("");
      setDescription("");
      setDraftSubtasks([]);
      setModalOpen(false);
      setToast("Task created — agents started triage");
      void refreshAll();
    } catch (err) {
      setToast(err instanceof Error ? err.message : "Failed to create task");
    } finally {
      setCreating(false);
    }
  }

  function useTemplate(template: (typeof SOFTWARE_TEMPLATES)[number]) {
    setTitle(template.title);
    setDescription(template.description);
    setDraftSubtasks(template.subtasks ?? []);
    setModalOpen(true);
  }

  async function resetBoard(reseedDemo: boolean) {
    setResetting(true);
    try {
      const res = await api.cards.reset(reseedDemo);
      setSelectedLiveId(null);
      setResetOpen(false);
      setToast(
        `Board reset — ${res.runtimes_stopped} app(s) stopped${
          reseedDemo ? " · demo regenerated" : ""
        }`,
      );
      await refreshAll();
    } catch (err) {
      setToast(err instanceof Error ? err.message : "Failed to reset board");
    } finally {
      setResetting(false);
    }
  }

  function toggleSelect(id: string) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function confirmDelete() {
    if (!deleteTarget?.length) return;
    setDeleting(true);
    const ids = deleteTarget.map((c) => c.id);
    try {
      const res =
        ids.length === 1 ? await api.cards.remove(ids[0]) : await api.cards.bulkRemove(ids);
      const removed = new Set(res.deleted);
      setCards(cards.filter((c) => !removed.has(c.id)));
      setSelectedIds((prev) => {
        const next = new Set(prev);
        for (const id of removed) next.delete(id);
        return next;
      });
      setDeleteTarget(null);
      setToast(`Deleted ${res.deleted.length} card(s)`);
      await refreshAll();
    } catch (err) {
      setToast(err instanceof Error ? err.message : "Failed to delete card(s)");
    } finally {
      setDeleting(false);
    }
  }

  async function runSwarmAction(action: "start" | "stop") {
    if (!swarmTargetCard && !activeMission) return;
    if (action === "stop" && !canStopSwarm) return;
    if (action === "start" && !canStartSwarm) return;

    setSwarmBusy(action);
    try {
      if (action === "stop") {
        if (swarmTargetCard) await api.swarm.stopCard(swarmTargetCard.id);
        else if (activeMission) await api.swarm.stop(activeMission.id);
        setToast("Enxame parado");
      } else {
        if (swarmTargetCard) await api.swarm.startCard(swarmTargetCard.id);
        else if (activeMission) await api.swarm.start(activeMission.id);
        setCelebrating(true);
        playRobotCheer();
        setToast("Enxame iniciado — robôs em festa!");
      }
      await refreshAll();
    } catch (err) {
      setToast(
        err instanceof Error
          ? err.message
          : action === "stop"
            ? "Falha ao parar o enxame"
            : "Falha ao iniciar o enxame",
      );
    } finally {
      setSwarmBusy(null);
    }
  }

  const coreAgents = agents.length
    ? AGENT_ROBOTS.filter((a) => agents.some((x) => x.id === a.id))
    : AGENT_ROBOTS;

  return (
    <div className="flex h-full min-h-0 flex-col gap-2 overflow-hidden">
      <header className="flex shrink-0 flex-wrap items-center justify-between gap-2">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-extrabold tracking-tight text-slate-900">Board</h1>
            <Badge tone="accent">6 lanes</Badge>
            {liveApps.length ? <Badge tone="success">{liveApps.length} live</Badge> : null}
          </div>
          <p className="mt-0.5 hidden text-xs text-slate-500 sm:block">
            Similar stages merged. Chip on each card shows the detailed status.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          <div className="rounded-lg border border-slate-200 bg-white px-2 py-1 text-[11px] font-semibold text-slate-600 shadow-sm">
            {building} building · {liveApps.length} live
          </div>
          {swarmTargetCard || activeMission ? (
            <div className="flex items-center gap-1">
              <Badge tone={canStopSwarm ? "success" : "neutral"}>
                Swarm {activeMission?.status ?? swarmTargetCard?.column ?? "ready"}
              </Badge>
              <Button
                variant="soft"
                className="!px-2.5 !py-1.5 text-xs"
                disabled={!canStartSwarm || swarmBusy !== null}
                onClick={() => void runSwarmAction("start")}
                title={`Start swarm · ${activeMission?.objective ?? swarmTargetCard?.title ?? ""}`}
              >
                {swarmBusy === "start" ? "..." : "Start"}
              </Button>
              <Button
                variant="danger"
                className="!px-2.5 !py-1.5 text-xs"
                disabled={!canStopSwarm || swarmBusy !== null}
                onClick={() => void runSwarmAction("stop")}
                title={`Stop swarm · ${activeMission?.objective ?? swarmTargetCard?.title ?? ""}`}
              >
                {swarmBusy === "stop" ? "..." : "Stop"}
              </Button>
            </div>
          ) : (
            <div className="flex items-center gap-1">
              <Button
                variant="soft"
                className="!px-2.5 !py-1.5 text-xs"
                disabled
                title="Nenhum card elegível para o enxame"
              >
                Start
              </Button>
              <Button
                variant="danger"
                className="!px-2.5 !py-1.5 text-xs"
                disabled
                title="Nenhuma missão ativa"
              >
                Stop
              </Button>
            </div>
          )}
          <input
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder="Search..."
            className="w-32 rounded-lg border border-slate-200 bg-white px-2 py-1.5 text-xs outline-none ring-blue-500 focus:ring-2 sm:w-40"
          />
          {selectedIds.size ? (
            <Button
              variant="danger"
              onClick={() =>
                setDeleteTarget(cards.filter((c) => selectedIds.has(c.id)))
              }
            >
              Delete selected ({selectedIds.size})
            </Button>
          ) : null}
          <Button variant="danger" onClick={() => setResetOpen(true)}>
            Reset
          </Button>
          <Button
            onClick={() => {
              setDraftSubtasks([]);
              setModalOpen(true);
            }}
          >
            + Create
          </Button>
        </div>
      </header>

      <div className="flex shrink-0 flex-wrap items-center gap-2">
        <div className="flex max-w-full gap-1.5 overflow-x-auto">
          {coreAgents.slice(0, 6).map((agent, i) => (
            <div
              key={agent.id}
              className="flex shrink-0 items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-2 py-1"
              title={agent.blurb}
            >
              <AgentAvatar
                id={agent.id}
                size="sm"
                celebrating={celebrating}
                motionDelayMs={i * 80}
              />
              <span className="text-[10px] font-bold text-slate-700">{agent.name}</span>
            </div>
          ))}
          <Link
            to="/agents"
            className="shrink-0 self-center text-[10px] font-bold text-blue-600 hover:underline"
          >
            +{Math.max(0, (agents.length || 260) - 6)} robots
          </Link>
        </div>
        <div className="flex max-w-full flex-1 gap-1 overflow-x-auto">
          {SOFTWARE_TEMPLATES.map((template) => (
            <button
              key={template.title}
              onClick={() => useTemplate(template)}
              className="shrink-0 rounded-full border border-slate-200 bg-white px-2 py-0.5 text-[10px] font-semibold text-slate-600 shadow-sm transition hover:border-blue-300 hover:text-blue-700"
            >
              {template.title}
            </button>
          ))}
        </div>
      </div>

      <div className="flex min-h-0 flex-1 gap-2 overflow-hidden">
        <DndContext
          sensors={sensors}
          onDragStart={(e: DragStartEvent) => setActiveId(String(e.active.id))}
          onDragEnd={(e) => void onDragEnd(e)}
        >
          <div
            className="grid min-h-0 min-w-0 flex-1 gap-2.5 overflow-hidden"
            style={{
              gridTemplateColumns: `repeat(${BOARD_LANES.length}, minmax(0, 1fr))`,
            }}
          >
            {BOARD_LANES.map((lane) => (
              <DroppableLane
                key={lane.id}
                lane={lane}
                cards={byLane[lane.id]}
                allCards={cards}
                selectedIds={selectedIds}
                celebrating={celebrating}
                onToggleSelect={toggleSelect}
                onDelete={(card) => setDeleteTarget([card])}
              />
            ))}
          </div>
          <DragOverlay>
            {activeCard ? (
              <div className="w-[240px] rotate-1 scale-[1.03]">
                <CardBody card={activeCard} allCards={cards} />
              </div>
            ) : null}
          </DragOverlay>
        </DndContext>

        <BoardChatPanel
          open={chatOpen}
          onToggle={() => setChatOpen((v) => !v)}
          messages={a2aMessages}
          cards={cards}
          filterCardId={chatFilterCardId}
          onFilterCardId={setChatFilterCardId}
          loading={chatLoading}
        />
      </div>

      {liveApps.length ? (
        <LiveAppDock apps={liveApps} selectedId={selectedLiveId} onSelect={setSelectedLiveId} />
      ) : (
        <div className="shrink-0 rounded-xl border border-dashed border-slate-300 bg-white/70 px-3 py-2 text-center text-[11px] text-slate-500">
          When an epic finishes, the developed app appears here — running live.
        </div>
      )}

      {deleteTarget?.length ? (
        <div className="fixed inset-0 z-50 flex items-end justify-center bg-slate-900/40 p-4 sm:items-center">
          <div className="w-full max-w-md rounded-2xl bg-white p-5 shadow-2xl">
            <div className="flex items-start justify-between gap-3">
              <div>
                <h2 className="text-xl font-extrabold tracking-tight text-rose-700">
                  {deleteTarget.length === 1
                    ? "Delete card"
                    : `Delete ${deleteTarget.length} cards`}
                </h2>
                <p className="mt-1 text-sm text-slate-500">
                  {deleteTarget.length === 1
                    ? `"${deleteTarget[0].title}" and its generated app will be removed.`
                    : "The selected cards and their generated apps will be removed."}{" "}
                  Child work cards are deleted too. This cannot be undone.
                </p>
              </div>
              <button
                onClick={() => setDeleteTarget(null)}
                className="rounded-lg px-2 py-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
              >
                ✕
              </button>
            </div>
            {deleteTarget.length > 1 ? (
              <ul className="mt-3 max-h-40 space-y-1 overflow-y-auto rounded-xl bg-slate-50 p-3 text-sm text-slate-700">
                {deleteTarget.map((c) => (
                  <li key={c.id} className="truncate">
                    • {c.title}
                  </li>
                ))}
              </ul>
            ) : null}
            <div className="mt-5 flex justify-end gap-2">
              <Button variant="ghost" disabled={deleting} onClick={() => setDeleteTarget(null)}>
                Cancel
              </Button>
              <Button variant="danger" disabled={deleting} onClick={() => void confirmDelete()}>
                {deleting ? "Deleting..." : "Delete"}
              </Button>
            </div>
          </div>
        </div>
      ) : null}

      {resetOpen ? (
        <div className="fixed inset-0 z-50 flex items-end justify-center bg-slate-900/40 p-4 sm:items-center">
          <div className="w-full max-w-md rounded-2xl bg-white p-5 shadow-2xl">
            <div className="flex items-start justify-between gap-3">
              <div>
                <h2 className="text-xl font-extrabold tracking-tight text-rose-700">
                  Reset board
                </h2>
                <p className="mt-1 text-sm text-slate-500">
                  Deletes all cards and stops every generated app. This cannot be undone.
                </p>
              </div>
              <button
                onClick={() => setResetOpen(false)}
                className="rounded-lg px-2 py-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
              >
                ✕
              </button>
            </div>
            <div className="mt-5 flex flex-col gap-2">
              <Button
                variant="danger"
                disabled={resetting}
                onClick={() => void resetBoard(true)}
              >
                {resetting ? "Resetting..." : "Delete all & regenerate demo"}
              </Button>
              <Button
                variant="ghost"
                disabled={resetting}
                onClick={() => void resetBoard(false)}
              >
                {resetting ? "Resetting..." : "Delete all (empty board)"}
              </Button>
              <Button variant="ghost" disabled={resetting} onClick={() => setResetOpen(false)}>
                Cancel
              </Button>
            </div>
          </div>
        </div>
      ) : null}

      {modalOpen ? (
        <div className="fixed inset-0 z-50 flex items-end justify-center bg-slate-900/40 p-4 sm:items-center">
          <div className="w-full max-w-lg rounded-2xl bg-white p-5 shadow-2xl">
            <div className="flex items-start justify-between gap-3">
              <div>
                <h2 className="text-xl font-extrabold tracking-tight">Create software task</h2>
                <p className="mt-1 text-sm text-slate-500">
                  Describe a small complete product. Agents will triage, build, and deploy it.
                </p>
              </div>
              <button
                onClick={closeCreateModal}
                className="rounded-lg px-2 py-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
              >
                ✕
              </button>
            </div>
            <div className="mt-4 space-y-3">
              <input
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Task title"
                className="w-full rounded-xl border border-slate-200 px-3 py-2.5 text-sm outline-none ring-blue-500 focus:ring-2"
              />
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                rows={5}
                placeholder="Describe the mini-app to build and deploy..."
                className="w-full resize-none rounded-xl border border-slate-200 px-3 py-2.5 text-sm outline-none ring-blue-500 focus:ring-2"
              />
            </div>
            <div className="mt-5 flex justify-end gap-2">
              <Button variant="ghost" onClick={closeCreateModal}>
                Cancel
              </Button>
              <Button onClick={() => void createCard()} disabled={creating || !title.trim()}>
                {creating ? "Creating..." : "Create & start agents"}
              </Button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
