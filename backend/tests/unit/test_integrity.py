"""
Unit tests for app/services/integrity_service.py's pure hash-chain logic.
No database required — constructs Transaction ORM objects in memory
(never flushed/committed) and exercises the hashing/chaining/verification
functions directly.
"""
from datetime import datetime, timezone

from app.models.transaction import Transaction
from app.services import integrity_service


def _make_txn(customer_id="c1", amount=100.0) -> Transaction:
    return Transaction(
        customer_id=customer_id, merchant_id="m1", amount=amount,
        currency="USD", timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


class TestSealTransaction:
    def test_genesis_hash_used_for_first_record(self):
        txn = _make_txn()
        result_hash = integrity_service.seal_transaction_with_known_previous(txn, integrity_service.GENESIS_HASH, 0)
        assert txn.previous_record_hash == integrity_service.GENESIS_HASH
        assert txn.record_hash == result_hash
        assert txn.chain_sequence == 0

    def test_id_assigned_before_hashing(self):
        """Regression test: Transaction.id has a Python-side default that
        SQLAlchemy only applies at flush time — hashing before an id is
        assigned would make the persisted hash unreproducible once the
        real id gets populated. _ensure_id must run before hash
        computation."""
        txn = _make_txn()
        assert txn.id is None
        integrity_service.seal_transaction_with_known_previous(txn, integrity_service.GENESIS_HASH, 0)
        assert txn.id is not None
        # Recomputing with the now-assigned id must match the stored hash.
        recomputed = integrity_service.compute_record_hash(txn, integrity_service.GENESIS_HASH)
        assert recomputed == txn.record_hash

    def test_different_amounts_produce_different_hashes(self):
        txn1 = _make_txn(amount=100.0)
        txn2 = _make_txn(amount=200.0)
        h1 = integrity_service.seal_transaction_with_known_previous(txn1, integrity_service.GENESIS_HASH, 0)
        h2 = integrity_service.seal_transaction_with_known_previous(txn2, integrity_service.GENESIS_HASH, 0)
        assert h1 != h2

    def test_chain_links_previous_hash_correctly(self):
        txn1 = _make_txn()
        h1 = integrity_service.seal_transaction_with_known_previous(txn1, integrity_service.GENESIS_HASH, 0)
        txn2 = _make_txn()
        integrity_service.seal_transaction_with_known_previous(txn2, h1, 1)
        assert txn2.previous_record_hash == h1
        assert txn2.chain_sequence == 1


class TestVerifySingleRecord:
    def test_unsealed_record_reports_not_sealed(self):
        txn = _make_txn()
        result = integrity_service.verify_single_record(txn)
        assert result.sealed is False

    def test_sealed_record_matches_after_sealing(self):
        txn = _make_txn()
        integrity_service.seal_transaction_with_known_previous(txn, integrity_service.GENESIS_HASH, 0)
        result = integrity_service.verify_single_record(txn)
        assert result.sealed is True
        assert result.hash_recomputation_matches is True

    def test_tampered_record_fails_verification(self):
        """The core tamper-detection guarantee: mutating a field after
        sealing must make recomputation disagree with the stored hash."""
        txn = _make_txn(amount=100.0)
        integrity_service.seal_transaction_with_known_previous(txn, integrity_service.GENESIS_HASH, 0)
        txn.amount = 999999.0  # tamper after sealing
        result = integrity_service.verify_single_record(txn)
        assert result.hash_recomputation_matches is False
