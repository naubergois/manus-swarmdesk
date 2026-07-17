from fastapi import APIRouter, Query

from app.models.contracts import AgentBoardMessage
from app.services import agent_bus, project_manager
from app.services.project_manager import BoardLiveState

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


@router.get("/live", response_model=BoardLiveState)
async def board_live(
    board_id: str | None = None,
    limit: int = Query(default=24, ge=1, le=80),
) -> BoardLiveState:
    """Nova's live view: headline, briefing, focus card, and recent A2A."""
    return await project_manager.get_live_state(board_id=board_id, limit=limit)
