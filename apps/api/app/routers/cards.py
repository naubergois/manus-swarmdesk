from fastapi import APIRouter, Query

from app.models.contracts import (
    ApprovalAction,
    CardDetail,
    CreateCardRequest,
    HumanApproval,
    TaskCard,
    TransitionRequest,
)
from app.services import cards as card_service
from app.services.transitions import transition_card

router = APIRouter(tags=["cards"])


@router.get("/boards/{board_id}/cards")
async def board_cards(board_id: str) -> list[TaskCard]:
    return await card_service.list_cards(board_id)


@router.get("/cards")
async def all_cards(board_id: str | None = Query(default=None)) -> list[TaskCard]:
    return await card_service.list_cards(board_id)


@router.post("/cards/reset")
async def reset_board(reseed_demo: bool = Query(default=True)) -> dict:
    """Delete all cards and generated apps, then regenerate a fresh board."""
    return await card_service.reset_board(reseed_demo=reseed_demo)


@router.post("/boards/{board_id}/cards")
async def create_board_card(board_id: str, payload: CreateCardRequest) -> TaskCard:
    from app.db import get_store

    store = get_store()
    board = await store.get("kanban_boards", board_id)
    if board and not payload.project_id:
        payload = payload.model_copy(update={"project_id": board["project_id"]})
    return await card_service.create_card(payload, run_pipeline=True)


@router.post("/cards")
async def create_card(payload: CreateCardRequest) -> TaskCard:
    return await card_service.create_card(payload, run_pipeline=True)


@router.get("/cards/{card_id}")
async def get_card(card_id: str) -> CardDetail:
    return await card_service.get_card_detail(card_id)


@router.post("/cards/{card_id}/transition")
async def transition(card_id: str, payload: TransitionRequest) -> TaskCard:
    return await transition_card(card_id, payload)


@router.post("/cards/{card_id}/approve")
async def approve(card_id: str, payload: ApprovalAction) -> HumanApproval:
    return await card_service.approve_card(card_id, payload)


@router.post("/cards/{card_id}/reject")
async def reject(card_id: str, payload: ApprovalAction) -> HumanApproval:
    from app.models.enums import ApprovalDecision

    action = ApprovalAction(
        decision=ApprovalDecision.REPROVADO,
        comment=payload.comment,
        approver=payload.approver,
    )
    return await card_service.approve_card(card_id, action)


@router.get("/cards/{card_id}/timeline")
async def timeline(card_id: str):
    detail = await card_service.get_card_detail(card_id)
    return detail.timeline
