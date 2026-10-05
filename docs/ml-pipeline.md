# Machine Learning Pipeline

## Scope

This document covers the fraud/risk model only. **The reported
results apply to IEEE-CIS and are not transferable to IBM or Ethereum**
— those datasets feed different capabilities (behavioral baselines,
graph analysis respectively) that don't produce a comparable
classification metric.

## Preprocessing (`app/data/preprocessing.py`)

1. Feature engineering: log-transformed amount, hour-of-day/day-of-week
   derived from `TransactionDT`, email-domain risk flag, device-type
   flags.
2. Missing-value handling: numeric columns filled with the **training
   set's** median (persisted and reused at inference — see below);
   categorical columns filled with the literal string `"missing"`.
3. High-cardinality category bucketing: `DeviceInfo` (1,786 real
   distinct values) is bucketed to its top-20 most frequent values in
   the training data + an `"other"` bucket, fit once and persisted.
   Without this, one-hot encoding produced a 1,963-column matrix,
   discovered when real data was first loaded (the synthetic stand-in
   used during earlier development had far lower cardinality and never
   surfaced this).
4. One-hot encoding, then column-name sanitization (LightGBM rejects
   `":"`, `","`, `"`, etc. in feature names — real `DeviceInfo` values
   like `"rv:11.0"` triggered this).

**Train/inference consistency**: the category vocabulary and numeric
medians are both *fit once, at training time, from training data only*,
then persisted (`app/ml_artifacts/{model}.category_vocab.json`,
`{model}.numeric_medians.json`) and reused identically at inference.
This matters specifically because a single-row inference call has no
meaningful "median of one value" or "top-20 categories of one row" —
recomputing either at inference time would be either degenerate or
would let one transaction silently redefine the vocabulary.

## Models trained and compared

Logistic Regression (scaled, `class_weight="balanced"`), Random
Forest (`class_weight="balanced_subsample"`), XGBoost
(`scale_pos_weight` set from the real class ratio), LightGBM
(`class_weight="balanced"`). All four trained on an identical
stratified 70/10/20 train/val/test split of the full real 590,540-row
IEEE-CIS dataset (`random_state=42` throughout, for reproducibility).

**Selection metric: validation PR-AUC**, not ROC-AUC and not accuracy
— standard practice for ~3.5% class imbalance, where ROC-AUC is easy
to inflate and accuracy is close to meaningless (a model predicting
"never fraud" scores 96.5% accuracy).

## Real results (reproducible — see "How to reproduce" below)

| Model | Val PR-AUC | Val ROC-AUC |
|---|---|---|
| **LightGBM (selected)** | 0.582 | — |
| Logistic Regression | 0.145 | 0.770 |
| Random Forest | 0.420 | 0.884 |
| XGBoost | 0.435 | 0.877 |

**Held-out test set (never used for model selection):**

| Metric | Value |
|---|---|
| PR-AUC | 0.556 |
| ROC-AUC | 0.923 |
| Precision (at 0.5 threshold) | 0.201 |
| Recall (at 0.5 threshold) | 0.809 |
| F1 | 0.322 |
| Confusion matrix | TN=100,708, FP=13,269, FN=788, TP=3,344 |

Full metrics, including the per-model validation comparison, are
served live at `GET /api/v1/fraud/models/metrics` — this table is not
a static copy that can drift from the actual artifact; it's read
directly from the persisted `metrics.json` written by the training run.

**Interpretation**: at the default 0.5 probability threshold, the
model catches 80.9% of real fraud (recall) at the cost of a high false
positive rate (precision 20.1%) — a deliberate, adjustable trade-off
for a fraud-screening use case where missing fraud is typically costlier
than a false alarm an analyst can dismiss. ROC-AUC of 0.923 is a
credible, in-line-with-public-benchmarks result for this well-known
dataset with this feature set.

## SHAP explainability (`app/services/xai_service.py`)

`shap.TreeExplainer` for the LightGBM model (this project's
`ShapExplainerService` selects `LinearExplainer` automatically if a
future retrain picks Logistic Regression instead — both paths are
implemented, not just the currently-active one). Background sample:
100 rows from the real training distribution. Returns the top 8
features by absolute contribution, each with its signed contribution
and direction (`increases_risk` / `decreases_risk`).

## How to reproduce

```
python -m scripts.ingest_data       # ~5 min with the real IBM file
python -m app.ml.train_fraud_model  # ~3 min on the full real IEEE-CIS data
```

Both commands are deterministic (`random_state=42` throughout); the
same real input files will reproduce the same split, the same trained
model, and the same reported metrics.
