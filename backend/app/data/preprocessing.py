"""
Preprocessing / feature engineering for the fraud model input.

Operates identically on real IEEE-CIS data and on the synthetic
stand-in — same columns in, same transformation logic, same columns
out, so pipeline mechanics validated against synthetic data carry over
unchanged to real data.

Real-data finding (not present in the synthetic generator, discovered
once real data was loaded): DeviceInfo has 1,786 distinct values in the
real dataset vs. a handful in the synthetic stand-in. One-hot encoding
it directly exploded the feature matrix to ~1,963 columns, most of them
near-singleton dummy columns contributing noise more than signal. This
module now buckets high-cardinality categoricals to their top-N most
frequent values (+ "other") — a standard, documented treatment for this
exact column on this exact dataset, not an arbitrary simplification.

Train/inference consistency: the top-N vocabulary for each bucketed
column is computed once at training time and must be persisted and
reused at inference (see app/ml/train_fraud_model.py and
app/services/fraud_service.py) — recomputing it per-request would let
a single transaction's DeviceInfo value silently redefine "top N",
which is exactly the kind of train/inference skew this project's
feature-alignment step (feature_alignment.py) exists to prevent.
"""
import numpy as np
import pandas as pd
import re

from app.data.schemas import IEEE_CIS_CATEGORICAL, IEEE_CIS_TARGET

NUMERIC_FEATURES = [
    "TransactionAmt", "card1", "card2", "card3", "card5",
    "addr1", "dist1", "dist2",
    "C1", "C2", "C3", "C4", "C5",
    "D1", "D2", "D3", "D4", "D5",
]

ENGINEERED_FEATURES = [
    "amt_log", "hour_of_day", "day_of_week",
    "email_is_anonymous_relay", "device_is_mobile", "device_missing",
]

CATEGORICAL_FEATURES = IEEE_CIS_CATEGORICAL

# Columns whose real-data cardinality is high enough to require bucketing
# before one-hot encoding. Threshold chosen from the real observed
# cardinalities (see module docstring) — P_emaildomain/R_emaildomain (~60
# each) and the M-flags/ProductCD/card4/card6 (2-5 each) don't need it.
HIGH_CARDINALITY_COLUMNS = ["DeviceInfo"]
MAX_CATEGORIES_PER_COLUMN = 20


def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """Adds derived columns. Does not drop or reorder existing columns,
    so this is safe to call before or after other cleaning steps."""
    out = df.copy()

    out["amt_log"] = np.log1p(out["TransactionAmt"].clip(lower=0))

    # TransactionDT is seconds-from-reference in the real dataset (not a
    # real timestamp) — this is the standard, documented IEEE-CIS
    # convention, not a mistake.
    seconds = out["TransactionDT"].astype(float)
    out["hour_of_day"] = ((seconds // 3600) % 24).astype(int)
    out["day_of_week"] = ((seconds // (3600 * 24)) % 7).astype(int)

    out["email_is_anonymous_relay"] = out["P_emaildomain"].fillna("").str.contains("anonymous", case=False).astype(int)
    out["device_is_mobile"] = (out["DeviceType"] == "mobile").astype(int)
    out["device_missing"] = out["DeviceType"].isna().astype(int)

    return out


def clean_missing_values(df: pd.DataFrame, numeric_medians: dict[str, float] | None = None) -> pd.DataFrame:
    """Fills missing numeric values with the median. At training time
    (numeric_medians=None), the median is computed from the batch itself
    — correct when the batch is the whole training set. At single-row
    inference time this is degenerate (the "median" of one value is
    that value; if it's NaN, filling with it is a no-op), so inference
    callers must pass the persisted training-set medians instead — same
    persisted-artifact pattern as fit_category_vocab below."""
    out = df.copy()
    for col in NUMERIC_FEATURES:
        if col in out.columns:
            fill_value = numeric_medians[col] if numeric_medians and col in numeric_medians else out[col].median()
            out[col] = out[col].fillna(fill_value)
    for col in CATEGORICAL_FEATURES:
        if col in out.columns:
            out[col] = out[col].fillna("missing")
    return out


def fit_numeric_medians(df: pd.DataFrame, columns: list[str] = NUMERIC_FEATURES) -> dict[str, float]:
    """Computes per-column medians from training data only, for reuse at
    inference time via clean_missing_values(numeric_medians=...)."""
    return {col: float(df[col].median()) for col in columns if col in df.columns}


def fit_category_vocab(df: pd.DataFrame, columns: list[str] = HIGH_CARDINALITY_COLUMNS,
                        max_categories: int = MAX_CATEGORIES_PER_COLUMN) -> dict[str, list[str]]:
    """Computes the top-N most frequent values for each high-cardinality
    column, from training data only. Call once at training time; persist
    the result (app/ml/train_fraud_model.py writes it alongside the
    feature-column list) and pass it into build_feature_matrix at
    inference time via category_vocab."""
    vocab = {}
    for col in columns:
        if col in df.columns:
            top_values = df[col].fillna("missing").value_counts().head(max_categories).index.tolist()
            vocab[col] = top_values
    return vocab


def _apply_category_vocab(df: pd.DataFrame, vocab: dict[str, list[str]]) -> pd.DataFrame:
    out = df.copy()
    for col, top_values in vocab.items():
        if col in out.columns:
            out[col] = out[col].where(out[col].isin(top_values), other="other")
    return out


def build_feature_matrix(
    df: pd.DataFrame,
    category_vocab: dict[str, list[str]] | None = None,
    numeric_medians: dict[str, float] | None = None,
) -> tuple[pd.DataFrame, pd.Series | None]:
    """Returns (X, y). y is None if the frame has no target column
    (i.e. this is being called at inference time on a single transaction,
    not during training).

    category_vocab: the fitted top-N vocabulary for high-cardinality
    columns (from fit_category_vocab). Required for correct, consistent
    behavior — if omitted, high-cardinality columns fall back to raw
    one-hot encoding (the 1,963-column explosion this exists to avoid).

    numeric_medians: the fitted per-column medians (from
    fit_numeric_medians). Required at single-row inference time — see
    clean_missing_values docstring for why computing a "median" from a
    single row is degenerate. Training and inference must use the SAME
    persisted values for both category_vocab and numeric_medians.
    """
    engineered = engineer_features(df)
    cleaned = clean_missing_values(engineered, numeric_medians=numeric_medians)

    if category_vocab:
        cleaned = _apply_category_vocab(cleaned, category_vocab)

    feature_cols = NUMERIC_FEATURES + ENGINEERED_FEATURES + CATEGORICAL_FEATURES
    feature_cols = [c for c in feature_cols if c in cleaned.columns]

    X = cleaned[feature_cols].copy()
    X = pd.get_dummies(X, columns=[c for c in CATEGORICAL_FEATURES if c in X.columns], dummy_na=False)

    # LightGBM rejects several JSON special characters in feature names
    # (discovered when real DeviceInfo values like "rv:11.0" produced
    # one-hot columns such as "DeviceInfo_rv:11.0"). Sanitizing here is a
    # pure function of the column name string — no fitted state to
    # persist — so applying it inside build_feature_matrix guarantees
    # train and inference always agree without extra bookkeeping.
    X.columns = [re.sub(r'[",\'\[\]{}:\\\\]', "_", str(c)) for c in X.columns]

    y = cleaned[IEEE_CIS_TARGET] if IEEE_CIS_TARGET in cleaned.columns else None
    return X, y
