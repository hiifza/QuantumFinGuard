"""
Behavioral baseline computation.

Turns raw IBM Credit Card Transactions rows into per-user statistical
baselines (mean/stddev of amount, typical hour, typical merchant
category) — the actual data this project's BehavioralService (Phase 3)
will consume once wired up in Phase 7. This module is the real
computation; app/services/behavioral_service.py's
NoBaselineBehavioralService is what it replaces once Phase 7 connects
this to the API layer.

Streaming variants (added once the real 24.4M-row IBM file was
available): compute_user_baselines/compute_merchant_baselines above
assume the whole frame fits in memory, which is true for the synthetic
stand-in but not for the real file. The _streaming versions below
process the file in chunks, accumulating per-user/per-merchant running
sums (count, sum, sum-of-squares) — a small amount of state (bounded by
the number of distinct users/merchants, not the number of rows) — and
finalize mean/stddev only after seeing every real row. This is full-
dataset statistics, not a sample: every one of the 24.4M rows
contributes to the baselines, just without ever holding all of them in
memory at once.
"""
import pandas as pd

from app.data.schemas import IBM_CREDIT_TARGET


def _parse_amount(series: pd.Series) -> pd.Series:
    return series.astype(str).str.replace("$", "", regex=False).astype(float)


def _finalize_streaming_stats(accum: dict, group_col_name: str, min_history: int, extra_col_name: str) -> pd.DataFrame:
    rows = []
    for key, s in accum.items():
        n = s["count"]
        if n < min_history:
            continue
        mean = s["sum"] / n
        variance = max(0.0, (s["sum_sq"] / n) - (mean ** 2))
        rows.append({
            group_col_name: key,
            "transaction_count": n,
            "amount_mean": mean,
            "amount_stddev": variance ** 0.5,
            extra_col_name: len(s["extra_set"]),
            "historical_fraud_rate": (s["fraud_count"] / n) if n else 0.0,
        })
    return pd.DataFrame(rows)


def compute_user_baselines_streaming(chunk_iterator, min_history: int = 20) -> tuple[pd.DataFrame, dict]:
    """Full-dataset streaming equivalent of compute_user_baselines.
    Returns (baselines_df, stats) where stats reports how many rows were
    actually processed — real evidence the full file was used, not an
    assumption."""
    accum: dict = {}
    total_rows = 0
    for chunk in chunk_iterator:
        total_rows += len(chunk)
        amounts = _parse_amount(chunk["Amount"])
        is_fraud = (chunk[IBM_CREDIT_TARGET] == "Yes").astype(int) if IBM_CREDIT_TARGET in chunk.columns else pd.Series(0, index=chunk.index)
        for user, amount, city, fraud in zip(chunk["User"], amounts, chunk["Merchant City"], is_fraud):
            s = accum.setdefault(user, {"count": 0, "sum": 0.0, "sum_sq": 0.0, "extra_set": set(), "fraud_count": 0})
            s["count"] += 1
            s["sum"] += amount
            s["sum_sq"] += amount * amount
            s["extra_set"].add(city)
            s["fraud_count"] += int(fraud)

    baselines = _finalize_streaming_stats(accum, "User", min_history, "distinct_merchant_cities")
    stats = {"total_rows_processed": total_rows, "distinct_users_seen": len(accum), "users_with_sufficient_history": len(baselines)}
    return baselines, stats


def compute_merchant_baselines_streaming(chunk_iterator, min_history: int = 20) -> tuple[pd.DataFrame, dict]:
    """Full-dataset streaming equivalent of compute_merchant_baselines,
    grouped by MCC."""
    accum: dict = {}
    total_rows = 0
    for chunk in chunk_iterator:
        total_rows += len(chunk)
        amounts = _parse_amount(chunk["Amount"])
        is_fraud = (chunk[IBM_CREDIT_TARGET] == "Yes").astype(int) if IBM_CREDIT_TARGET in chunk.columns else pd.Series(0, index=chunk.index)
        for mcc, amount, user, fraud in zip(chunk["MCC"], amounts, chunk["User"], is_fraud):
            s = accum.setdefault(mcc, {"count": 0, "sum": 0.0, "sum_sq": 0.0, "extra_set": set(), "fraud_count": 0})
            s["count"] += 1
            s["sum"] += amount
            s["sum_sq"] += amount * amount
            s["extra_set"].add(user)
            s["fraud_count"] += int(fraud)

    baselines = _finalize_streaming_stats(accum, "MCC", min_history, "distinct_users")
    stats = {"total_rows_processed": total_rows, "distinct_mccs_seen": len(accum), "merchants_with_sufficient_history": len(baselines)}
    return baselines, stats


def compute_user_baselines(df: pd.DataFrame, min_history: int = 20) -> pd.DataFrame:
    """One row per user with enough history to form a meaningful baseline.
    Users below min_history are dropped, not zero-filled — matching the
    project rule that "insufficient history" must be an explicit state,
    not a silently fabricated baseline."""
    work = df.copy()
    work["amount_numeric"] = _parse_amount(work["Amount"])
    work["hour"] = work["Time"].astype(str).str.split(":").str[0].astype(float)
    work["is_fraud_label"] = (work[IBM_CREDIT_TARGET] == "Yes").astype(int) if IBM_CREDIT_TARGET in work.columns else 0

    grouped = work.groupby("User").agg(
        transaction_count=("amount_numeric", "count"),
        amount_mean=("amount_numeric", "mean"),
        amount_stddev=("amount_numeric", "std"),
        typical_hour=("hour", "median"),
        distinct_merchant_cities=("Merchant City", "nunique"),
        historical_fraud_rate=("is_fraud_label", "mean"),
    ).reset_index()

    grouped["amount_stddev"] = grouped["amount_stddev"].fillna(0.0)
    return grouped[grouped["transaction_count"] >= min_history].reset_index(drop=True)


def compute_merchant_baselines(df: pd.DataFrame, min_history: int = 20) -> pd.DataFrame:
    """Same idea as compute_user_baselines but grouped by merchant
    category (MCC) rather than user — the merchant-level counterpart
    described in the project's behavioral analytics scope."""
    work = df.copy()
    work["amount_numeric"] = _parse_amount(work["Amount"])
    work["is_fraud_label"] = (work[IBM_CREDIT_TARGET] == "Yes").astype(int) if IBM_CREDIT_TARGET in work.columns else 0

    grouped = work.groupby("MCC").agg(
        transaction_count=("amount_numeric", "count"),
        amount_mean=("amount_numeric", "mean"),
        amount_stddev=("amount_numeric", "std"),
        distinct_users=("User", "nunique"),
        historical_fraud_rate=("is_fraud_label", "mean"),
    ).reset_index()

    grouped["amount_stddev"] = grouped["amount_stddev"].fillna(0.0)
    return grouped[grouped["transaction_count"] >= min_history].reset_index(drop=True)


def compute_deviation(observed_amount: float, baseline_row: pd.Series) -> dict:
    """The actual sigma-deviation calculation the BehavioralContext
    signals (Phase 3 dataclass) are built from."""
    mean = float(baseline_row["amount_mean"])
    stddev = float(baseline_row["amount_stddev"]) or 1e-6  # avoid div-by-zero for near-constant spenders
    sigma = (observed_amount - mean) / stddev
    return {
        "observed_value": observed_amount,
        "baseline_mean": mean,
        "baseline_stddev": stddev,
        "deviation_sigma": round(sigma, 2),
        "is_unusual": abs(sigma) > 2.5,
    }
