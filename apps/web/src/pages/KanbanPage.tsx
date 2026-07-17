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
import { Badge, Button, PRIORITY_LABEL, priorityTone } from "../components/ui";
import { useAppStore } from "../store";
import {
  COLUMN_COLORS,
  COLUMN_LABELS,
  KANBAN_COLUMNS,
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

function AgentAvatar({
  id,
  working = false,
  size = "md",
}: {
  id: string;
  working?: boolean;
  size?: "sm" | "md";
}) {
  const agent = agentVisual(id);
  const dim = size === "sm" ? "h-7 w-7 text-sm" : "h-9 w-9 text-base";
  return (
    <div
      title={`${agent.name} · ${agent.role}`}
      className={`${dim} ${working ? "agent-working" : "agent-float"} inline-flex items-center justify-center rounded-full border-2 border-white text-center shadow-sm`}
      style={{ background: `${agent.color}22`, color: agent.color }}
    >
      <span aria-hidden>{agent.emoji}</span>
    </div>
  );
}

function DroppableColumn({
  id,
  cards,
  allCards,
}: {
  id: KanbanColumn;
  cards: TaskCard[];
  allCards: TaskCard[];
}) {
  const { setNodeRef, isOver } = useDroppable({ id });
  return (
    <div
      ref={setNodeRef}
      className={`flex w-[300px] shrink-0 flex-col rounded-2xl bg-[var(--board)]/90 transition ${
        isOver ? "ring-2 ring-blue-500 ring-offset-2" : ""
      }`}
    >
      <div className="flex items-center justify-between gap-2 px-3 py-3">
        <div className="flex items-center gap-2">
          <span className="h-2.5 w-2.5 rounded-full" style={{ background: COLUMN_COLORS[id] }} />
          <h3 className="text-sm font-bold text-slate-700">{COLUMN_LABELS[id]}</h3>
        </div>
        <span className="rounded-lg bg-white px-2 py-0.5 text-xs font-bold text-slate-500 shadow-sm">
          {cards.length}
        </span>
      </div>
      <div className="flex flex-1 flex-col gap-2.5 px-2.5 pb-3">
        {cards.map((card) => (
          <DraggableCard key={card.id} card={card} allCards={allCards} />
        ))}
      </div>
    </div>
  );
}

function DraggableCard({ card, allCards }: { card: TaskCard; allCards: TaskCard[] }) {
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id: card.id,
  });
  const style = {
    transform: CSS.Translate.toString(transform),
    opacity: isDragging ? 0.4 : 1,
  };
  return (
    <div ref={setNodeRef} style={style} {...listeners} {...attributes}>
      <CardBody card={card} allCards={allCards} />
    </div>
  );
}

function CardBody({ card, allCards = [] }: { card: TaskCard; allCards?: TaskCard[] }) {
  const working = WORKING_COLUMNS.has(card.column);
  const kind = card.kind ?? (card.parent_id ? "work" : "epic");
  const parent = card.parent_id ? allCards.find((c) => c.id === card.parent_id) : undefined;
  const agents = card.agents.length ? card.agents : working ? ["desenvolvedor"] : [];
  const visibleTags = card.tags.filter((t) => t !== "epic" && t !== "work").slice(0, 2);

  return (
    <div
      className={`group rounded-xl border bg-white p-3 shadow-[var(--shadow-card)] transition hover:-translate-y-0.5 hover:shadow-md ${
        kind === "epic"
          ? "border-indigo-200/90 hover:border-indigo-300"
          : "border-slate-200/80 hover:border-blue-200"
      }`}
    >
      <div className="mb-1.5 flex flex-wrap items-center gap-1.5">
        <Badge tone={kind === "epic" ? "accent" : "neutral"}>{kind === "epic" ? "Epic" : "Work"}</Badge>
        <Badge tone={priorityTone(card.priority)}>
          {PRIORITY_LABEL[card.priority] ?? card.priority}
        </Badge>
      </div>
      <div className="flex items-start justify-between gap-2">
        <Link
          to={`/cards/${card.id}`}
          className="text-sm font-bold leading-snug text-slate-900 hover:text-blue-600"
          onPointerDown={(e) => e.stopPropagation()}
        >
          {card.title}
        </Link>
      </div>
      {parent ? (
        <p className="mt-1 text-[11px] font-semibold text-indigo-600/80">↳ {parent.title}</p>
      ) : null}
      <p className="mt-2 line-clamp-2 text-xs leading-relaxed text-slate-500">{card.description}</p>

      {agents.length ? (
        <div className="mt-3 flex items-center justify-between gap-2">
          <div className="flex -space-x-1.5">
            {agents.slice(0, 4).map((id) => (
              <AgentAvatar key={id} id={id} working={working} size="sm" />
            ))}
          </div>
          {working ? (
            <span className="text-[10px] font-bold uppercase tracking-wide text-blue-600">
              Agents building
            </span>
          ) : null}
        </div>
      ) : null}

      <div className="mt-3 flex flex-wrap items-center gap-1.5">
        {visibleTags.map((tag) => (
          <Badge key={tag} tone="neutral">
            {tag}
          </Badge>
        ))}
        {card.preview_url ? (
          <a
            href={card.preview_url}
            target="_blank"
            rel="noreferrer"
            onPointerDown={(e) => e.stopPropagation()}
            className="inline-flex items-center rounded-lg bg-emerald-50 px-2 py-0.5 text-[11px] font-bold text-emerald-700 hover:bg-emerald-100"
          >
            Live app
          </a>
        ) : null}
        {card.block_reason ? <Badge tone="danger">Blocked</Badge> : null}
      </div>
    </div>
  );
}

