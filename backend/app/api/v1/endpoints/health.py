from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.fraud_service import get_fraud_service
from app.services.graph_service import get_graph_service

router = APIRouter(tags=["health"])


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/health/detailed")
def health_detailed(db: Session = Depends(get_db)):
    db_ok = True
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        db_ok = False

    return {
        "status": "ok" if db_ok else "degraded",
        "components": {
            "database": "ok" if db_ok else "unreachable",
            "fraud_model": "ready" if get_fraud_service().is_ready() else "not_trained",
            "graph_database": "ready" if get_graph_service().is_ready() else "not_configured",
        },
    }
