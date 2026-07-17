"""Internal A2A (agent-to-agent) message bus for board chat."""

from __future__ import annotations

from app.db import get_store
from app.models.contracts import AgentBoardMessage, TaskCard

AGENT_ALIASES: dict[str, str] = {
    "developer": "desenvolvedor",
    "reviewer": "revisor",
    "tester": "testador",
    "docs": "documentacao",
    "forge": "desenvolvedor",
    "lens": "revisor",
    "planner": "planejador",
    "architect": "arquiteto",
    "coordinator": "coordenador",
}


def normalize_agent_id(agent_id: str) -> str:
    key = agent_id.strip().lower()
    return AGENT_ALIASES.get(key, agent_id)


async def publish_a2a(
    card: TaskCard,
    from_agent: str,
    content: str,
    *,
    to_agent: str | None = None,
    message_type: str = "status",
    pipeline_step: str | None = None,
    correlation_id: str | None = None,
) -> AgentBoardMessage:
    """Persist an agent message for the board chat."""
    store = get_store()
    message = AgentBoardMessage(
        board_id=card.board_id,
        card_id=card.id,
        from_agent_id=normalize_agent_id(from_agent),
        to_agent_id=normalize_agent_id(to_agent) if to_agent else None,
        message_type=message_type,
        content=content.strip(),
        pipeline_step=pipeline_step,
        correlation_id=correlation_id,
    )
    await store.insert("agent_messages", message)
    return message


async def list_board_messages(
    *,
    board_id: str | None = None,
    card_id: str | None = None,
    limit: int = 80,
) -> list[AgentBoardMessage]:
    store = get_store()
    filters: dict[str, str] = {}
    if board_id:
        filters["board_id"] = board_id
    if card_id:
        filters["card_id"] = card_id
    rows = await store.list("agent_messages", filters or None)
    messages = [AgentBoardMessage.model_validate(row) for row in rows]
    messages.sort(key=lambda m: m.created_at, reverse=True)
    return messages[: max(1, min(limit, 200))]
