from fastapi import APIRouter, Query

from app.models.contracts import AgentBoardMessage
from app.services import agent_bus

router = APIRouter(prefix="/board-chat", tags=["board-chat"])


@router.get("/messages", response_model=list[AgentBoardMessage])
async def list_messages(
    board_id: str | None = None,
    card_id: str | None = None,
    limit: int = Query(default=80, ge=1, le=200),
) -> list[AgentBoardMessage]:
    return await agent_bus.list_board_messages(
        board_id=board_id,
        card_id=card_id,
        limit=limit,
    )
