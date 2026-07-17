"""Kanban transition rules (control plane)."""

from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException

from app.db import get_store
from app.models.contracts import AuditEvent, TaskCard, TransitionRequest
from app.models.enums import KanbanColumn

ALLOWED: dict[KanbanColumn, set[KanbanColumn]] = {
    KanbanColumn.ENTRADA: {KanbanColumn.TRIAGEM, KanbanColumn.CANCELADO},
    KanbanColumn.TRIAGEM: {KanbanColumn.REFINAMENTO, KanbanColumn.AGUARDANDO_DECISAO, KanbanColumn.CANCELADO},
    KanbanColumn.REFINAMENTO: {
        KanbanColumn.AGUARDANDO_APROVACAO,
        KanbanColumn.AGUARDANDO_DECISAO,
        KanbanColumn.CANCELADO,
    },
    KanbanColumn.AGUARDANDO_APROVACAO: {
        KanbanColumn.PRONTO_ENXAME,
        KanbanColumn.REFINAMENTO,
        KanbanColumn.CANCELADO,
    },
    KanbanColumn.PRONTO_ENXAME: {KanbanColumn.EM_EXECUCAO, KanbanColumn.BLOQUEADO, KanbanColumn.CANCELADO},
    KanbanColumn.EM_EXECUCAO: {
        KanbanColumn.EM_REVISAO,
        KanbanColumn.BLOQUEADO,
        KanbanColumn.AGUARDANDO_DECISAO,
        KanbanColumn.CANCELADO,
    },
    KanbanColumn.EM_REVISAO: {
        KanbanColumn.EM_TESTES,
        KanbanColumn.EM_EXECUCAO,
        KanbanColumn.AGUARDANDO_DECISAO,
    },
    KanbanColumn.EM_TESTES: {
        KanbanColumn.PRONTO_ENTREGA,
        KanbanColumn.EM_EXECUCAO,
        KanbanColumn.BLOQUEADO,
    },
    KanbanColumn.AGUARDANDO_DECISAO: {
        KanbanColumn.REFINAMENTO,
        KanbanColumn.EM_EXECUCAO,
        KanbanColumn.PRONTO_ENXAME,
        KanbanColumn.CANCELADO,
        KanbanColumn.BLOQUEADO,
    },
    KanbanColumn.PRONTO_ENTREGA: {
        KanbanColumn.CONCLUIDO,
        KanbanColumn.EM_EXECUCAO,
        KanbanColumn.CANCELADO,
    },
    KanbanColumn.BLOQUEADO: {
        KanbanColumn.EM_EXECUCAO,
        KanbanColumn.AGUARDANDO_DECISAO,
        KanbanColumn.CANCELADO,
    },
    KanbanColumn.CONCLUIDO: set(),
    KanbanColumn.CANCELADO: set(),
}


async def transition_card(card_id: str, request: TransitionRequest) -> TaskCard:
    store = get_store()
    raw = await store.get("task_cards", card_id)
    if not raw:
        raise HTTPException(status_code=404, detail="Cartão não encontrado")

    card = TaskCard.model_validate(raw)
    target = request.target

    if target not in ALLOWED.get(card.column, set()):
        raise HTTPException(
            status_code=400,
            detail=f"Transição inválida: {card.column.value} → {target.value}",
        )

    if target in {KanbanColumn.PRONTO_ENXAME, KanbanColumn.EM_EXECUCAO}:
        if not card.acceptance_criteria:
            raise HTTPException(
                status_code=400,
                detail="Cartão sem critérios de aceitação não pode entrar em execução",
            )

    if target == KanbanColumn.PRONTO_ENTREGA:
        tests = await store.list("test_results", {"card_id": card.id})
        if not tests:
            raise HTTPException(status_code=400, detail="Entrega exige resultados de testes")
        latest = sorted(tests, key=lambda t: t.get("created_at", ""))[-1]
        if latest.get("failed", 0) > 0:
            raise HTTPException(status_code=400, detail="Há testes reprovados")

    if target == KanbanColumn.CONCLUIDO:
        arts = await store.list("artifacts", {"card_id": card.id})
        if not arts:
            raise HTTPException(status_code=400, detail="Conclusão exige artefatos/documentação")

    if target == KanbanColumn.BLOQUEADO and not request.reason:
        raise HTTPException(status_code=400, detail="Bloqueio exige motivo")

    previous = card.column
    card.column = target
    if target == KanbanColumn.BLOQUEADO:
        card.block_reason = request.reason
    elif previous == KanbanColumn.BLOQUEADO:
        card.block_reason = None
    card.updated_at = datetime.utcnow()
    await store.upsert("task_cards", card)

    event = AuditEvent(
        card_id=card.id,
        actor=request.actor,
        action="kanban_transition",
        previous_state=previous.value,
        next_state=target.value,
        input_data={"reason": request.reason},
    )
    await store.insert("audit_events", event)

    # Nova (gestor) narrates every move so the board speaks visually.
    from app.services import project_manager

    try:
        await project_manager.announce_transition(
            card,
            previous,
            target,
            actor=request.actor,
            reason=request.reason,
        )
    except Exception:
        pass

    return card
