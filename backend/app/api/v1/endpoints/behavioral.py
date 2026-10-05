from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.transaction import Transaction
from app.models.user import User
from app.services.behavioral_service import InsufficientHistoryError, get_behavioral_service

router = APIRouter(prefix="/behavioral", tags=["behavioral"])


def _get_transaction_or_404(transaction_id: str, db: Session) -> Transaction:
    transaction = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found.")
    return transaction


@router.get("/customers/{customer_id}/context")
def customer_context(
    customer_id: str,
    transaction_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    transaction = _get_transaction_or_404(transaction_id, db)
    if transaction.customer_id != customer_id:
        raise HTTPException(status_code=400, detail="transaction_id does not belong to the given customer_id.")

    service = get_behavioral_service()
    try:
        return service.get_customer_context(transaction)
    except InsufficientHistoryError as exc:
        raise HTTPException(status_code=501, detail=str(exc))


@router.get("/merchants/{merchant_id}/context")
def merchant_context(
    merchant_id: str,
    transaction_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    transaction = _get_transaction_or_404(transaction_id, db)
    if transaction.merchant_id != merchant_id:
        raise HTTPException(status_code=400, detail="transaction_id does not belong to the given merchant_id.")

    service = get_behavioral_service()
    try:
        return service.get_merchant_context(transaction)
    except InsufficientHistoryError as exc:
        raise HTTPException(status_code=501, detail=str(exc))
