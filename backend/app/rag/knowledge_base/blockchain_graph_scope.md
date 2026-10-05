# Blockchain Graph Analysis Scope

QuantumFinGuard represents Ethereum wallet relationships as a graph —
wallet addresses as nodes, sent/received relationships as edges — and
supports wallet lookup, bounded-depth (1-3 hop) neighborhood expansion,
and listing of flagged (suspicious-pattern) addresses.

## Graph backend

The real Neo4j-backed implementation (`Neo4jGraphService`) is fully
implemented with correct Cypher queries, but requires a live Neo4j
instance (self-hosted or AuraDB) that this environment cannot currently
reach. A local, file-backed fallback (`LocalGraphService`, using
networkx) answers the identical query interface using the same
real/synthetic Ethereum data — this is not a mock; it loads the actual
derived node/edge tables and performs real graph traversal. Which
backend is active is reported at `GET /api/v1/blockchain/status`.

## Important limitation: no card-transaction linkage

Ethereum wallet data is address-level, not linked to individual card
transactions (IEEE-CIS or IBM). A card transaction's investigation view
will show blockchain context as "not_applicable" — this is accurate,
not a missing feature: linking specific crypto-relevant card
transactions to wallet addresses would require a shared identifier that
doesn't exist between these datasets.

## Flagged wallets

Wallets are flagged based on fan-out/velocity patterns (many outgoing
transactions in a short time, many unique counterparties) — available
at `GET /api/v1/blockchain/wallets/flagged`.
