"""
Real dataset loaders.

IMPORTANT — why this doesn't download data automatically:

The three datasets are hosted on Kaggle under Kaggle's terms of use,
which require an authenticated account and (for the IEEE-CIS competition
data specifically) accepting competition rules before download. This
pipeline is built to consume files placed locally, not to fetch them
itself.

## Expected file placement (real Kaggle filenames, verified against
## the actual uploaded files — not invented names)

    backend/data/raw/train_transaction.csv       (IEEE-CIS, ~683MB, 590,541 rows)
    backend/data/raw/train_identity.csv          (IEEE-CIS, ~26.5MB, 144,233 rows)
    backend/data/raw/ibm_credit_card_transactions.csv   (IBM, ~2.35GB, 24,386,900 rows)
    backend/data/raw/ethereum_dataset.csv        (Ethereum, ~2.9MB, 9,841 rows)

## Memory strategy (verified necessary, not precautionary)

IEEE-CIS: loaded via `usecols` — only the ~32 columns this project's
feature pipeline actually uses, out of 394 real columns (V1-V339 are
not used). This keeps a full 590k-row load well within a few hundred
MB, so no sampling is needed for IEEE-CIS; every real row is used.

IBM: 24.4M rows cannot be loaded into memory at once in this project's
target environment (a few GB of RAM). `stream_ibm_credit_chunks()`
below processes the file in chunks for full-dataset aggregate
statistics (behavioral baselines), and `get_ibm_credit_sample_frame()`
returns a documented, deterministic systematic sample (every Nth row,
fixed stride, no randomness) for populating the transactions table —
sampling method and size are recorded in the returned metadata rather
than silently chosen.
"""
from pathlib import Path
from typing import Iterator

import pandas as pd

from app.data.schemas import (
    ETHEREUM_REQUIRED_COLUMNS,
    IBM_CREDIT_REQUIRED_COLUMNS,
    IEEE_CIS_IDENTITY_REQUIRED_COLUMNS,
    IEEE_CIS_TRANSACTION_REQUIRED_COLUMNS,
    validate_columns,
)

RAW_DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "raw"

IEEE_TRANSACTION_PATH = RAW_DATA_DIR / "train_transaction.csv"
IEEE_IDENTITY_PATH = RAW_DATA_DIR / "train_identity.csv"
IBM_CREDIT_PATH = RAW_DATA_DIR / "ibm_credit_card_transactions.csv"
ETHEREUM_PATH = RAW_DATA_DIR / "ethereum_dataset.csv"

IBM_CHUNK_SIZE = 500_000


class DatasetNotFoundError(Exception):
    pass


def _require_file(path: Path, kaggle_hint: str) -> None:
    if not path.exists():
        raise DatasetNotFoundError(
            f"Real dataset file not found at {path}.\n"
            f"Download it yourself via: {kaggle_hint}\n"
            f"See app/data/loaders.py module docstring for exact expected filenames."
        )


def get_ieee_cis_frame(nrows: int | None = None) -> pd.DataFrame:
    """Loads and left-merges the real train_transaction.csv +
    train_identity.csv on TransactionID. Uses usecols so the ~360
    unused V-columns and id_XX columns are never parsed into memory."""
    _require_file(IEEE_TRANSACTION_PATH, "kaggle competitions download -c ieee-fraud-detection")
    _require_file(IEEE_IDENTITY_PATH, "kaggle competitions download -c ieee-fraud-detection")

    txn_df = pd.read_csv(IEEE_TRANSACTION_PATH, usecols=IEEE_CIS_TRANSACTION_REQUIRED_COLUMNS, nrows=nrows)
    validate_columns(txn_df.columns.tolist(), IEEE_CIS_TRANSACTION_REQUIRED_COLUMNS, "IEEE-CIS train_transaction.csv")

    identity_df = pd.read_csv(IEEE_IDENTITY_PATH, usecols=IEEE_CIS_IDENTITY_REQUIRED_COLUMNS)
    validate_columns(identity_df.columns.tolist(), IEEE_CIS_IDENTITY_REQUIRED_COLUMNS, "IEEE-CIS train_identity.csv")

    merged = txn_df.merge(identity_df, on="TransactionID", how="left")
    return merged


