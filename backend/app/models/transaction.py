import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class Transaction(Base):
    """
    Canonical transaction record used across the platform.

    Fields are deliberately sourced from the IEEE-CIS / IBM transaction
    schemas at the field level (amount, timestamp, card/device metadata,
    merchant category) rather than storing either raw dataset verbatim —
    this is the "integrated at the intelligence layer" schema described
    in the project spec, not a blind concatenation of two datasets.
    """

    __tablename__ = "transactions"
    __table_args__ = (
        Index("ix_transactions_customer_id", "customer_id"),
        Index("ix_transactions_merchant_id", "merchant_id"),
        Index("ix_transactions_timestamp", "timestamp"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    external_ref: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)

    customer_id: Mapped[str] = mapped_column(String(64), nullable=False)
    merchant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    merchant_category: Mapped[str | None] = mapped_column(String(64), nullable=True)

    amount: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(8), default="USD")
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    device_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    card_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    country: Mapped[str | None] = mapped_column(String(2), nullable=True)

    # Populated once ingestion assigns a source dataset row.
    source_dataset: Mapped[str | None] = mapped_column(String(32), nullable=True)  # 'ieee_cis' | 'ibm_credit'

    # Tamper-evident integrity hash — see app.services.integrity.
    # Chains to the previous record's hash so any retroactive edit to a
    # historical transaction is detectable. This is the "blockchain-
    # inspired integrity" mechanism described in the spec: it does not
    # claim to be a distributed ledger.
    record_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    previous_record_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Explicit monotonic ordering for chain verification — created_at
    # alone isn't guaranteed unambiguous for rows inserted in the same
    # batch/millisecond, which breaks chain-order verification. This is
    # assigned sequentially by the sealing code, never by the DB.
    chain_sequence: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)

    # Raw source-dataset fields (e.g. full IEEE-CIS row: card1-6, addr,
    # C/D/M columns, ProductCD, etc.) captured at ingestion time. The
    # Transaction table's own typed columns above only cover a display
    # subset — nowhere near what the trained fraud model needs as input.
    # Rather than have the fraud service silently score off partial data
    # (which would be a fabricated-looking prediction), inference
    # reconstructs the exact feature vector from this snapshot. NULL for
    # transactions created through the plain API without a full source
    # row — those honestly cannot be scored until this is populated.
    feature_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    predictions: Mapped[list["FraudPrediction"]] = relationship(back_populates="transaction")
