"""
Unit tests for app/services/pqc_service.py. These exercise the REAL
ML-KEM-768 / ML-DSA-65 reference implementations — no mocking of the
cryptographic primitives, since the entire point is verifying they
actually work.
"""
import pytest

from app.services.pqc_service import get_pqc_service


@pytest.fixture(scope="module")
def pqc():
    return get_pqc_service()


class TestSelfTest:
    def test_self_test_reports_real_pass(self, pqc):
        result = pqc.self_test()
        assert result.kem_self_test_passed is True
        assert result.signature_self_test_passed is True
        assert result.kem_algorithm == "ML-KEM-768"
        assert result.signature_algorithm == "ML-DSA-65"


class TestKemRoundTrip:
    def test_encapsulate_decapsulate_shared_secret_matches(self, pqc):
        keypair = pqc.generate_kem_keypair()
        shared_secret, ciphertext = pqc.encapsulate(keypair.encapsulation_key)
        recovered = pqc.decapsulate(keypair.decapsulation_key, ciphertext)
        assert shared_secret == recovered

    def test_wrong_decapsulation_key_gives_different_secret(self, pqc):
        keypair_a = pqc.generate_kem_keypair()
        keypair_b = pqc.generate_kem_keypair()
        shared_secret, ciphertext = pqc.encapsulate(keypair_a.encapsulation_key)
        wrong_secret = pqc.decapsulate(keypair_b.decapsulation_key, ciphertext)
        assert shared_secret != wrong_secret


class TestSignatureRoundTrip:
    def test_valid_signature_verifies(self, pqc):
        keypair = pqc.generate_signing_keypair()
        message = b"quantumfinguard audit record"
        signature = pqc.sign(keypair.secret_key, message)
        assert pqc.verify(keypair.public_key, message, signature) is True

    def test_tampered_message_fails_verification(self, pqc):
        keypair = pqc.generate_signing_keypair()
        signature = pqc.sign(keypair.secret_key, b"original message")
        assert pqc.verify(keypair.public_key, b"tampered message", signature) is False

    def test_wrong_public_key_fails_verification(self, pqc):
        keypair_a = pqc.generate_signing_keypair()
        keypair_b = pqc.generate_signing_keypair()
        message = b"quantumfinguard audit record"
        signature = pqc.sign(keypair_a.secret_key, message)
        assert pqc.verify(keypair_b.public_key, message, signature) is False


class TestQuantumSafeExport:
    def test_export_then_import_recovers_original_payload(self, pqc):
        payload = {"entries": [{"action": "auth.login", "user": "test"}], "count": 1}
        bundle = pqc.create_quantum_safe_export(payload)
        valid, recovered, detail = pqc.verify_and_decrypt_export(bundle)
        assert valid is True
        assert recovered == payload

    def test_tampered_ciphertext_rejected(self, pqc):
        import base64
        bundle = pqc.create_quantum_safe_export({"x": 1})
        raw = bytearray(base64.b64decode(bundle["encrypted_payload"]))
        raw[0] ^= 0xFF
        bundle["encrypted_payload"] = base64.b64encode(bytes(raw)).decode()
        valid, recovered, detail = pqc.verify_and_decrypt_export(bundle)
        assert valid is False
        assert recovered is None

    def test_tampered_signature_rejected(self, pqc):
        import base64
        bundle = pqc.create_quantum_safe_export({"x": 1})
        raw = bytearray(base64.b64decode(bundle["signature"]))
        raw[0] ^= 0xFF
        bundle["signature"] = base64.b64encode(bytes(raw)).decode()
        valid, recovered, detail = pqc.verify_and_decrypt_export(bundle)
        assert valid is False

    def test_malformed_bundle_rejected_not_crashed(self, pqc):
        valid, recovered, detail = pqc.verify_and_decrypt_export({"nonsense": "bundle"})
        assert valid is False
        assert recovered is None
