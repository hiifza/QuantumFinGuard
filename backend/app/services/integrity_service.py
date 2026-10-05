"""
Tamper-evident record integrity.

This is the concrete, working part of "blockchain security" described
in the spec: not a distributed ledger, but a hash chain over transaction
records — each record's hash incorporates the previous record's hash,
so any retroactive modification to a historical row breaks the chain
and is detectable by verification. This is a genuinely real integrity
mechanism (the same core idea blockchains use for tamper evidence), and
it is explicitly labeled as such rather than described as "blockchain
security" in a way that overclaims what it is.
"""
import hashlib
import json
import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.transaction import Transaction

GENESIS_HASH = "0" * 64


def _canonical_payload(t: Transaction) -> dict:
    """Deterministic field set used for hashing — order-independent via sorted keys."""
    return {
        "id": t.id,
        "customer_id": t.customer_id,
        "merchant_id": t.merchant_id,
        "amount": t.amount,
        "currency": t.currency,
        "timestamp": t.timestamp.isoformat() if t.timestamp else None,
    }


def compute_record_hash(t: Transaction, previous_hash: str) -> str:
    payload = _canonical_payload(t)
    payload["previous_record_hash"] = previous_hash
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def get_latest_hash_and_sequence(db: Session) -> tuple[str, int]:
    """Returns (previous_hash, next_sequence_number). Used both by the
    single-row API path and as the starting point for a bulk-ingestion
    loop's in-memory chain tracking."""
    latest = (
        db.query(Transaction)
        .filter(Transaction.record_hash.isnot(None))
        .order_by(Transaction.chain_sequence.desc())
        .first()
    )
    if latest is None:
        return GENESIS_HASH, 0
    return latest.record_hash, latest.chain_sequence + 1


def get_latest_hash(db: Session) -> str:
    previous_hash, _ = get_latest_hash_and_sequence(db)
    return previous_hash


def _ensure_id(transaction: Transaction) -> None:
    """Transaction.id has a Python-side default, but SQLAlchemy only
    invokes column defaults at flush time — not at object construction.
    Since we hash the transaction *before* it's flushed, transaction.id
    would still be None at hash time unless assigned explicitly here,
    which would make the stored hash unreproducible from the eventually-
    persisted row (exactly the bug that broke chain verification during
    initial ingestion). Assigning eagerly here fixes that at the source."""
    if transaction.id is None:
        transaction.id = str(uuid.uuid4())


def seal_transaction(db: Session, transaction: Transaction) -> Transaction:
    """Chains and hashes a newly created transaction against the latest
    *committed* row. Call this at creation time, before commit, for
    single-transaction API writes (app/api/v1/endpoints/transactions.py).

    NOT safe to call in a tight loop before each row is committed —
    get_latest_hash_and_sequence only sees committed rows (session
    autoflush is off by design), so every row in an uncommitted batch
    would chain off the same stale previous hash. Bulk ingestion must
    use seal_transaction_with_known_previous below instead, tracking the
    running hash+sequence in memory.
    """
    previous_hash, next_seq = get_latest_hash_and_sequence(db)
    _ensure_id(transaction)
    transaction.previous_record_hash = previous_hash
    transaction.chain_sequence = next_seq
    transaction.record_hash = compute_record_hash(transaction, previous_hash)
    return transaction


def seal_transaction_with_known_previous(transaction: Transaction, previous_hash: str, sequence: int) -> str:
    """Bulk-ingestion variant: caller tracks the running (previous_hash,
    sequence) in memory across the loop — starting from
    get_latest_hash_and_sequence(db) once, before any inserts — instead
    of re-querying the DB per row. Returns the new hash so the caller can
    pass it as previous_hash for the next row; sequence is simply
    incremented by the caller. This is what keeps a batch-committed
    chain unbroken and unambiguously ordered."""
    _ensure_id(transaction)
    transaction.previous_record_hash = previous_hash
    transaction.chain_sequence = sequence
    transaction.record_hash = compute_record_hash(transaction, previous_hash)
    return transaction.record_hash


@dataclass
class ChainVerificationResult:
    valid: bool
    total_records: int
    first_broken_record_id: str | None
    checked_at_count: int


@dataclass
class RecordIntegrityResult:
    record_hash: str | None
    previous_record_hash: str | None
    chain_sequence: int | None
    hash_recomputation_matches: bool
    sealed: bool


def verify_single_record(transaction: Transaction) -> RecordIntegrityResult:
    """Local, fast check: does this record's stored hash still match what
    recomputing it now would produce? This does NOT confirm the record's
    position in the full chain is unbroken (a record can locally
    recompute correctly while an earlier record was tampered with) — for
    that, use verify_chain. This is the right granularity for a
    transaction investigation view ('has *this* record been altered
    since it was sealed'), not a substitute for full-chain verification."""
    if transaction.record_hash is None or transaction.previous_record_hash is None:
        return RecordIntegrityResult(None, None, transaction.chain_sequence, False, sealed=False)

    recomputed = compute_record_hash(transaction, transaction.previous_record_hash)
    return RecordIntegrityResult(
        record_hash=transaction.record_hash,
        previous_record_hash=transaction.previous_record_hash,
        chain_sequence=transaction.chain_sequence,
        hash_recomputation_matches=(recomputed == transaction.record_hash),
        sealed=True,
    )


def verify_chain(db: Session) -> ChainVerificationResult:
    """Walks the full chain in chain_sequence order (not created_at,
    which isn't guaranteed unambiguous within a batch) and re-derives
    each hash, comparing against the stored value. Any mismatch means a
    record was altered after being sealed, or the chain was broken."""
    transactions = (
        db.query(Transaction)
        .filter(Transaction.record_hash.isnot(None))
        .order_by(Transaction.chain_sequence.asc())
        .all()
    )

    expected_previous = GENESIS_HASH
    for t in transactions:
        if t.previous_record_hash != expected_previous:
            return ChainVerificationResult(False, len(transactions), t.id, len(transactions))
        recomputed = compute_record_hash(t, expected_previous)
        if recomputed != t.record_hash:
            return ChainVerificationResult(False, len(transactions), t.id, len(transactions))
        expected_previous = t.record_hash

    return ChainVerificationResult(True, len(transactions), None, len(transactions))
