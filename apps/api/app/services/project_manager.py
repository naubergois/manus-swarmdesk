"""Nova — robot gestor de projetos: narrates and steers the Kanban board."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.db import get_store
from app.models.contracts import AgentBoardMessage, TaskCard, new_id
from app.models.enums import KanbanColumn
from app.services import agent_bus as a2a

COLUMN_SPEECH: dict[str, str] = {
    KanbanColumn.ENTRADA.value: "entrada",
    KanbanColumn.TRIAGEM.value: "triagem",
    KanbanColumn.REFINAMENTO.value: "refinamento",
    KanbanColumn.AGUARDANDO_APROVACAO.value: "aguardando aprovação",
    KanbanColumn.PRONTO_ENXAME.value: "pronto para o enxame",
    KanbanColumn.EM_EXECUCAO.value: "em execução",
    KanbanColumn.EM_REVISAO.value: "em revisão",
    KanbanColumn.EM_TESTES.value: "em testes",
    KanbanColumn.AGUARDANDO_DECISAO.value: "aguardando decisão",
    KanbanColumn.PRONTO_ENTREGA.value: "pronto para entrega",
    KanbanColumn.BLOQUEADO.value: "bloqueado",
    KanbanColumn.CONCLUIDO.value: "concluído",
    KanbanColumn.CANCELADO.value: "cancelado",
}

LANE_GROUPS: list[tuple[str, str, set[str]]] = [
    ("inbox", "Inbox", {KanbanColumn.ENTRADA.value, KanbanColumn.TRIAGEM.value, KanbanColumn.REFINAMENTO.value}),
    (
        "approve",
        "Aprovar",
        {
            KanbanColumn.AGUARDANDO_APROVACAO.value,
            KanbanColumn.AGUARDANDO_DECISAO.value,
            KanbanColumn.PRONTO_ENXAME.value,
        },
    ),
    ("build", "Build", {KanbanColumn.EM_EXECUCAO.value, KanbanColumn.EM_REVISAO.value}),
    ("qa", "QA", {KanbanColumn.EM_TESTES.value, KanbanColumn.PRONTO_ENTREGA.value}),
    ("live", "Live", {KanbanColumn.CONCLUIDO.value}),
    ("parked", "Parked", {KanbanColumn.BLOQUEADO.value, KanbanColumn.CANCELADO.value}),
]

WORKING = {
    KanbanColumn.TRIAGEM.value,
    KanbanColumn.REFINAMENTO.value,
    KanbanColumn.EM_EXECUCAO.value,
    KanbanColumn.EM_REVISAO.value,
    KanbanColumn.EM_TESTES.value,
}


class BoardLaneCount(BaseModel):
    id: str
    label: str
    count: int


class BoardLiveState(BaseModel):
    """What Nova sees and says about the board right now."""

    board_id: str | None = None
    headline: str
    briefing: str
    mood: str = "idle"  # idle | busy | blocked | celebrate
    focus_card_id: str | None = None
    focus_card_title: str | None = None
    speaking_agent_id: str = "supervisor"
    lane_counts: list[BoardLaneCount] = Field(default_factory=list)
    building: int = 0
    blocked: int = 0
    awaiting_approval: int = 0
    live_apps: int = 0
    recent: list[AgentBoardMessage] = Field(default_factory=list)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


def _col_speech(column: str | KanbanColumn) -> str:
    key = column.value if isinstance(column, KanbanColumn) else column
    return COLUMN_SPEECH.get(key, key.replace("_", " "))


async def announce(
    card: TaskCard,
    content: str,
    *,
    message_type: str = "status",
    pipeline_step: str | None = None,
    to_agent: str | None = None,
) -> AgentBoardMessage:
    """Nova speaks to the board about something that just happened."""
    return await a2a.publish_a2a(
        card,
        "supervisor",
        content.strip(),
        to_agent=to_agent,
        message_type=message_type,
        pipeline_step=pipeline_step or "pm_announce",
    )


async def announce_transition(
    card: TaskCard,
    previous: KanbanColumn,
    target: KanbanColumn,
    *,
    actor: str = "human",
    reason: str = "",
) -> AgentBoardMessage | None:
    """Nova narrates a Kanban move so the board stays visually self-explanatory."""
    if previous == target:
        return None
    prev_s = _col_speech(previous)
    next_s = _col_speech(target)
    who = "você" if actor == "human" else actor
    extra = f" Motivo: {reason}." if reason and target == KanbanColumn.BLOQUEADO else ""
    if target == KanbanColumn.CONCLUIDO:
        text = f"🎉 «{card.title}» chegou em {next_s}. Entrega no ar!"
        msg_type = "result"
    elif target == KanbanColumn.BLOQUEADO:
        text = f"⛔ «{card.title}» ficou bloqueado (vinha de {prev_s}).{extra}"
        msg_type = "status"
    elif target == KanbanColumn.AGUARDANDO_APROVACAO:
        text = f"✋ «{card.title}» precisa da sua aprovação de escopo."
        msg_type = "question"
    else:
        text = f"📌 Movi «{card.title}»: {prev_s} → {next_s} (ação de {who})."
        msg_type = "status"
    return await announce(
        card,
        text,
        message_type=msg_type,
        pipeline_step="kanban_transition",
    )


async def announce_intake(card: TaskCard) -> AgentBoardMessage:
    return await announce(
        card,
        (
            f"Nova demanda no board: «{card.title}». "
            "Estou coordenando triagem → requisitos → plano. Acompanhe o cartão se mover."
        ),
        pipeline_step="receive_demand",
    )


def _lane_counts(cards: list[TaskCard]) -> list[BoardLaneCount]:
    tops = [c for c in cards if not c.parent_id]
    out: list[BoardLaneCount] = []
    for lane_id, label, cols in LANE_GROUPS:
        out.append(
            BoardLaneCount(
                id=lane_id,
                label=label,
                count=sum(1 for c in tops if c.column.value in cols),
            )
        )
    return out


def _pick_focus(
    cards: list[TaskCard],
    recent: list[AgentBoardMessage],
) -> tuple[str | None, str | None]:
    if recent:
        card_id = recent[0].card_id
        match = next((c for c in cards if c.id == card_id), None)
        if match:
            return match.id, match.title
    working = [c for c in cards if c.column.value in WORKING and not c.parent_id]
    if working:
        working.sort(key=lambda c: c.updated_at, reverse=True)
        return working[0].id, working[0].title
    pending = [
        c
        for c in cards
        if c.column == KanbanColumn.AGUARDANDO_APROVACAO and not c.parent_id
    ]
    if pending:
        return pending[0].id, pending[0].title
    return None, None


def _compose_headline(
    *,
    building: int,
    blocked: int,
    awaiting: int,
    live_apps: int,
    focus_title: str | None,
    latest: AgentBoardMessage | None,
) -> tuple[str, str]:
    """Returns (headline, mood)."""
    if blocked:
        return (
            f"Atenção: {blocked} item(ns) bloqueado(s)"
            + (f" — foco em «{focus_title}»" if focus_title else ""),
            "blocked",
        )
    if building:
        who = ""
        if latest and latest.from_agent_id != "supervisor":
            who = f" · {latest.from_agent_id} falando"
        return (
            f"Enxame ativo: {building} em trabalho"
            + (f" · «{focus_title}»" if focus_title else "")
            + who,
            "busy",
        )
    if awaiting:
        return (
            f"Preciso de você: {awaiting} aprovação(ões) pendente(s)"
            + (f" · «{focus_title}»" if focus_title else ""),
            "busy",
        )
    if live_apps:
        return (f"Board estável · {live_apps} app(s) no ar", "celebrate")
    if latest:
        return (latest.content[:140], "idle")
    return ("Board quieto — crie uma demanda ou dê Start no enxame.", "idle")


def _compose_briefing(
    lane_counts: list[BoardLaneCount],
    *,
    building: int,
    blocked: int,
    awaiting: int,
    live_apps: int,
    focus_title: str | None,
) -> str:
    parts = [f"{lc.label}: {lc.count}" for lc in lane_counts if lc.count]
    lanes = " · ".join(parts) if parts else "vazio"
    lines = [f"Sou a Nova, gestora do board. Situação: {lanes}."]
    if building:
        lines.append(f"{building} cartão(ões) em movimento agora.")
    if awaiting:
        lines.append(f"{awaiting} aguardando sua aprovação.")
    if blocked:
        lines.append(f"{blocked} bloqueado(s) — preciso destravar.")
    if live_apps:
        lines.append(f"{live_apps} app(s) live no dock.")
    if focus_title:
        lines.append(f"Foco atual: «{focus_title}».")
    return " ".join(lines)


async def get_live_state(
    *,
    board_id: str | None = None,
    limit: int = 24,
) -> BoardLiveState:
    store = get_store()
    rows = await store.list("task_cards", {"board_id": board_id} if board_id else None)
    cards = [TaskCard.model_validate(r) for r in rows]
    if not board_id and cards:
        board_id = cards[0].board_id

    recent = await a2a.list_board_messages(board_id=board_id, limit=limit)
    # list_board_messages returns newest-first; keep that order for "recent"
    focus_id, focus_title = _pick_focus(cards, recent)
    lane_counts = _lane_counts(cards)
    building = sum(1 for c in cards if c.column.value in WORKING)
    blocked = sum(1 for c in cards if c.column == KanbanColumn.BLOQUEADO)
    awaiting = sum(1 for c in cards if c.column == KanbanColumn.AGUARDANDO_APROVACAO)
    live_apps = sum(1 for c in cards if c.preview_url and not c.parent_id)

    latest = recent[0] if recent else None
    headline, mood = _compose_headline(
        building=building,
        blocked=blocked,
        awaiting=awaiting,
        live_apps=live_apps,
        focus_title=focus_title,
        latest=latest,
    )
    briefing = _compose_briefing(
        lane_counts,
        building=building,
        blocked=blocked,
        awaiting=awaiting,
        live_apps=live_apps,
        focus_title=focus_title,
    )
    speaking = latest.from_agent_id if latest else "supervisor"

    return BoardLiveState(
        board_id=board_id,
        headline=headline,
        briefing=briefing,
        mood=mood,
        focus_card_id=focus_id,
        focus_card_title=focus_title,
        speaking_agent_id=speaking,
        lane_counts=lane_counts,
        building=building,
        blocked=blocked,
        awaiting_approval=awaiting,
        live_apps=live_apps,
        recent=recent,
    )


async def seed_gestor_intro(board_id: str, card_id: str) -> AgentBoardMessage:
    """Optional seed line so a fresh board already hears Nova."""
    store = get_store()
    msg = AgentBoardMessage(
        id=new_id("a2a_"),
        board_id=board_id,
        card_id=card_id,
        from_agent_id="supervisor",
        content=(
            "Olá — sou a Nova, gestora deste board. "
            "Vou narrar cada movimento dos robôs e apontar o que precisa de você."
        ),
        message_type="status",
        pipeline_step="pm_intro",
    )
    await store.upsert("agent_messages", msg)
    return msg
