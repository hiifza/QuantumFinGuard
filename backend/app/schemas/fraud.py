from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class ShapFeatureContribution(BaseModel):
    feature: str
    value: str
    contribution: float  # signed: positive pushes toward "suspicious"
    direction: Literal["increases_risk", "decreases_risk"]


class FraudPredictionOut(BaseModel):
    model_config = ConfigDict(protected_namespaces=(), from_attributes=True)

    transaction_id: str
    model_version: str
    risk_score: float  # 0-100
    fraud_probability: float  # 0-1, model's raw output
    predicted_class: Literal["legitimate", "suspicious"]
    risk_category: Literal["low", "medium", "high"]
    shap_explanation: list[ShapFeatureContribution] | None
    scored_at: datetime


class ModelNotAvailable(BaseModel):
    """Explicit contract for the 'no model trained yet' state — returned
    instead of a fabricated prediction. Matches project rule: never fake
    fraud statistics or model output."""

    detail: str = "No fraud model is currently active. Prediction unavailable."
    active_model_version: str | None = None
