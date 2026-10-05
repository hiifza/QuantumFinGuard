"""
Fraud/risk scoring service.

This defines the real, permanent interface the API layer talks to. The
concrete implementation swapped in here is `NoModelLoadedFraudService`
until Phase 5 trains and registers an actual model artifact — at which
point `TrainedFraudService` (loading a serialized pipeline from
MODEL_ARTIFACT_DIR) is swapped in via `get_fraud_service()` with no
change to any endpoint or schema.

This file exists specifically so the API never has to fabricate a
prediction: the "not available" path is a first-class, explicit state.
"""
from abc import ABC, abstractmethod
import json
from pathlib import Path

from app.core.config import settings
from app.models.transaction import Transaction
from app.schemas.fraud import FraudPredictionOut


class ModelNotLoadedError(Exception):
    """Raised when a prediction is requested but no trained model is registered."""


class FraudService(ABC):
    @abstractmethod
    def score_transaction(self, transaction: Transaction) -> FraudPredictionOut:
        """Return a real prediction, or raise ModelNotLoadedError."""

    @abstractmethod
    def is_ready(self) -> bool:
        """Whether a trained model is currently loaded and able to score."""


class NoModelLoadedFraudService(FraudService):
    """
    Default implementation while ACTIVE_FRAUD_MODEL_VERSION is unset.

    Every method fails loudly and explicitly rather than returning a
    plausible-looking number. This is intentional: a fabricated fraud
    score is worse than no score.
    """

    def score_transaction(self, transaction: Transaction) -> FraudPredictionOut:
        raise ModelNotLoadedError(
            "No fraud detection model has been trained/registered yet. "
            "This endpoint will return real scores once Phase 5 (ML pipeline) "
            "trains a model on the IEEE-CIS dataset and registers it via "
            "ACTIVE_FRAUD_MODEL_VERSION."
        )

    def is_ready(self) -> bool:
        return False


# --- Real implementation ---
class TrainedFraudService(FraudService):
    """Loads the model registered in app/ml_artifacts/active_model.json
    (written by app/ml/train_fraud_model.py) and scores real transactions
    against it. Registry-file-driven rather than requiring a manual
    ACTIVE_FRAUD_MODEL_VERSION env edit, so "a model was trained" and
    "the API is using it" can't silently drift out of sync."""

    def __init__(self, registry: dict):
        import joblib as _joblib
        from app.ml.feature_alignment import load_feature_columns

        self._model_version = registry["model_version"]
        self._is_synthetic = registry.get("is_synthetic_data", False)
        self._model = _joblib.load(registry["model_path"])
        self._scaler = _joblib.load(registry["scaler_path"]) if registry.get("scaler_path") else None
        self._columns = load_feature_columns(Path(registry["columns_path"]))

        # Category vocab (top-N bucketing for high-cardinality columns like
        # DeviceInfo) must match what training used — see preprocessing.py.
        # Older model artifacts predating this feature won't have the key;
        # fall back to no bucketing rather than crashing, so this stays
        # backward-compatible with already-trained models.
        vocab_path = registry.get("category_vocab_path")
        self._category_vocab = json.loads(Path(vocab_path).read_text()) if vocab_path else {}
        medians_path = registry.get("numeric_medians_path")
        self._numeric_medians = json.loads(Path(medians_path).read_text()) if medians_path else {}

    def is_ready(self) -> bool:
        return True

    def score_transaction(self, transaction: Transaction) -> FraudPredictionOut:
        from datetime import datetime, timezone

        import pandas as pd

        from app.data import preprocessing
        from app.ml.feature_alignment import align_to_training_columns

        if not transaction.feature_snapshot:
            raise ModelNotLoadedError(
                "This transaction has no stored feature snapshot (feature_snapshot is null), "
                "so it cannot be scored against the trained model — it was likely created "
                "through the plain transaction API rather than the IEEE-CIS ingestion pipeline. "
                "Score a transaction ingested via scripts/ingest_data.py instead."
            )

        if transaction.source_dataset and not transaction.source_dataset.startswith("ieee_cis"):
            raise ModelNotLoadedError(
                f"This transaction is sourced from '{transaction.source_dataset}', not IEEE-CIS. "
                f"The fraud/risk model was trained on IEEE-CIS features (ProductCD, card1-6, C/D/M "
                f"columns, etc.) and cannot score transactions from other datasets — their "
                f"feature_snapshot has a different, incompatible schema. This is a dataset-scope "
                f"limitation, not a bug: fraud scoring is an IEEE-CIS-specific capability in the "
                f"current implementation."
            )

        row_df = pd.DataFrame([transaction.feature_snapshot])
        X, _ = preprocessing.build_feature_matrix(row_df, category_vocab=self._category_vocab, numeric_medians=self._numeric_medians)
        X = align_to_training_columns(X, self._columns)

        if self._scaler is not None:
            X = self._scaler.transform(X)
        probability = float(self._model.predict_proba(X)[:, 1][0])

        risk_score = round(probability * 100, 2)
        risk_category = "high" if probability >= 0.5 else ("medium" if probability >= 0.2 else "low")
        predicted_class = "suspicious" if probability >= 0.5 else "legitimate"

        return FraudPredictionOut(
            transaction_id=transaction.id,
            model_version=self._model_version,
            risk_score=risk_score,
            fraud_probability=probability,
            predicted_class=predicted_class,
            risk_category=risk_category,
            shap_explanation=None,  # populated in Phase 6
            scored_at=datetime.now(timezone.utc),
        )


def _load_active_registry() -> dict | None:
    registry_path = Path(settings.MODEL_ARTIFACT_DIR) / "active_model.json"
    if not registry_path.exists():
        return None
    return json.loads(registry_path.read_text())


_cached_fraud_service: FraudService | None = None
_cached_fraud_model_version: str | None = None


def get_fraud_service() -> FraudService:
    """Cached for the same reason as get_xai_service (xai_service.py):
    avoid reloading model artifacts from disk on every single request.
    Invalidated when active_model.json's model_version changes."""
    global _cached_fraud_service, _cached_fraud_model_version

    registry = _load_active_registry()
    if registry is None:
        return NoModelLoadedFraudService()

    if _cached_fraud_service is not None and _cached_fraud_model_version == registry["model_version"]:
        return _cached_fraud_service

    service = TrainedFraudService(registry)
    _cached_fraud_service = service
    _cached_fraud_model_version = registry["model_version"]
    return service