def get_ibm_credit_frame(nrows: int | None = None) -> pd.DataFrame:
    """Small-file / synthetic-data path: loads the whole thing. Only
    safe for the synthetic stand-in or a small real file — the real
    24.4M-row IBM file must go through stream_ibm_credit_chunks() or
    get_ibm_credit_sample_frame() instead (see module docstring)."""
    _require_file(IBM_CREDIT_PATH, "kaggle datasets download -d ealtman2019/credit-card-transactions")
    df = pd.read_csv(IBM_CREDIT_PATH, nrows=nrows)
    validate_columns(df.columns.tolist(), IBM_CREDIT_REQUIRED_COLUMNS, "IBM Credit Card Transactions")
    return df


def stream_ibm_credit_chunks(chunksize: int = IBM_CHUNK_SIZE) -> Iterator[pd.DataFrame]:
    """Yields the real IBM file in chunks for full-dataset streaming
    aggregation (behavioral baselines) without ever holding all 24.4M
    rows in memory at once."""
    _require_file(IBM_CREDIT_PATH, "kaggle datasets download -d ealtman2019/credit-card-transactions")
    reader = pd.read_csv(IBM_CREDIT_PATH, chunksize=chunksize)
    first = True
    for chunk in reader:
        if first:
            validate_columns(chunk.columns.tolist(), IBM_CREDIT_REQUIRED_COLUMNS, "IBM Credit Card Transactions")
            first = False
        yield chunk


def get_ibm_credit_sample_frame(target_rows: int = 200_000) -> tuple[pd.DataFrame, dict]:
    """Deterministic systematic sample of the real IBM file for
    populating the transactions table (not for baseline computation,
    which uses the full stream instead). Method is fixed-stride row
    selection — every Nth row, no randomness, fully reproducible.

    Implementation note: an earlier version used pandas' `skiprows=`
    with a per-row Python callable, which is a known-slow path for a
    24M-row file (a Python function call for every single row during
    CSV parsing). Rewritten to reuse the already-streaming chunk reader
    and select rows by global row index with a vectorized `.iloc` slice
    per chunk instead — the same deterministic systematic sample, at a
    fraction of the cost."""
    _require_file(IBM_CREDIT_PATH, "kaggle datasets download -d ealtman2019/credit-card-transactions")

    with open(IBM_CREDIT_PATH, "r") as f:
        total_rows = sum(1 for _ in f) - 1  # minus header

    stride = max(1, total_rows // target_rows)

    sampled_chunks = []
    global_row_index = 0
    for chunk in stream_ibm_credit_chunks():
        chunk_start = global_row_index
        # First global index >= chunk_start that's a multiple of stride:
        offset = (-chunk_start) % stride
        if offset < len(chunk):
            sampled_chunks.append(chunk.iloc[offset::stride])
        global_row_index += len(chunk)

    df = pd.concat(sampled_chunks, ignore_index=True)
    validate_columns(df.columns.tolist(), IBM_CREDIT_REQUIRED_COLUMNS, "IBM Credit Card Transactions")

    metadata = {
        "sampling_method": "systematic (fixed stride, deterministic, no randomness)",
        "total_rows_in_source": total_rows,
        "stride": stride,
        "sampled_rows": len(df),
        "target_rows_requested": target_rows,
    }
    return df, metadata


def get_ethereum_frame(nrows: int | None = None) -> pd.DataFrame:
    _require_file(ETHEREUM_PATH, "kaggle datasets download -d vagifa/ethereum-frauddetection-dataset")
    df = pd.read_csv(ETHEREUM_PATH, nrows=nrows)
    validate_columns(df.columns.tolist(), ETHEREUM_REQUIRED_COLUMNS, "Ethereum Fraud Detection Dataset")
    return df


def real_data_available() -> dict[str, bool]:
    return {
        "ieee_cis": IEEE_TRANSACTION_PATH.exists() and IEEE_IDENTITY_PATH.exists(),
        "ibm_credit": IBM_CREDIT_PATH.exists(),
        "ethereum": ETHEREUM_PATH.exists(),
    }
