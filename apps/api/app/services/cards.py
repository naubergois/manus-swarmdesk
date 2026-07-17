from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from fastapi import HTTPException

from app.adapters.langgraph_orchestrator import langgraph
from app.adapters.ruflo_swarm import ruflo
from app.agents import runners
from app.db import get_store
from app.models.contracts import (
    ApprovalAction,
    CardDetail,
    ChatMessage,
    ChatRequest,
    ChatResponse,
    CreateCardRequest,
    HumanApproval,
    TaskCard,
)
from app.models.enums import (
    ApprovalDecision,
    ApprovalType,
    KanbanColumn,
)

logger = logging.getLogger(__name__)


async def list_cards(board_id: str | None = None) -> list[TaskCard]:
    store = get_store()
    filters = {"board_id": board_id} if board_id else None
    rows = await store.list("task_cards", filters)
    return [TaskCard.model_validate(r) for r in rows]


async def get_card(card_id: str) -> TaskCard:
    store = get_store()
    raw = await store.get("task_cards", card_id)
    if not raw:
        raise HTTPException(status_code=404, detail="Cartão não encontrado")
    return TaskCard.model_validate(raw)


async def get_card_detail(card_id: str) -> CardDetail:
    store = get_store()
    card = await get_card(card_id)

    def first(rows: list[dict]):
        return rows[-1] if rows else None

    reqs = await store.list("requirements", {"card_id": card_id})
    plans = await store.list("execution_plans", {"card_id": card_id})
    missions = await store.list("swarm_missions", {"card_id": card_id})
    artifacts = await store.list("artifacts", {"card_id": card_id})
    tests = await store.list("test_results", {"card_id": card_id})
    reviews = await store.list("reviews", {"card_id": card_id})
    tickets = await store.list("tickets", {"card_id": card_id})
    approvals = await store.list("approvals", {"card_id": card_id})
    timeline = await store.list("audit_events", {"card_id": card_id})
    timeline = sorted(timeline, key=lambda e: e.get("created_at", ""))

    from app.models.contracts import (
        AuditEvent,
        ExecutionPlan,
        RequirementSpecification,
        ReviewDecision,
        SupportTicket,
        SwarmMission,
        TestResult,
        WorkArtifact,
    )

    return CardDetail(
        card=card,
        requirements=RequirementSpecification.model_validate(first(reqs)) if reqs else None,
        plan=ExecutionPlan.model_validate(first(plans)) if plans else None,
        mission=SwarmMission.model_validate(first(missions)) if missions else None,
        artifacts=[WorkArtifact.model_validate(a) for a in artifacts],
        tests=[TestResult.model_validate(t) for t in tests],
        reviews=[ReviewDecision.model_validate(r) for r in reviews],
        tickets=[SupportTicket.model_validate(t) for t in tickets],
        approvals=[HumanApproval.model_validate(a) for a in approvals],
        timeline=[AuditEvent.model_validate(e) for e in timeline],
    )


async def _run_pipeline_safe(card_id: str) -> None:
    """Background triage/spec/plan — failures are audited on the card, not on the HTTP client."""
    try:
        card = await get_card(card_id)
        await langgraph.receive_demand(card)
    except Exception as exc:
        logger.exception("LangGraph pipeline failed for %s: %s", card_id, exc)
        try:
            store = get_store()
            raw = await store.get("task_cards", card_id)
            if raw:
                card = TaskCard.model_validate(raw)
                card.tags = list({*card.tags, "pipeline_error"})
                card.updated_at = datetime.utcnow()
                await store.upsert("task_cards", card)
        except Exception:
            logger.exception("Failed to mark pipeline_error on %s", card_id)


async def reset_board(*, reseed_demo: bool = True) -> dict:
    """Delete all cards and generated apps so the board can be regenerated.

    Stops every running mini-app, wipes card-related data and workspaces,
    and (optionally) re-seeds the fresh demo board.
    """
    from app.db import init_store
    from app.services import runtime as runtime_service
    from app.services.seed import seed_if_empty

    stopped = runtime_service.stop_all_runtimes()
    runtime_service.clear_workspaces()

    store = get_store()
    await store.clear()
    # Rebuild an empty store (also reconnects Mongo collections if configured).
    await init_store()

    seeded = False
    if reseed_demo:
        result = await seed_if_empty()
        seeded = bool(result.get("seeded", True))

    logger.info("Board reset: stopped=%s reseed_demo=%s", stopped, reseed_demo)
    return {"ok": True, "runtimes_stopped": stopped, "reseeded": seeded}


