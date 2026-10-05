import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class FraudPrediction(Base):
    """
    One row per (transaction, model_version) scoring event.

    This table is only ever written by the real inference service
    (Phase 5). It intentionally has no default/mock row seeding — until
    a model is trained, endpoints that would read from this table return
    HTTP 501 with an explicit "model not yet trained" message rather than
    a fabricated score. See app/services/fraud_service.py.
    """

    __tablename__ = "fraud_predictions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    transaction_id: Mapped[str] = mapped_column(String(36), ForeignKey("transactions.id"), nullable=False)

    model_version: Mapped[str] = mapped_column(String(64), nullable=False)
    risk_score: Mapped[float] = mapped_column(Float, nullable=False)  # 0-100, calibrated from model probability
    fraud_probability: Mapped[float] = mapped_column(Float, nullable=False)  # raw model output, 0-1
    predicted_class: Mapped[str] = mapped_column(String(16), nullable=False)  # 'legitimate' | 'suspicious'
    risk_category: Mapped[str] = mapped_column(String(16), nullable=False)  # 'low' | 'medium' | 'high'

    # SHAP explanation payload: list of {feature, value, contribution}.
    # Populated by the XAI service (Phase 6); null until then.
    shap_explanation: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    scored_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    transaction: Mapped["Transaction"] = relationship(back_populates="predictions")
