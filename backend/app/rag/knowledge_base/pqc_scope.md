# Post-Quantum Cryptography Scope

QuantumFinGuard implements two NIST-standardized post-quantum algorithms:
ML-KEM-768 (FIPS 203) for key encapsulation, and ML-DSA-65 (FIPS 204)
for digital signatures.

## What this protects

- **Session/audit key encapsulation**: ML-KEM-768 is used to protect a
  symmetric AES-256 key used to encrypt exported audit-log bundles. This
  defends against a "harvest now, decrypt later" attacker who records
  encrypted traffic today, intending to decrypt it once a
  cryptographically relevant quantum computer exists.
- **Audit-record signing**: ML-DSA-65 signs exported audit-log bundles
  and report exports so their origin and integrity remain verifiable
  even under a post-quantum threat model.

## What this does NOT protect

- Network-layer transport (TLS) is NOT covered by this mechanism. TLS
  termination happens at the deployment's reverse proxy / load balancer,
  which is an infrastructure decision outside this application's code.
  A PQC-capable TLS configuration at that layer would be a separate,
  additional step.
- This is not a claim of "100% quantum-proof" or "quantum immune"
  security. It demonstrates a scoped, genuinely implemented use of
  standardized post-quantum primitives for two specific artifacts
  (session keys and audit signatures), not a blanket guarantee covering
  the entire platform.

## Where this is implemented

`app/services/pqc_service.py` contains the real implementation, backed
by the `kyber-py` (ML-KEM) and `dilithium-py` (ML-DSA) reference
libraries. A live self-test (key generation, encapsulation/decapsulation,
signing/verification) is available at `GET /api/v1/security/pqc/status`.
The working export/import feature is at `POST /api/v1/security/pqc/export-audit-log`
and `POST /api/v1/security/pqc/import-audit-export`.