export function KanbanPage() {
  const { cards, setCards, refreshAll, setToast, agents } = useAppStore();
  const [activeId, setActiveId] = useState<string | null>(null);
  const [filter, setFilter] = useState("");
  const [modalOpen, setModalOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 8 } }));

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

  const byColumn = useMemo(() => {
    const map = Object.fromEntries(KANBAN_COLUMNS.map((c) => [c, [] as TaskCard[]])) as Record<
      KanbanColumn,
      TaskCard[]
    >;
    for (const card of filtered) map[card.column].push(card);
    return map;
  }, [filtered]);

  const activeCard = cards.find((c) => c.id === activeId) ?? null;
  const building = cards.filter((c) => WORKING_COLUMNS.has(c.column)).length;
  const live = cards.filter((c) => c.preview_url || c.column === "concluido").length;
  const isBusy = building > 0;

  useEffect(() => {
    void refreshAll();
    const intervalMs = isBusy ? 2000 : 4000;
    const id = window.setInterval(() => void refreshAll(), intervalMs);
    return () => window.clearInterval(id);
  }, [refreshAll, isBusy]);

  async function onDragEnd(event: DragEndEvent) {
    setActiveId(null);
    const cardId = String(event.active.id);
    const target = event.over?.id as KanbanColumn | undefined;
    if (!target || !KANBAN_COLUMNS.includes(target)) return;
    const card = cards.find((c) => c.id === cardId);
    if (!card || card.column === target) return;

    const previous = cards;
    setCards(cards.map((c) => (c.id === cardId ? { ...c, column: target } : c)));
    try {
      const updated = await api.cards.transition(cardId, target);
      setCards(previous.map((c) => (c.id === cardId ? updated : c)));
      setToast(`Moved to ${COLUMN_LABELS[target]}`);
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
      });
      setTitle("");
      setDescription("");
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
    setModalOpen(true);
  }

  return (
    <div className="space-y-4">
      <header className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-3xl font-extrabold tracking-tight text-slate-900">Board</h1>
            <Badge tone="accent">Trello-style</Badge>
          </div>
          <p className="mt-1 text-sm text-slate-500">
            Create mini-software tasks. Robot agents build, review, test, and deploy live previews.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <div className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-600 shadow-sm">
            {building} building · {live} live
          </div>
          <input
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder="Search tasks..."
            className="w-44 rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm outline-none ring-blue-500 focus:ring-2 sm:w-56"
          />
          <Button onClick={() => setModalOpen(true)}>+ Create task</Button>
        </div>
      </header>

      <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-[var(--shadow-card)]">
        <div className="mb-3 flex items-center justify-between gap-3">
          <h2 className="text-sm font-bold text-slate-800">Core robot agents</h2>
          <Link to="/agents" className="text-xs font-bold text-blue-600 hover:underline">
            Browse {agents.length || 260}+ robots
          </Link>
        </div>
        <div className="flex gap-3 overflow-x-auto pb-1">
          {(agents.length
            ? AGENT_ROBOTS.filter((a) => agents.some((x) => x.id === a.id))
            : AGENT_ROBOTS
          ).map((agent) => (
            <div
              key={agent.id}
              className="min-w-[160px] rounded-xl border border-slate-100 bg-slate-50 px-3 py-3"
            >
              <div className="flex items-center gap-2">
                <AgentAvatar id={agent.id} />
                <div>
                  <div className="text-sm font-bold">{agent.name}</div>
                  <div className="text-[11px] font-semibold text-slate-500">{agent.role}</div>
                </div>
              </div>
              <p className="mt-2 text-[11px] leading-relaxed text-slate-500">{agent.blurb}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="flex flex-wrap gap-2">
        {SOFTWARE_TEMPLATES.map((template) => (
          <button
            key={template.title}
            onClick={() => useTemplate(template)}
            className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-600 shadow-sm transition hover:border-blue-300 hover:text-blue-700"
          >
            {template.title}
          </button>
        ))}
      </section>

      <DndContext
        sensors={sensors}
        onDragStart={(e: DragStartEvent) => setActiveId(String(e.active.id))}
        onDragEnd={(e) => void onDragEnd(e)}
      >
        <div className="flex gap-3 overflow-x-auto pb-6">
          {KANBAN_COLUMNS.map((column) => (
            <DroppableColumn
              key={column}
              id={column}
              cards={byColumn[column]}
              allCards={cards}
            />
          ))}
        </div>
        <DragOverlay>
          {activeCard ? (
            <div className="w-[280px] rotate-1 scale-[1.03]">
              <CardBody card={activeCard} allCards={cards} />
            </div>
          ) : null}
        </DragOverlay>
      </DndContext>

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
