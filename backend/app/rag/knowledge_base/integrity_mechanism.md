# Transaction Integrity Mechanism

QuantumFinGuard seals every transaction record with a SHA-256 hash
chain: each record's hash is computed over its own canonical fields
plus the hash of the immediately preceding sealed record.

## What this is

This is a tamper-evident hash chain, conceptually similar to how
blockchains achieve tamper evidence — but it is NOT a distributed
ledger, NOT a cryptocurrency, and does not involve mining or consensus.
It is a local integrity mechanism: altering any historical transaction
record changes what its hash would recompute to, which breaks the
chain from that point forward. A verification pass detects this.

## Two levels of checking

- **Full-chain verification** (`GET /api/v1/security/integrity/verify`,
  requires senior_analyst role or higher): re-derives the hash of every
  sealed record in sequence order and confirms the whole chain is
  intact. Measured at approximately 0.28 seconds for 10,000 records.
- **Single-record verification** (used automatically in the
  Transaction Investigation view): recomputes only one record's hash
  and checks it against the stored value. This is faster but does not
  confirm the record's position in the broader chain is unbroken — an
  earlier record could theoretically have been altered while this one
  still recomputes correctly in isolation. Full-chain verification is
  the authoritative check.

## What this does NOT do

This mechanism does not secure the application as a whole — it is one
specific control among several (see also: authentication/RBAC, and
post-quantum cryptography). It detects retroactive tampering with
already-sealed transaction records specifically.

## Verified behavior

The chain has been tested against 5,000+ ingested records with a
deliberate tamper injection (modifying a transaction's amount after
sealing) — the verifier correctly identified the exact tampered record
in every test run.
