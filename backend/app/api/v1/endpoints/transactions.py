from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_role
from app.core.security import Role
from app.db.session import get_db
from app.models.audit_log import AuditLog
from app.models.transaction import Transaction
from app.models.user import User
from app.schemas.transaction import TransactionCreate, TransactionListResponse, TransactionOut
from app.services.integrity_service import seal_transaction

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.post("", response_model=TransactionOut, status_code=201)
def create_transaction(
    payload: TransactionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.ANALYST)),
):
    transaction = Transaction(**payload.model_dump())
    seal_transaction(db, transaction)  # chains + hashes before persisting
    db.add(transaction)
    db.commit()
    db.refresh(transaction)

    db.add(AuditLog(
        actor_user_id=current_user.id,
        action="transaction.created",
        resource_type="transaction",
        resource_id=transaction.id,
    ))
    db.commit()
    return transaction


@router.get("", response_model=TransactionListResponse)
def list_transactions(
    customer_id: str | None = None,
    merchant_id: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Transaction)
    if customer_id:
        query = query.filter(Transaction.customer_id == customer_id)
    if merchant_id:
        query = query.filter(Transaction.merchant_id == merchant_id)

    total = query.count()
    items = (
        query.order_by(Transaction.timestamp.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return TransactionListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/{transaction_id}", response_model=TransactionOut)
def get_transaction(
    transaction_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    transaction = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found.")

    db.add(AuditLog(
        actor_user_id=current_user.id,
        action="transaction.viewed",
        resource_type="transaction",
        resource_id=transaction.id,
    ))
    db.commit()
    return transaction