async def create_card(
    payload: CreateCardRequest,
    run_pipeline: bool = True,
    *,
    background: bool = True,
) -> TaskCard:
    store = get_store()
    projects = await store.list("projects")
    boards = await store.list("kanban_boards")
    if not projects or not boards:
        raise HTTPException(status_code=400, detail="Nenhum projeto/board disponível")

    project_id = payload.project_id or projects[0]["id"]
    board = next((b for b in boards if b["project_id"] == project_id), boards[0])

    card = TaskCard(
        title=payload.title,
        description=payload.description,
        type=payload.type,
        project_id=project_id,
        board_id=board["id"],
        priority=payload.priority,
        autonomy_level=payload.autonomy_level,
        column=KanbanColumn.ENTRADA,
        kind="epic",
        tags=["epic"],
    )
    await store.upsert("task_cards", card)
    if run_pipeline:
        if background:
            # Return immediately so the UI is not stuck on "Creating..." during LLM calls.
            asyncio.create_task(_run_pipeline_safe(card.id))
        else:
            try:
                card = await langgraph.receive_demand(card)
            except HTTPException:
                raise
            except Exception as exc:
                raise HTTPException(status_code=502, detail=f"Falha no pipeline LangGraph: {exc}") from exc
    return card


async def handle_chat(payload: ChatRequest) -> ChatResponse:
    store = get_store()
    user_msg = ChatMessage(role="user", content=payload.message)
    await store.insert("conversations", user_msg)

    title = payload.message.strip().split("\n")[0][:80]
    card = await create_card(
        CreateCardRequest(
            title=title or "Nova demanda",
            description=payload.message,
            project_id=payload.project_id,
        ),
        run_pipeline=True,
        background=False,
    )

    try:
        supervisor = await runners.run_supervisor_reply(
            payload.message,
            card.title,
            card.column.value,
            card.type.value,
            card.priority.value,
        )
        reply = supervisor.reply
        if supervisor.suggested_title and supervisor.suggested_title != card.title:
            card.title = supervisor.suggested_title[:120]
            card.updated_at = datetime.utcnow()
            await store.upsert("task_cards", card)
    except Exception:
        reply = (
            f"Criei o cartão **{card.title}** e avancei até **{card.column.value}**. "
            f"Tipo: {card.type.value}, prioridade: {card.priority.value}. "
            "Revise o escopo em Aprovações para liberar o enxame."
        )

    assistant = ChatMessage(role="assistant", content=reply, card_id=card.id)
    await store.insert("conversations", assistant)
    messages = [ChatMessage.model_validate(m) for m in await store.list("conversations")]
    messages = sorted(messages, key=lambda m: m.created_at)[-40:]
    return ChatResponse(reply=reply, card=card, messages=messages)


async def list_chat_messages() -> list[ChatMessage]:
    store = get_store()
    rows = await store.list("conversations")
    messages = [ChatMessage.model_validate(m) for m in rows]
    return sorted(messages, key=lambda m: m.created_at)


async def decide_approval(approval_id: str, action: ApprovalAction) -> HumanApproval:
    store = get_store()
    raw = await store.get("approvals", approval_id)
    if not raw:
        raise HTTPException(status_code=404, detail="Aprovação não encontrada")

    approval = HumanApproval.model_validate(raw)
    if approval.decision != ApprovalDecision.PENDENTE:
        raise HTTPException(status_code=400, detail="Aprovação já decidida")

    approval.decision = action.decision
    approval.comment = action.comment or approval.comment
    approval.approver = action.approver
    approval.decided_at = datetime.utcnow()
    await store.upsert("approvals", approval)

    card = await get_card(approval.card_id)

    if action.decision == ApprovalDecision.APROVADO:
        if approval.type == ApprovalType.ESCOPO:
            card.column = KanbanColumn.PRONTO_ENXAME
            card.updated_at = datetime.utcnow()
            await store.upsert("task_cards", card)
            try:
                await ruflo.create_mission(card)
                card = await ruflo.execute(card)
            except HTTPException:
                raise
            except Exception as exc:
                raise HTTPException(status_code=502, detail=f"Falha no enxame: {exc}") from exc
        elif approval.type == ApprovalType.ENTREGA:
            card.column = KanbanColumn.CONCLUIDO
            card.updated_at = datetime.utcnow()
            await store.upsert("task_cards", card)
    elif action.decision in {ApprovalDecision.REPROVADO, ApprovalDecision.EDITAR}:
        card.column = KanbanColumn.REFINAMENTO
        card.updated_at = datetime.utcnow()
        await store.upsert("task_cards", card)

    return approval


async def approve_card(card_id: str, action: ApprovalAction) -> HumanApproval:
    store = get_store()
    approvals = await store.list("approvals", {"card_id": card_id})
    pending = [
        HumanApproval.model_validate(a)
        for a in approvals
        if a.get("decision") == ApprovalDecision.PENDENTE.value
    ]
    if not pending:
        raise HTTPException(status_code=404, detail="Nenhuma aprovação pendente")
    card = await get_card(card_id)
    if card.column == KanbanColumn.PRONTO_ENTREGA:
        target = next((a for a in pending if a.type == ApprovalType.ENTREGA), pending[-1])
    else:
        target = pending[-1]
    return await decide_approval(target.id, action)
