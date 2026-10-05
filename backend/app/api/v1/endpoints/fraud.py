import json
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.db.session import get_db
from app.models.fraud_prediction import FraudPrediction
from app.models.transaction import Transaction
from app.models.user import User
from app.schemas.fraud import FraudPredictionOut, ModelNotAvailable
from app.services.fraud_service import ModelNotLoadedError, get_fraud_service
from app.services.xai_service import ExplainerNotAvailableError, get_xai_service

router = APIRouter(prefix="/fraud", tags=["fraud"])


@router.post(
    "/transactions/{transaction_id}/score",
    response_model=FraudPredictionOut,
    responses={501: {"model": ModelNotAvailable}},
)
def score_transaction(
    transaction_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    transaction = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found.")

    service = get_fraud_service()
    try:
        prediction_out = service.score_transaction(transaction)
    except ModelNotLoadedError as exc:
        raise HTTPException(status_code=501, detail=str(exc))

    # SHAP explanation is best-effort on top of a successful score: if the
    # explainer fails for some reason, the prediction itself is still
    # valid and returned — the explanation is additive, not a
    # precondition for scoring. Failure is logged, not silently hidden.
    try:
        xai_service = get_xai_service()
        prediction_out.shap_explanation = xai_service.explain(transaction)
    except ExplainerNotAvailableError as exc:
        logging.getLogger("quantumfinguard.fraud").warning("SHAP explanation unavailable for %s: %s", transaction_id, exc)
        prediction_out.shap_explanation = None

    record = FraudPrediction(
        transaction_id=transaction.id,
        model_version=prediction_out.model_version,
        risk_score=prediction_out.risk_score,
        fraud_probability=prediction_out.fraud_probability,
        predicted_class=prediction_out.predicted_class,
        risk_category=prediction_out.risk_category,
        shap_explanation=[s.model_dump() for s in prediction_out.shap_explanation] if prediction_out.shap_explanation else None,
    )
    db.add(record)
    db.commit()
    return prediction_out


@router.get(
    "/transactions/{transaction_id}/predictions",
    response_model=list[FraudPredictionOut],
)
def get_predictions(
    transaction_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Returns real, previously stored predictions only. An empty list
    means no scoring has happened yet — never backfilled with a guess."""
    predictions = (
        db.query(FraudPrediction)
        .filter(FraudPrediction.transaction_id == transaction_id)
        .order_by(FraudPrediction.scored_at.desc())
        .all()
    )
    return predictions


@router.get("/status")
def fraud_service_status(current_user: User = Depends(get_current_user)):
    service = get_fraud_service()
    return {"ready": service.is_ready()}


@router.get("/models/metrics")
def model_comparison_metrics(current_user: User = Depends(get_current_user)):
    """Returns the real, persisted training-run metrics written by
    app/ml/train_fraud_model.py — precision/recall/F1/ROC-AUC/PR-AUC for
    every model that was compared, plus which one was selected and why.
    404 if no training run has happened yet; never a fabricated table."""
    registry_path = Path(settings.MODEL_ARTIFACT_DIR) / "active_model.json"
    if not registry_path.exists():
        raise HTTPException(status_code=404, detail="No trained model registered yet. Run app/ml/train_fraud_model.py first.")
    registry = json.loads(registry_path.read_text())
    metrics_path = Path(registry["metrics_path"])
    if not metrics_path.exists():
        raise HTTPException(status_code=404, detail="Model registry exists but metrics file is missing.")
    return json.loads(metrics_path.read_text())
