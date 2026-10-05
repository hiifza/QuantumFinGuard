# QuantumFinGuard — Architecture

## System overview

QuantumFinGuard is a FastAPI backend + React/TypeScript frontend
implementing an analyst-facing financial fraud investigation workflow:

```
DETECT -> EXPLAIN -> CONTEXTUALIZE -> INVESTIGATE -> SECURE -> FUTURE-PROOF -> DECIDE
```

Each stage maps to a distinct backend module and is backed by real
computation against real data (see `docs/datasets.md` for what "real"
means for each of the three source datasets):

| Stage | Module | Real data source |
|---|---|---|
| DETECT | `app/services/fraud_service.py`, `app/ml/train_fraud_model.py` | IEEE-CIS (full 590,540 rows) |
| EXPLAIN | `app/services/xai_service.py` (SHAP) | Same trained model |
| CONTEXTUALIZE | `app/services/behavioral_service.py` | IBM Credit Card Transactions (full 24.4M rows, streamed) |
| INVESTIGATE | `app/services/graph_service.py` | Ethereum Fraud Detection (9,841 addresses) |
| SECURE | `app/services/integrity_service.py`, Security Center | All ingested transactions (hash chain) |
| FUTURE-PROOF | `app/services/pqc_service.py` | N/A (cryptographic primitives, not dataset-derived) |
| DECIDE | `app/services/copilot_service.py` + `app/services/evidence_service.py` | Aggregates all of the above |

## Backend layout

```
backend/
  app/
    api/v1/endpoints/    # one file per resource area (auth, transactions,
                          # fraud, behavioral, blockchain, security, copilot,
                          # investigation, data_status, health)
    core/                # config, JWT/security, logging, middleware
    data/                # dataset schemas, loaders, preprocessing, resolver
    db/                  # SQLAlchemy session/engine
    ml/                  # training pipeline, feature alignment
    models/               # SQLAlchemy ORM models
    rag/                  # knowledge base + retriever + LLM provider
    schemas/               # Pydantic request/response models
    services/              # business logic, one file per capability
    ml_artifacts/           # persisted trained model + metadata (checked in,
                             # excluded only the raw datasets)
  data/
    raw/                   # NOT checked in — place real Kaggle CSVs here
    processed/              # derived parquet artifacts (baselines, features)
  scripts/ingest_data.py    # one-shot: load real-or-synthetic data, persist
                             # processed artifacts, populate the DB
  tests/
    unit/                   # no DB, no API — pure function tests
    integration/            # FastAPI TestClient against real ingested data
    e2e/                     # sequential full-workflow smoke tests
```

## Design principle: honest degradation, not simulation

Every external dependency this system has — real Kaggle datasets, a
live Neo4j instance, an Anthropic API key — is optional at the code
level. When present, the real implementation runs. When absent, the
system reports an explicit, specific "not available" state (with a
reason) rather than fabricating a plausible-looking substitute. This
is enforced structurally: every service that has an external
dependency (`FraudService`, `GraphService`, `LlmProvider`,
`BehavioralService`) is an abstract interface with a real
implementation and an explicit "unavailable" implementation, selected
by a factory function that checks for the dependency's actual presence.

## Data flow: ingestion to serving

```
Real CSV files (backend/data/raw/)
  -> app/data/loaders.py       (schema validation, memory-safe loading)
  -> app/data/preprocessing.py  (feature engineering, category bucketing)
  -> scripts/ingest_data.py     (orchestrates: persist processed artifacts,
                                  write sampled/full transactions to DB,
                                  hash-chain seal each one)
  -> app/ml/train_fraud_model.py (trains 4 models on the FULL real IEEE-CIS
                                   data, persists the best one + its
                                   preprocessing artifacts to app/ml_artifacts/)
  -> app/services/*.py           (serve real predictions/explanations/
                                   context at request time, loading the
                                   persisted artifacts)
  -> app/api/v1/endpoints/*.py   (HTTP layer)
  -> frontend/src/api/           (typed client, consumed by React pages)
```

See `docs/ml-pipeline.md`, `docs/datasets.md`, and `docs/limitations.md`
for the details of each stage.
