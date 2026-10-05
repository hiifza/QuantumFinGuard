"""
Behavioral analytics service (Phase 7).

Loads the persisted per-user and per-merchant baselines that
scripts/ingest_data.py computed from the IBM Credit Card Transactions
dataset (app/data/behavioral_features.py), and answers "does this
transaction look unusual relative to this entity's own history?" for
any transaction that actually has a matching baseline.

IMPORTANT — why this only works for IBM-sourced transactions:
IEEE-CIS and IBM Credit Card Transactions are separate Kaggle datasets
with unrelated synthetic identifier spaces (IEEE-CIS's card1-derived
customer_id has no real-world correspondence to IBM's User index). This
project's own design principle — keep the three datasets integrated at
the intelligence layer, not merged — means behavioral context is a real
capability demonstrated on IBM-sourced transactions, not something
fabricated for IEEE-CIS transactions by pretending the two ID spaces
line up. A transaction whose customer_id doesn't start with
"ibm_user_" gets an honest, specific "wrong dataset" explanation rather
than a silently-wrong baseline.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from app.core.config import settings
from app.data.behavioral_features import compute_deviation
from app.models.transaction import Transaction


class InsufficientHistoryError(Exception):
    pass


@dataclass
class BehavioralSignal:
    name: str
    observed_value: float
    baseline_mean: float
    baseline_stddev: float
    deviation_sigma: float
    is_unusual: bool


@dataclass
class BehavioralContext:
    entity_type: str  # "customer" | "merchant"
    entity_id: str
    history_window_days: int
    history_sample_size: int
    signals: list[BehavioralSignal]


MIN_HISTORY_FOR_BASELINE = 20  # must match app/data/behavioral_features.py's default


class BehavioralService(ABC):
    @abstractmethod
    def get_customer_context(self, transaction: Transaction) -> BehavioralContext: ...

    @abstractmethod
    def get_merchant_context(self, transaction: Transaction) -> BehavioralContext: ...

    @abstractmethod
    def is_ready(self) -> bool: ...


class NoBaselineBehavioralService(BehavioralService):
    """Active when no baseline files have been computed yet (ingestion
    hasn't run). Raises rather than returning zeroed/placeholder
    signals, which would misleadingly look like 'nothing unusual found'."""

    def get_customer_context(self, transaction: Transaction) -> BehavioralContext:
        raise InsufficientHistoryError(
            "Behavioral baselines have not been computed yet. Run "
            "scripts/ingest_data.py, which computes them from the IBM "
            "Credit Card Transactions dataset."
        )

    def get_merchant_context(self, transaction: Transaction) -> BehavioralContext:
        raise InsufficientHistoryError("Behavioral baselines have not been computed yet.")

    def is_ready(self) -> bool:
        return False


class RealBehavioralService(BehavioralService):
    def __init__(self, user_baseline_path: Path, merchant_baseline_path: Path):
        self._user_baselines = pd.read_parquet(user_baseline_path).set_index("User")
        self._merchant_baselines = pd.read_parquet(merchant_baseline_path).set_index("MCC")

    def is_ready(self) -> bool:
        return True

    def get_customer_context(self, transaction: Transaction) -> BehavioralContext:
        if not transaction.customer_id.startswith("ibm_user_"):
            raise InsufficientHistoryError(
                f"customer_id '{transaction.customer_id}' is not from the IBM Credit Card "
                f"Transactions dataset (source_dataset='{transaction.source_dataset}'). Behavioral "
                f"baselines are computed from IBM transaction history and do not apply to "
                f"customer identifiers from other datasets — the two datasets' identifier "
                f"spaces are unrelated by design (see module docstring)."
            )

        user_key = transaction.customer_id.removeprefix("ibm_user_")
        try:
            user_id = int(user_key)
        except ValueError:
            raise InsufficientHistoryError(f"Malformed IBM user id in customer_id: {transaction.customer_id}")

        if user_id not in self._user_baselines.index:
            raise InsufficientHistoryError(
                f"User {user_id} has fewer than {MIN_HISTORY_FOR_BASELINE} historical transactions "
                f"in the ingested IBM data — not enough to form a meaningful baseline."
            )

        baseline_row = self._user_baselines.loc[user_id]
        deviation = compute_deviation(transaction.amount, baseline_row)
        signal = BehavioralSignal(
            name="transaction_amount_zscore",
            observed_value=deviation["observed_value"],
            baseline_mean=deviation["baseline_mean"],
            baseline_stddev=deviation["baseline_stddev"],
            deviation_sigma=deviation["deviation_sigma"],
            is_unusual=deviation["is_unusual"],
        )
        return BehavioralContext(
            entity_type="customer", entity_id=transaction.customer_id,
            history_window_days=30, history_sample_size=int(baseline_row["transaction_count"]),
            signals=[signal],
        )

    def get_merchant_context(self, transaction: Transaction) -> BehavioralContext:
        if not transaction.merchant_id.startswith("ibm_mcc_"):
            raise InsufficientHistoryError(
                f"merchant_id '{transaction.merchant_id}' is not from the IBM Credit Card "
                f"Transactions dataset. Merchant baselines are computed from IBM merchant "
                f"category (MCC) history only."
            )

        mcc_key = transaction.merchant_id.removeprefix("ibm_mcc_")
        try:
            mcc = int(mcc_key)
        except ValueError:
            raise InsufficientHistoryError(f"Malformed MCC in merchant_id: {transaction.merchant_id}")

        if mcc not in self._merchant_baselines.index:
            raise InsufficientHistoryError(
                f"Merchant category {mcc} has fewer than {MIN_HISTORY_FOR_BASELINE} historical "
                f"transactions in the ingested IBM data."
            )

        baseline_row = self._merchant_baselines.loc[mcc]
        deviation = compute_deviation(transaction.amount, baseline_row)
        signal = BehavioralSignal(
            name="transaction_amount_zscore",
            observed_value=deviation["observed_value"],
            baseline_mean=deviation["baseline_mean"],
            baseline_stddev=deviation["baseline_stddev"],
            deviation_sigma=deviation["deviation_sigma"],
            is_unusual=deviation["is_unusual"],
        )
        return BehavioralContext(
            entity_type="merchant", entity_id=transaction.merchant_id,
            history_window_days=30, history_sample_size=int(baseline_row["transaction_count"]),
            signals=[signal],
        )


def get_behavioral_service() -> BehavioralService:
    processed_dir = Path(settings.PROCESSED_DATA_DIR)
    for suffix in ("", "_synthetic"):  # real data (no suffix) must win if both exist
        user_path = processed_dir / f"ibm_user_baselines{suffix}.parquet"
        merchant_path = processed_dir / f"ibm_merchant_baselines{suffix}.parquet"
        if user_path.exists() and merchant_path.exists():
            return RealBehavioralService(user_path, merchant_path)
    return NoBaselineBehavioralService()
