from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from fastapi import HTTPException

from app.adapters.langgraph_orchestrator import langgraph
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
        WorkspaceFile,
    )
    from app.services.runtime import list_workspace_files

    workspace_files = [
        WorkspaceFile.model_validate(row) for row in list_workspace_files(card_id)
    ]

    return CardDetail(
        card=card,
        requirements=RequirementSpecification.model_validate(first(reqs)) if reqs else None,
        plan=ExecutionPlan.model_validate(first(plans)) if plans else None,
        mission=SwarmMission.model_validate(first(missions)) if missions else None,
        artifacts=[WorkArtifact.model_validate(a) for a in artifacts],
        files=workspace_files,
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


# Collections holding data linked to a card via `card_id`.
CARD_RELATED_COLLECTIONS = [
    "requirements",
    "execution_plans",
    "swarm_missions",
    "artifacts",
    "test_results",
    "reviews",
    "tickets",
    "approvals",
    "audit_events",
    "conversations",
]


async def delete_card(card_id: str, *, cascade: bool = True) -> dict:
    """Delete a card, its related data, its generated app, and (optionally) its child cards."""
    from app.services import runtime as runtime_service

    store = get_store()
    card = await store.get("task_cards", card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Cartão não encontrado")

    ids = [card_id]
    if cascade:
        children = await store.list("task_cards", {"parent_id": card_id})
        ids.extend(c["id"] for c in children)

    for cid in ids:
        runtime_service.stop_runtime(cid)
        runtime_service.remove_workspace(cid)
        for collection in CARD_RELATED_COLLECTIONS:
            for row in await store.list(collection, {"card_id": cid}):
                await store.delete(collection, row["id"])
        await store.delete("task_cards", cid)

    logger.info("Deleted card(s): %s", ids)
    return {"ok": True, "deleted": ids}


async def delete_cards(card_ids: list[str], *, cascade: bool = True) -> dict:
    """Delete a batch of cards. Missing IDs are skipped."""
    deleted: list[str] = []
    for cid in card_ids:
        if cid in deleted:
            continue
        try:
            result = await delete_card(cid, cascade=cascade)
            deleted.extend(i for i in result["deleted"] if i not in deleted)
        except HTTPException as exc:
            if exc.status_code != 404:
                raise
    if not deleted:
        raise HTTPException(status_code=404, detail="Nenhum cartão encontrado")
    return {"ok": True, "deleted": deleted}


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

    result = await seed_if_empty(include_demo_cards=reseed_demo)
    seeded = reseed_demo and bool(result.get("seeded", True))

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
        subtasks=[t.strip() for t in payload.subtasks if t.strip()],
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
            "Os subcards podem ser criados automaticamente no Kanban; revise o escopo "
            "em Aprovações antes de liberar a construção da aplicação."
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
            try:
                card = await langgraph.start_swarm_after_approval(card.id)
            except HTTPException:
                raise
            except Exception as exc:
                raise HTTPException(status_code=502, detail=f"Falha ao liberar o enxame: {exc}") from exc
            from app.services import project_manager

            try:
                await project_manager.announce(
                    card,
                    (
                        f"👍 Escopo de «{card.title}» aprovado. "
                        "Enxame liberado — clique em Start quando quiser que eu ponha os robôs a trabalhar."
                    ),
                    message_type="result",
                    pipeline_step="pm_scope_approved",
                )
            except Exception:
                pass
        elif approval.type == ApprovalType.ENTREGA:
            card.column = KanbanColumn.CONCLUIDO
            card.updated_at = datetime.utcnow()
            await store.upsert("task_cards", card)
            from app.services import project_manager

            try:
                await project_manager.announce(
                    card,
                    f"🎉 Entrega de «{card.title}» aprovada — cartão concluído e app no dock live.",
                    message_type="result",
                    pipeline_step="pm_delivery_approved",
                )
            except Exception:
                pass
    elif action.decision in {ApprovalDecision.REPROVADO, ApprovalDecision.EDITAR}:
        card.column = KanbanColumn.REFINAMENTO
        card.updated_at = datetime.utcnow()
        await store.upsert("task_cards", card)
        from app.services import project_manager

        try:
            await project_manager.announce(
                card,
                f"↩️ «{card.title}» voltou para refinamento — vou reorganizar o plano com a equipe.",
                pipeline_step="pm_scope_rejected",
            )
        except Exception:
            pass

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
