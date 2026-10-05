# QuantumFinGuard Backend

FastAPI backend for the QuantumFinGuard financial risk and fraud
analytics platform. This README reflects the REAL state of the system
as of the latest real-dataset integration — every claim below was
verified by actually running the thing, not assumed.

## What changed in this pass: real datasets, not synthetic

The three authoritative Kaggle datasets are now integrated and the
fraud model is trained on real data:

| Dataset | Rows | Status |
|---|---|---|
| IEEE-CIS Fraud Detection | 590,540 (full) | Real — used for model training + SHAP |
| IBM Credit Card Transactions | 24,386,900 (full, streamed) | Real — used for behavioral baselines |
| Ethereum Fraud Detection | 9,841 (full) | Real — used for wallet graph |

**Real trained model**: LightGBM (selected by validation PR-AUC over
Logistic Regression, Random Forest, and XGBoost). Test-set metrics on
held-out real IEEE-CIS data: **ROC-AUC 0.923, PR-AUC 0.556, Recall
0.809, Precision 0.201** (at default 0.5 threshold — precision/recall
trade off against each other; PR-AUC is the metric that matters most
given ~3.5% fraud prevalence). Full comparison across all four models
available at `GET /api/v1/fraud/models/metrics`.

## Real bugs found and fixed while integrating real data

Documented here because they're the kind of thing that matters for
research reproducibility, and because "it worked on synthetic data"
turned out not to mean "it's correct":

1. **IEEE-CIS is two files, not one.** `DeviceType`/`DeviceInfo` live in
   `train_identity.csv`, joined to `train_transaction.csv` on
   `TransactionID` (left join — only ~24% of transactions have a
   matching identity record). An earlier version of this pipeline
   incorrectly assumed a single pre-joined file.
2. **DeviceInfo has 1,786 distinct real values**, not the handful the
   synthetic generator produced. Naive one-hot encoding exploded the
   feature matrix to 1,963 columns. Fixed by bucketing to the top-20
   most frequent values + "other", fit on training data and persisted
   for consistent inference.
3. **LightGBM rejects certain special characters in feature names**
   (e.g., real DeviceInfo values like `"rv:11.0"` produced a column
   literally named `DeviceInfo_rv:11.0`). Fixed with a deterministic
   sanitizer applied identically at train and inference time.
4. **Stale-file preference bug**: the graph and behavioral services
   checked for `*_synthetic.parquet` files before real ones, so leftover
   files from an earlier phase silently shadowed the newly-ingested
   real data even though ingestion succeeded. Fixed the check order and
   deleted the stale files.
5. **SHAP explainer was rebuilt from scratch on every single request**,
   including a full reload of the 590K-row real dataset for the
   background sample (~15-20s per request). Fixed with a cached
   singleton, invalidated only when the active model actually changes.
6. **Single-row median imputation was degenerate at inference time**
   (the "median" of one value is that value — if it's NaN, filling with
   it does nothing). Fixed by persisting training-set medians and
   reusing them at inference, same pattern as the category vocabulary.

## Setup (Windows / PowerShell)

```powershell
# 1. Clone/extract this project, then from the backend/ folder:
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# 2. Copy the environment template and edit as needed
copy .env.example .env

# 3. Place the real datasets (see below) at backend\data\raw\

# 4. Ingest data + train the model (takes ~5-8 minutes with the full
#    real IBM file; see "Performance notes" below)
python -m scripts.ingest_data
python -m app.ml.train_fraud_model

# 5. Start the server
uvicorn app.main:app --reload --port 8000
```

Then open http://127.0.0.1:8000/api/docs for interactive Swagger docs.

## Required dataset placement

Download these yourself from Kaggle (requires a free account; IEEE-CIS
requires accepting competition rules) and place at exactly these paths
— filenames must match the real Kaggle release exactly:

```
backend/data/raw/train_transaction.csv        (IEEE-CIS, ~683MB)
backend/data/raw/train_identity.csv           (IEEE-CIS, ~26.5MB)
backend/data/raw/ibm_credit_card_transactions.csv   (IBM, ~2.35GB)
backend/data/raw/ethereum_dataset.csv         (Ethereum, ~2.9MB)
```

Sources:
- IEEE-CIS: `kaggle competitions download -c ieee-fraud-detection`
- IBM: `kaggle datasets download -d ealtman2019/credit-card-transactions`
  (the file inside is named `credit_card_transactions-ibm_v2.csv` —
  rename it to `ibm_credit_card_transactions.csv` after extracting)
- Ethereum: `kaggle datasets download -d vagifa/ethereum-frauddetection-dataset`

If these files are absent, the system automatically falls back to a
clearly-labeled synthetic data generator (every resulting record is
tagged `_synthetic` in the database) so the pipeline remains runnable
for development — but no real research results come from that path.

## Performance notes (measured, not estimated)

- IEEE-CIS load + merge: ~14s, ~520MB peak memory
- IBM full-file streaming (both baseline passes): ~100s for 24.4M rows
- Full 4-model training on real 590K-row IEEE-CIS data: ~175s
  (Random Forest is the slowest at ~126s; LightGBM ~16s)
- Chain verification over 103,762 sealed records: ~0.3-5s depending on
  environment load

This ran successfully in a constrained environment (3.9GB RAM). A
typical development machine will be faster.

## What's genuinely implemented vs. configuration-dependent

**Fully implemented and verified against real data in this pass:**
auth/JWT/RBAC, transaction ingestion + hash-chain integrity, real
4-model fraud training + comparison, real SHAP explanations, real
behavioral baselines (full 24.4M-row IBM coverage), real Ethereum
wallet graph (local NetworkX backend), Security Center, PQC self-test
+ quantum-safe audit export/import, RAG copilot with TF-IDF retrieval
and evidence-grounded fallback.

**Configuration-dependent (real code, needs external service):**
- Live Neo4j graph backend — falls back to the local NetworkX
  implementation when `NEO4J_URI` is unset (same query interface).
- LLM-generated copilot answers — falls back to a clearly-labeled,
  non-AI evidence digest when `ANTHROPIC_API_KEY` is unset.

**Not yet done in this pass** (flagging honestly rather than silently
omitting): full pytest test suite, Windows-specific end-to-end testing
(commands above are standard and should work but weren't run on actual
Windows), research-paper artifact regeneration (confusion matrix
plots, PR/ROC curve images) against the real results above, and
frontend re-verification against this real-data backend specifically
(the frontend was built against the same API contracts, which haven't
changed, so it should work unmodified — but that assumption hasn't
been re-tested end-to-end since real data landed).

## Environment variables

See `.env.example` for the full list. Nothing here requires a paid
service to run the core system — `ANTHROPIC_API_KEY` and `NEO4J_URI`
are both optional, honestly-degrading capabilities, not requirements.
