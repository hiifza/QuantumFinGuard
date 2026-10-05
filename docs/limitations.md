# Known Limitations

Consolidated, honest list. Anything not mentioned elsewhere in docs/
that a reviewer should know before treating this as more finished than
it is.

## Backend

- No live Neo4j tested. The Neo4jGraphService implementation is
  complete and has correct Cypher queries, but was never run against
  an actual Neo4j instance in this development environment (no network
  path to one). LocalGraphService (networkx-backed, same interface) is
  what's actually been tested, against real Ethereum data.
- No LLM provider tested. Same situation as Neo4j: AnthropicProvider is
  a complete, real implementation, activated by ANTHROPIC_API_KEY, but
  has not been exercised against the real Anthropic API in this
  environment (no credentialed key available here).
- The stale-synthetic-parquet-shadowing-real-data bug has no automated
  regression test (see docs/testing.md). It was fixed (file-check
  order corrected, stale files deleted), but a future change could
  reintroduce a similar class of bug without a test catching it.
- IBM and IEEE-CIS transactions in the live database are samples for
  the DB-population path specifically (50,076 and 53,686 rows
  respectively, both documented systematic samples -- see
  docs/datasets.md). The ML training and behavioral baseline
  computation use the FULL real datasets; only the live/demo database
  population is sampled, for practical performance reasons.
- Rate limiting is in-memory, documented in the code as adequate for
  single-instance deployment only; a multi-instance production
  deployment would need a Redis-backed limiter.
- PQC key storage is a local JSON file, explicitly documented as
  appropriate for a research prototype, not production.

## Frontend

- 9 of 14 planned screens are not built: Fraud & Risk (standalone),
  Behavioral Intelligence (standalone), Blockchain Explorer (including
  the 3D wallet graph visualization), standalone Investigation Copilot
  page, Security Center, Quantum-Safe/PQC Center, Audit Trail, Dataset
  Status page, System/API Health page. Their nav entries route to an
  honest "not built in this pass" page. The backend API for every one
  of these already exists and has been integration-tested -- this is a
  frontend sequencing gap, not a missing backend capability.
- No visual/screenshot QA. The development environment has no
  reachable browser (Playwright's browser-binary CDN is not network-
  accessible from this sandbox). Verification was TypeScript
  compilation + production build + a Node.js script replicating each
  page's exact API calls against the live real-data backend, not
  human-eye visual review. The actual rendered UI has not been looked
  at by a human as of this delivery.
- Light theme is implemented at the CSS-token level but not
  individually spot-checked per component.
- No frontend automated test suite.

## Research paper compatibility

- The real ROC-AUC 0.923 / PR-AUC 0.556 result (see docs/ml-pipeline.md)
  is genuinely reproducible and safe to cite -- it came from an actual
  training run against the actual full IEEE-CIS dataset, is
  deterministic (random_state=42), and has been re-run more than once
  during this development process with identical results.
- No SHAP summary plots, confusion matrix images, or PR/ROC curve
  images have been generated as standalone artifacts (the raw
  confusion matrix numbers are available via the API and in
  docs/ml-pipeline.md, but not rendered as a figure).
- No behavioral-analytics or blockchain-graph "results" section exists
  because these capabilities don't produce a single evaluable metric
  the way a classifier does -- they're investigative tools, and their
  correctness is what's tested (real deviation calculations, real
  multi-hop graph traversal), not a benchmark score.

## What would need to happen for a from-scratch clean-room reproduction

1. Download the three real Kaggle datasets (requires a free Kaggle
   account; IEEE-CIS also requires accepting competition rules).
2. Place them at the exact paths in the backend README.
3. Run `python -m scripts.ingest_data` (~5 minutes; do not interrupt
   the IBM streaming pass).
4. Run `python -m app.ml.train_fraud_model` (~3 minutes).
5. Run `pytest` to confirm 104/104 passing against your own real data
   (exact counts may differ slightly if Kaggle has updated either
   dataset since this was written).
