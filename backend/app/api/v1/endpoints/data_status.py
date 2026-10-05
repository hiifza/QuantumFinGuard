from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.data.resolver import ingestion_status
from app.db.session import get_db
from app.models.transaction import Transaction
from app.models.user import User

router = APIRouter(prefix="/data", tags=["data"])


@router.get("/ingestion-status")
def get_ingestion_status(current_user: User = Depends(get_current_user)):
    """Reports, honestly, whether each dataset's REAL Kaggle file is
    present on disk right now — not whether it's ever been ingested.
    See app/data/loaders.py for how to provide the real files."""
    return ingestion_status()


@router.get("/transactions/source-breakdown")
def transaction_source_breakdown(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Real counts, grouped by source_dataset — this is what lets the UI
    show a 'Synthetic / Demo Data' badge wherever it actually applies,
    computed from the data itself rather than a hardcoded flag."""
    rows = (
        db.query(Transaction.source_dataset, func.count(Transaction.id))
        .group_by(Transaction.source_dataset)
        .all()
    )
    return {
        (source or "unknown"): {
            "count": count,
            "is_synthetic": bool(source and source.endswith("_synthetic")),
        }
        for source, count in rows
    }
