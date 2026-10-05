# Fraud/Risk Model Status

QuantumFinGuard's fraud/risk model was trained and compared across four
candidates: Logistic Regression, Random Forest, XGBoost, and LightGBM,
using precision, recall, F1, ROC-AUC, and PR-AUC (not accuracy alone,
which is misleading for the severe class imbalance typical of fraud
data).

## Important limitation: training data

**The model currently in production was trained on labeled-synthetic
data, not the real IEEE-CIS Fraud Detection dataset.** The real Kaggle
dataset requires an authenticated Kaggle account and has not yet been
downloaded into this environment. A schema-faithful synthetic data
generator (`app/data/synthetic_generator.py`) produces structurally
identical data so the ML pipeline could be built and tested end-to-end,
but every synthetic-derived database record is explicitly tagged with a
`_synthetic` suffix on its `source_dataset` field, and predictions
report which model/data version produced them.

Any risk score, prediction, or SHAP explanation currently returned by
this system should be understood as a demonstration of a working
pipeline, not a validated fraud-detection result. Real IEEE-CIS
training and evaluation is pending.

## Selected model

Logistic Regression was selected (by validation PR-AUC) over the
tree-based candidates in the most recent training run. Full comparison
metrics are available at `GET /api/v1/fraud/models/metrics`.

## Explainability

SHAP (`shap.LinearExplainer` for the current linear model;
`shap.TreeExplainer` is used automatically if a tree-based model is
selected in a future retrain) provides per-transaction feature
contributions at `POST /api/v1/fraud/transactions/{id}/score`.

## Dataset scope limitation

The fraud model and its SHAP explainer only work on transactions
sourced from the IEEE-CIS dataset (`source_dataset` starting with
`ieee_cis`). Transactions sourced from IBM Credit Card Transactions
data have a different, incompatible feature schema and will return an
explicit "wrong dataset" error rather than a fabricated score.
