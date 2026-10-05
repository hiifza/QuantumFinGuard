from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.audit_log import AuditLog
from app.models.transaction import Transaction
from app.models.user import User
from app.rag.llm_provider import get_llm_provider
from app.rag.retriever import get_retriever
from app.services.copilot_service import get_copilot_service

router = APIRouter(prefix="/copilot", tags=["copilot"])


class AskRequest(BaseModel):
    question: str
    transaction_id: str | None = None


@router.get("/status")
def copilot_status(current_user: User = Depends(get_current_user)):
    provider = get_llm_provider()
    retriever = get_retriever()
    return {
        "llm_provider": provider.provider_name,
        "llm_configured": provider.is_configured(),
        "retrieval_ready": retriever.is_ready(),
        "knowledge_base_chunks": len(retriever._chunks) if retriever.is_ready() else 0,
        "note": (
            "llm_configured=false means the copilot answers with a retrieved-evidence "
            "digest instead of an LLM-generated narrative — see /copilot/ask."
        ) if not provider.is_configured() else None,
    }


@router.post("/ask")
def ask_copilot(
    payload: AskRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    transaction = None
    if payload.transaction_id:
        transaction = db.query(Transaction).filter(Transaction.id == payload.transaction_id).first()
        if not transaction:
            raise HTTPException(status_code=404, detail="Transaction not found.")

    response = get_copilot_service().ask(db, payload.question, transaction)

    db.add(AuditLog(
        actor_user_id=current_user.id,
        action="copilot.asked",
        resource_type="transaction" if transaction else None,
        resource_id=transaction.id if transaction else None,
        metadata_json={"mode": response.mode, "llm_provider": response.llm_provider, "question": payload.question[:200]},
    ))
    db.commit()

    return {
        "mode": response.mode,
        "answer": response.answer,
        "sources": [{"id": s.id, "type": s.type, "detail": s.detail} for s in response.sources],
        "llm_provider": response.llm_provider,
        "warning": response.warning,
    }
