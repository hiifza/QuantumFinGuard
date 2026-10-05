# Security, Integrity, and Post-Quantum Cryptography

## Three independent security dimensions

The Security Center (`GET /api/v1/security/center/overview`)
deliberately reports these as **separate** facts, never combined into
a single aggregate score:

### 1. Application security
JWT (HS256) authentication with access + refresh tokens (each carrying
a unique `jti` claim -- added after a real test failure showed
same-second token issuance could otherwise produce byte-identical
tokens), bcrypt password hashing, role-based access control
(`analyst < senior_analyst < compliance_officer < admin`), a fixed-
window rate limiter, and structured JSON logging with a request-id
correlation.

### 2. Transaction integrity (hash chain)
Every transaction is sealed with a SHA-256 hash over its canonical
fields plus the previous record's hash -- a tamper-evident chain, NOT
a distributed ledger. Verified end-to-end: 103,762 real records
chain-verified valid; a deliberate tamper test (modifying a field on a
committed record) is caught by both the full-chain verifier and a
dedicated pytest regression test that tampers, verifies detection, and
restores the original value.

Two verification granularities, intentionally different:
`verify_single_record()` (used in the investigation view) checks only
that one record's stored hash matches its recomputed value -- fast,
but doesn't confirm the *position* in the chain is unbroken.
`verify_chain()` (full chain, senior_analyst+ role) re-derives every
record's hash in sequence -- the authoritative check, measured at
~0.3-5s for the full 103,762-record chain depending on environment load.

### 3. Post-quantum cryptography
Real NIST-standardized algorithms: ML-KEM-768 (FIPS 203) for key
encapsulation, ML-DSA-65 (FIPS 204) for signatures, via the
`kyber-py` / `dilithium-py` reference implementations (not a custom or
simulated cryptographic scheme).

Explicit security boundary -- stated plainly, not implied:
- Covered: application-layer session-key protection (an ML-KEM-
  encapsulated AES-256-GCM key) and audit-record signing for the
  quantum-safe export/import feature
  (`POST /api/v1/security/pqc/export-audit-log` /
  `POST /api/v1/security/pqc/import-audit-export`).
- NOT covered: network-transport TLS. That's a deployment/reverse-
  proxy concern, outside this application's code, and this system
  makes no claim about it.
- NOT claimed: "100% quantum-safe," "quantum-proof," or any variant.
  The self-test (`GET /api/v1/security/pqc/status`) reports exactly
  two booleans -- whether a live KEM round-trip and a live signature
  round-trip actually passed just now -- nothing more.

Key management: the platform's long-term ML-KEM and ML-DSA keypairs
are generated once and persisted to a local JSON file
(`app/security_artifacts/pqc_keystore.json`, excluded from version
control and from delivery packages). This is explicitly documented as
appropriate for a research prototype on a single trusted machine, not
production practice -- a real deployment would use a secrets manager
or HSM.

## Audit trail

Every security-relevant action -- login, transaction views,
investigation views, chain verifications, PQC self-tests, quantum-safe
exports, copilot queries -- writes a real AuditLog row. The audit-log
endpoint supports filtering by resource_type/resource_id (e.g. "what
security-relevant events touched this specific transaction?"),
verified by a test that opens an investigation view and confirms the
resulting investigation.viewed event is retrievable filtered to that
exact transaction.
