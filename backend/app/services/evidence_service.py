"""
Shared transaction evidence assembly (Phase 6, refactored in Phase 11).

Originally lived inline in app/api/v1/endpoints/investigation.py. Pulled
out into its own service so the RAG Investigation Copilot (Phase 11)
retrieves the exact same real evidence the investigation view shows —
not a second, possibly-drifting copy of the same logic. Both callers
get identical status/reason strings for unavailable stages, which
matters for the copilot: if it's going to explain *why* behavioral
context is missing, that explanation needs to be the real one, not a
paraphrase that could go stale.
"""
from sqlalchemy.orm import Session

from app.models.fraud_prediction import FraudPrediction
from app.models.transaction import Transaction
from app.services.behavioral_service import InsufficientHistoryError, get_behavioral_service
from app.services.fraud_service import ModelNotLoadedError, get_fraud_service
from app.services.integrity_service import verify_single_record
from app.services.xai_service import ExplainerNotAvailableError, get_xai_service


def get_risk_assessment(db: Session, transaction: Transaction) -> dict:
    existing = (
        db.query(FraudPrediction)
        .filter(FraudPrediction.transaction_id == transaction.id)
        .order_by(FraudPrediction.scored_at.desc())
        .first()
    )
    if existing:
        return {
            "status": "available",
            "source": "cached_prediction",
            "risk_score": existing.risk_score,
            "fraud_probability": existing.fraud_probability,
            "predicted_class": existing.predicted_class,
            "risk_category": existing.risk_category,
            "model_version": existing.model_version,
            "scored_at": existing.scored_at.isoformat(),
        }

    service = get_fraud_service()
    try:
        prediction = service.score_transaction(transaction)
    except ModelNotLoadedError as exc:
        return {"status": "not_available", "reason": str(exc)}

    record = FraudPrediction(
        transaction_id=transaction.id, model_version=prediction.model_version,
        risk_score=prediction.risk_score, fraud_probability=prediction.fraud_probability,
        predicted_class=prediction.predicted_class, risk_category=prediction.risk_category,
    )
    db.add(record)
    db.commit()
    return {
        "status": "available", "source": "computed_now",
        "risk_score": prediction.risk_score, "fraud_probability": prediction.fraud_probability,
        "predicted_class": prediction.predicted_class, "risk_category": prediction.risk_category,
        "model_version": prediction.model_version, "scored_at": prediction.scored_at.isoformat(),
    }


def get_explanation(transaction: Transaction) -> dict:
    try:
        contributions = get_xai_service().explain(transaction)
        return {"status": "available", "top_features": [c.model_dump() for c in contributions]}
    except ExplainerNotAvailableError as exc:
        return {"status": "not_available", "reason": str(exc)}


def get_behavioral_context(transaction: Transaction) -> dict:
    try:
        ctx = get_behavioral_service().get_customer_context(transaction)
        return {"status": "available", "context": ctx}
    except InsufficientHistoryError as exc:
        return {"status": "not_available", "reason": str(exc)}


def get_blockchain_context(transaction: Transaction) -> dict:
    # Card-sourced transactions (IEEE-CIS) carry no wallet address today.
    # This is an honest architectural gap, not a missing feature to hide:
    # linking crypto-relevant transactions to the Ethereum wallet graph
    # is Phase 8 work.
    return {
        "status": "not_applicable",
        "reason": (
            "This transaction has no associated wallet address. Blockchain "
            "relationship analysis applies to cryptocurrency-linked "
            "transactions once Phase 8 links them to the Ethereum wallet graph."
        ),
    }


def get_security_context(transaction: Transaction) -> dict:
    result = verify_single_record(transaction)
    return {
        "status": "available" if result.sealed else "not_available",
        "sealed": result.sealed,
        "chain_sequence": result.chain_sequence,
        "record_hash": result.record_hash,
        "previous_record_hash": result.previous_record_hash,
        "hash_recomputation_matches": result.hash_recomputation_matches,
        "note": (
            "This checks only that this specific record's stored hash still "
            "matches its content — it does not confirm the full chain is "
            "unbroken. Full-chain verification is available to "
            "senior_analyst+ roles at GET /api/v1/security/integrity/verify."
        ),
    }


def build_deterministic_summary(risk: dict, explanation: dict, behavioral: dict, blockchain: dict, security: dict) -> str:
    """Deterministic, template-assembled summary from the evidence already
    gathered above — explicitly NOT an LLM/RAG-generated narrative. Used
    both as the investigation view's summary and as the copilot's
    fallback when no LLM provider is configured (Phase 11)."""
    parts = []
    if risk["status"] == "available":
        parts.append(f"Risk score {risk['risk_score']}/100 ({risk['risk_category']} category, "
                      f"model {risk['model_version']}).")
    else:
        parts.append("Risk assessment unavailable: " + risk["reason"])

    if explanation["status"] == "available" and explanation["top_features"]:
        top = explanation["top_features"][0]
        parts.append(f"Top contributing factor: {top['feature']} ({top['direction'].replace('_', ' ')}).")

    if behavioral["status"] != "available":
        parts.append("Behavioral context not available: " + behavioral.get("reason", "unknown reason"))
    else:
        sig = behavioral["context"].signals[0] if behavioral["context"].signals else None
        if sig:
            parts.append(f"Behavioral deviation: {sig.deviation_sigma:+.2f}sigma from baseline "
                          f"({'unusual' if sig.is_unusual else 'within normal range'}).")

    if blockchain["status"] == "not_applicable":
        parts.append("No blockchain relationship data applies to this transaction.")

    if security["status"] == "available":
        integrity_state = "intact" if security["hash_recomputation_matches"] else "MISMATCH — record may have been altered"
        parts.append(f"Record integrity: {integrity_state}.")

    parts.append("This is an auto-assembled evidence summary, not an AI-generated narrative or a fraud determination — the analyst decides.")
    return " ".join(parts)


def gather_all_evidence(db: Session, transaction: Transaction) -> dict:
    """Single call that assembles everything — what both the
    investigation endpoint and the copilot actually use."""
    risk = get_risk_assessment(db, transaction)
    explanation = get_explanation(transaction)
    behavioral = get_behavioral_context(transaction)
    blockchain = get_blockchain_context(transaction)
    security = get_security_context(transaction)
    return {
        "risk_assessment": risk,
        "explanation": explanation,
        "behavioral_context": behavioral,
        "blockchain_context": blockchain,
        "security_context": security,
        "summary": build_deterministic_summary(risk, explanation, behavioral, blockchain, security),
    }
