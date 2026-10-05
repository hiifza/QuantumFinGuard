"""
SHAP explainability service (Phase 6).

Wired to whichever model app/ml/train_fraud_model.py registered as
active (app/ml_artifacts/active_model.json) — not a separate, possibly
inconsistent copy. If the active model is retrained and swapped, this
service picks up the new one automatically on next load, the same way
fraud_service.py does.

Explainer choice is real, not cosmetic: LinearExplainer for the
logistic-regression case (exact for linear models, and fast) and
TreeExplainer for tree-based models (RandomForest/XGBoost/LightGBM),
matching the "TreeSHAP for tree-based models" design stated in the
accompanying paper (Section V-B design intent, now actually built).
A background sample for the explainer's baseline is drawn from the same
resolved training data (same seed) used at training time, so the
explanation's reference point is the real training distribution, not
an arbitrary placeholder.
"""
import json
import logging
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import shap
from sklearn.linear_model import LogisticRegression

from app.core.config import settings
from app.data import preprocessing, resolver
from app.ml.feature_alignment import align_to_training_columns, load_feature_columns
from app.models.transaction import Transaction
from app.schemas.fraud import ShapFeatureContribution

logger = logging.getLogger("quantumfinguard.xai")

BACKGROUND_SAMPLE_SIZE = 100
TOP_N_FEATURES = 8


class ExplainerNotAvailableError(Exception):
    pass


class XaiService:
    def explain(self, transaction: Transaction) -> list[ShapFeatureContribution]:
        raise NotImplementedError

    def is_ready(self) -> bool:
        raise NotImplementedError


class NoExplainerAvailable(XaiService):
    def explain(self, transaction: Transaction) -> list[ShapFeatureContribution]:
        raise ExplainerNotAvailableError(
            "No trained model is registered yet, so there is nothing to explain. "
            "Run app/ml/train_fraud_model.py first (see app/services/fraud_service.py)."
        )

    def is_ready(self) -> bool:
        return False


class ShapExplainerService(XaiService):
    def __init__(self, registry: dict):
        self._model_version = registry["model_version"]
        self._model = joblib.load(registry["model_path"])
        self._scaler = joblib.load(registry["scaler_path"]) if registry.get("scaler_path") else None
        self._columns = load_feature_columns(Path(registry["columns_path"]))
        vocab_path = registry.get("category_vocab_path")
        self._category_vocab = json.loads(Path(vocab_path).read_text()) if vocab_path else {}
        medians_path = registry.get("numeric_medians_path")
        self._numeric_medians = json.loads(Path(medians_path).read_text()) if medians_path else {}
        self._explainer = self._build_explainer()

    def _background_sample(self) -> pd.DataFrame:
        """Same resolution + preprocessing path as training (same seed),
        so the background distribution genuinely matches what the model
        was trained on rather than being an arbitrary stand-in."""
        resolved = resolver.resolve_ieee_cis(n_rows_if_synthetic=5000)
        X, _ = preprocessing.build_feature_matrix(resolved.frame, category_vocab=self._category_vocab, numeric_medians=self._numeric_medians)
        X = align_to_training_columns(X, self._columns)
        sample = X.sample(n=min(BACKGROUND_SAMPLE_SIZE, len(X)), random_state=42)
        return self._scaler.transform(sample) if self._scaler is not None else sample

    def _build_explainer(self):
        background = self._background_sample()
        if isinstance(self._model, LogisticRegression):
            logger.info("Using shap.LinearExplainer for %s (exact for linear models)", self._model_version)
            return shap.LinearExplainer(self._model, background)
        # Tree-based models (RandomForest, XGBoost, LightGBM) all expose
        # the sklearn-compatible tree API TreeExplainer needs.
        try:
            logger.info("Using shap.TreeExplainer for %s", self._model_version)
            return shap.TreeExplainer(self._model)
        except Exception as exc:
            logger.warning("TreeExplainer failed (%s); falling back to KernelExplainer (slower)", exc)
            return shap.KernelExplainer(self._model.predict_proba, background)

    def is_ready(self) -> bool:
        return True

    def explain(self, transaction: Transaction) -> list[ShapFeatureContribution]:
        if not transaction.feature_snapshot:
            raise ExplainerNotAvailableError(
                "This transaction has no stored feature snapshot, so it cannot be explained "
                "(same limitation as scoring — see fraud_service.py)."
            )
        if transaction.source_dataset and not transaction.source_dataset.startswith("ieee_cis"):
            raise ExplainerNotAvailableError(
                f"This transaction is sourced from '{transaction.source_dataset}', not IEEE-CIS. "
                f"The active explainer is fit to the IEEE-CIS feature space and cannot explain "
                f"transactions from other datasets (same dataset-scope limitation as scoring — "
                f"see fraud_service.py)."
            )

        row_df = pd.DataFrame([transaction.feature_snapshot])
        X, _ = preprocessing.build_feature_matrix(row_df, category_vocab=self._category_vocab, numeric_medians=self._numeric_medians)
        X_aligned = align_to_training_columns(X, self._columns)
        X_for_model = self._scaler.transform(X_aligned) if self._scaler is not None else X_aligned

        raw_shap = self._explainer.shap_values(X_for_model)
        # Different explainer types return different shapes; normalize to
        # a flat 1D array of per-feature contributions for the positive
        # (fraud) class.
        values = self._extract_positive_class_values(raw_shap)

        contributions = []
        for col, val, x_val in zip(self._columns, values, X_aligned.iloc[0]):
            contributions.append(ShapFeatureContribution(
                feature=col,
                value=str(round(float(x_val), 4)) if isinstance(x_val, (int, float, np.floating)) else str(x_val),
                contribution=round(float(val), 5),
                direction="increases_risk" if val > 0 else "decreases_risk",
            ))

        contributions.sort(key=lambda c: abs(c.contribution), reverse=True)
        return contributions[:TOP_N_FEATURES]

    @staticmethod
    def _extract_positive_class_values(raw_shap) -> np.ndarray:
        # LinearExplainer on a binary LogisticRegression: array shape (1, n_features).
        # TreeExplainer on a binary classifier: sometimes a list [class0_arr, class1_arr].
        if isinstance(raw_shap, list):
            arr = raw_shap[1] if len(raw_shap) > 1 else raw_shap[0]
        else:
            arr = raw_shap
        arr = np.asarray(arr)
        if arr.ndim == 2:
            return arr[0]
        return arr


_cached_xai_service: XaiService | None = None
_cached_xai_model_version: str | None = None


def get_xai_service() -> XaiService:
    """Cached: constructing ShapExplainerService means reloading the full
    IEEE-CIS dataset to draw a background sample (~15-20s with the real
    683MB file, vs. near-instant with the old synthetic stand-in) — doing
    that on every single request would make scoring unusably slow. Cache
    is invalidated only when the registry's model_version actually
    changes (i.e. a retrain happened), so a new model is picked up
    without requiring a server restart, but repeated requests against
    the same model reuse the same explainer."""
    global _cached_xai_service, _cached_xai_model_version

    registry_path = Path(settings.MODEL_ARTIFACT_DIR) / "active_model.json"
    if not registry_path.exists():
        return NoExplainerAvailable()

    registry = json.loads(registry_path.read_text())
    if _cached_xai_service is not None and _cached_xai_model_version == registry["model_version"]:
        return _cached_xai_service

    logger.info("Building SHAP explainer for model_version=%s (this reloads training data for the background sample)", registry["model_version"])
    service = ShapExplainerService(registry)
    _cached_xai_service = service
    _cached_xai_model_version = registry["model_version"]
    return service
