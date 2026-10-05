"""
Transaction Investigation View (Phase 6, refactored Phase 11).

Thin endpoint wrapper around app/services/evidence_service.py, which
does the real work of assembling risk/SHAP/behavioral/blockchain/
security evidence for one transaction. The RAG Investigation Copilot
(Phase 11) uses the same evidence_service functions, so this view and
the copilot's answers are always grounded in identical underlying data.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.audit_log import AuditLog
from app.models.transaction import Transaction
from app.models.user import User
from app.schemas.transaction import TransactionOut
from app.services.evidence_service import gather_all_evidence

router = APIRouter(prefix="/investigation", tags=["investigation"])


@router.get("/transactions/{transaction_id}")
def get_investigation_view(
    transaction_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    transaction = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found.")

    evidence = gather_all_evidence(db, transaction)

    db.add(AuditLog(
        actor_user_id=current_user.id,
        action="investigation.viewed",
        resource_type="transaction",
        resource_id=transaction.id,
        metadata_json={
            "risk_status": evidence["risk_assessment"]["status"],
            "integrity_intact": evidence["security_context"].get("hash_recomputation_matches"),
        },
    ))
    db.commit()

    return {
        "transaction": TransactionOut.model_validate(transaction).model_dump(),
        "risk_assessment": evidence["risk_assessment"],
        "explanation": evidence["explanation"],
        "behavioral_context": evidence["behavioral_context"],
        "blockchain_context": evidence["blockchain_context"],
        "security_context": evidence["security_context"],
        "investigation_summary": evidence["summary"],
    }
