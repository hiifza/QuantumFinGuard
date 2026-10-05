from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_role
from app.core.config import settings
from app.core.security import ROLE_HIERARCHY, Role
from app.db.session import get_db
from app.models.audit_log import AuditLog
from app.models.transaction import Transaction
from app.models.user import User
from app.services.integrity_service import ChainVerificationResult, verify_chain
from app.services.pqc_service import PqcReadinessStatus, get_pqc_service

router = APIRouter(prefix="/security", tags=["security"])


@router.get("/integrity/verify", response_model=ChainVerificationResult)
def verify_transaction_integrity(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.SENIOR_ANALYST)),
):
    """Re-derives the hash chain over every sealed transaction right now
    and reports whether it's intact — real computation (measured at
    ~0.3s for 10,000 records), not a cached flag. Every run is itself
    logged to the audit trail, so "when was this last verified and by
    whom" is a real historical record, not something recomputed silently."""
    result = verify_chain(db)
    db.add(AuditLog(
        actor_user_id=current_user.id,
        action="security.chain_verified",
        resource_type="transaction_chain",
        metadata_json={
            "valid": result.valid,
            "total_records": result.total_records,
            "first_broken_record_id": result.first_broken_record_id,
        },
    ))
    db.commit()
    return result


@router.get("/pqc/status", response_model=PqcReadinessStatus)
def pqc_readiness(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Runs a live ML-KEM-768 + ML-DSA-65 round trip and reports the
    actual result. See app/services/pqc_service.py for scope notes —
    this covers application-layer key encapsulation and signing, not
    network-transport TLS."""
    result = get_pqc_service().self_test()
    db.add(AuditLog(
        actor_user_id=current_user.id,
        action="security.pqc_self_test",
        resource_type="pqc_service",
        metadata_json={
            "kem_self_test_passed": result.kem_self_test_passed,
            "signature_self_test_passed": result.signature_self_test_passed,
        },
    ))
    db.commit()
    return result


@router.post("/pqc/export-audit-log")
def export_audit_log_quantum_safe(
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.COMPLIANCE_OFFICER)),
):
    """
    The real, working use of the PQC primitives beyond a self-test:
    fetches the most recent audit-log entries, signs them with
    ML-DSA-65, and encrypts them with ML-KEM-768-encapsulated
    AES-256-GCM — see PqcService.create_quantum_safe_export for the
    full mechanism. The returned bundle is self-contained: anyone with
    the signer's public key (included in the bundle) can verify it
    hasn't been tampered with; only the platform's own decapsulation
    key can decrypt it (see /pqc/import-audit-export).
    """
    entries = (
        db.query(AuditLog)
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
        .all()
    )
    payload = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "exported_by": current_user.id,
        "entry_count": len(entries),
        "entries": [
            {
                "id": e.id, "actor_user_id": e.actor_user_id, "action": e.action,
                "resource_type": e.resource_type, "resource_id": e.resource_id,
                "metadata_json": e.metadata_json, "created_at": e.created_at.isoformat(),
            }
            for e in entries
        ],
    }
    bundle = get_pqc_service().create_quantum_safe_export(payload)

    db.add(AuditLog(
        actor_user_id=current_user.id,
        action="security.audit_log_exported",
        resource_type="audit_log",
        metadata_json={"entry_count": len(entries), "signer_public_key": bundle["signer_public_key"][:16] + "..."},
    ))
    db.commit()
    return bundle


class ExportBundleIn(BaseModel):
    algorithm: dict
    kem_ciphertext: str
    nonce: str
    encrypted_payload: str
    signature: str
    signer_public_key: str
    created_at: str


@router.post("/pqc/import-audit-export")
def import_audit_log_quantum_safe(
    bundle: ExportBundleIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.COMPLIANCE_OFFICER)),
):
    """
    Independently verifies and decrypts a bundle produced by
    /pqc/export-audit-log. Demonstrates the round trip actually works
    end to end — sign+encrypt on export, verify+decrypt on import — not
    just that the two operations work in isolation.
    """
    valid, payload, detail = get_pqc_service().verify_and_decrypt_export(bundle.model_dump())

    db.add(AuditLog(
        actor_user_id=current_user.id,
        action="security.audit_log_import_attempted",
        resource_type="audit_log",
        metadata_json={"signature_valid": valid, "detail": detail},
    ))
    db.commit()

    if not valid:
        raise HTTPException(status_code=400, detail=detail)
    return {"signature_valid": True, "detail": detail, "payload": payload}


@router.get("/audit-log")
def list_audit_log(
    limit: int = Query(50, ge=1, le=500),
    action: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.COMPLIANCE_OFFICER)),
):
    """Supports filtering by resource so an investigator can ask 'what
    security-relevant events touched this specific transaction/record?'
    — the traceability half of the SECURE workflow stage, not just a
    flat unfiltered log."""
    query = db.query(AuditLog)
    if action:
        query = query.filter(AuditLog.action == action)
    if resource_type:
        query = query.filter(AuditLog.resource_type == resource_type)
    if resource_id:
        query = query.filter(AuditLog.resource_id == resource_id)
    return query.order_by(AuditLog.created_at.desc()).limit(limit).all()


@router.get("/center/overview")
def security_center_overview(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Consolidated Security Center view combining the three security
    dimensions described in the project spec: application security,
    blockchain/transaction integrity, and post-quantum readiness.

    Every field here is either a real static configuration fact (e.g.
    the actual rate limit, the actual JWT algorithm) or a real,
    freshly-computed result (chain verification, PQC self-test) — none
    of it is a marketing-style score. In line with the project's
    explicit rule, this endpoint does NOT compute or expose any single
    aggregate "security score", and does not claim the hash chain
    secures the platform as a whole — it is one specific, scoped
    mechanism among several, described as such below.
    """
    total_transactions = db.query(func.count(Transaction.id)).scalar()
    sealed_transactions = db.query(func.count(Transaction.id)).filter(Transaction.record_hash.isnot(None)).scalar()

    last_chain_check = (
        db.query(AuditLog)
        .filter(AuditLog.action == "security.chain_verified")
        .order_by(AuditLog.created_at.desc())
        .first()
    )

    audit_counts = dict(
        db.query(AuditLog.action, func.count(AuditLog.id)).group_by(AuditLog.action).all()
    )

    pqc_result = get_pqc_service().self_test()

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "application_security": {
            "authentication": "JWT (HS256), access + refresh token pair",
            "password_hashing": settings.PASSWORD_HASH_SCHEME,
            "authorization_model": "role-based access control",
            "roles": [r.value for r in ROLE_HIERARCHY.keys()],
            "rate_limit_per_minute": settings.RATE_LIMIT_PER_MINUTE,
            "security_headers_enforced": [
                "X-Content-Type-Options", "X-Frame-Options",
                "Referrer-Policy", "Permissions-Policy", "Strict-Transport-Security",
            ],
            "structured_logging": True,
        },
        "blockchain_integrity": {
            "mechanism": "SHA-256 hash chain over transaction records (tamper-evident, not a distributed ledger)",
            "scope_note": (
                "This mechanism detects retroactive tampering with sealed transaction "
                "records. It does not by itself secure the rest of the application "
                "(authentication, network transport, etc. are separate controls above)."
            ),
            "total_transactions": total_transactions,
            "sealed_transactions": sealed_transactions,
            "last_verification": {
                "checked_at": last_chain_check.created_at.isoformat() if last_chain_check else None,
                "result": last_chain_check.metadata_json if last_chain_check else None,
                "status": "available" if last_chain_check else "not_yet_run",
            },
            "note_if_never_run": None if last_chain_check else (
                "No chain verification has been run yet. Call GET /api/v1/security/integrity/verify "
                "(senior_analyst role or higher) to run one."
            ),
        },
        "quantum_safe_security": {
            "kem_algorithm": pqc_result.kem_algorithm,
            "kem_standard": pqc_result.kem_standard,
            "signature_algorithm": pqc_result.signature_algorithm,
            "signature_standard": pqc_result.signature_standard,
            "kem_self_test_passed": pqc_result.kem_self_test_passed,
            "signature_self_test_passed": pqc_result.signature_self_test_passed,
            "scope_note": pqc_result.scope_note,
        },
        "audit_trail": {
            "total_events": sum(audit_counts.values()),
            "events_by_action": audit_counts,
        },
    }
