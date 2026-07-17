from fastapi import APIRouter, HTTPException

from app.adapters.ruflo_swarm import ruflo
from app.db import get_store
from app.models.contracts import SwarmMission

router = APIRouter(prefix="/swarm", tags=["swarm"])


@router.get("/missions")
async def list_missions() -> list[SwarmMission]:
    store = get_store()
    rows = await store.list("swarm_missions")
    items = [SwarmMission.model_validate(r) for r in rows]
    return sorted(items, key=lambda m: m.created_at, reverse=True)


@router.get("/missions/{mission_id}")
async def get_mission(mission_id: str) -> SwarmMission:
    store = get_store()
    raw = await store.get("swarm_missions", mission_id)
    if not raw:
        raise HTTPException(status_code=404, detail="Missão não encontrada")
    return SwarmMission.model_validate(raw)


@router.post("/missions/{mission_id}/stop")
async def stop_mission(mission_id: str) -> SwarmMission:
    mission = await ruflo.stop_mission(mission_id)
    if not mission:
        raise HTTPException(status_code=404, detail="Missão não encontrada")
    return mission


@router.post("/missions/{mission_id}/start")
async def start_mission(mission_id: str) -> SwarmMission:
    mission = await ruflo.start_mission(mission_id)
    if not mission:
        raise HTTPException(status_code=404, detail="Missão não encontrada")
    return mission


@router.post("/cards/{card_id}/stop")
async def stop_card_swarm(card_id: str) -> SwarmMission:
    try:
        return await ruflo.stop_card(card_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/cards/{card_id}/start")
async def start_card_swarm(card_id: str) -> SwarmMission:
    try:
        return await ruflo.start_card(card_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
