"""
Data ingestion entrypoint.

Run: python -m scripts.ingest_data

What it does, in order:
  1. Resolves each dataset (real if the Kaggle CSV is present at
     backend/data/raw/..., otherwise the labeled synthetic fallback).
  2. IEEE-CIS: engineers features, persists a processed feature parquet
     for Phase 5's training script, and writes each row into the
     `transactions` table (hash-chain sealed, same as the API path) so
     the rest of the platform has real rows to query against.
  3. IBM: computes per-user behavioral baselines, persists them for
     Phase 7's behavioral service.
  4. Ethereum: derives the wallet graph edge/node tables, persists them
     for Phase 8's Neo4j loader.

Every persisted transaction/baseline/edge is tagged with whether it
came from real or synthetic data — nothing downstream has to guess.
"""
import logging
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import settings
from app.core.logging_config import configure_logging
from app.data import behavioral_features, ethereum_graph, loaders, preprocessing, resolver
from app.db.session import Base, SessionLocal, engine
from app.models.transaction import Transaction
from app.services.integrity_service import get_latest_hash_and_sequence, seal_transaction_with_known_previous

configure_logging()
logger = logging.getLogger("quantumfinguard.ingest")

PROCESSED_DIR = Path(settings.PROCESSED_DATA_DIR)


def _source_tag(base_name: str, is_synthetic: bool) -> str:
    return f"{base_name}_synthetic" if is_synthetic else base_name


def _json_safe_row(row: pd.Series) -> dict:
    """Converts a pandas row (with numpy scalar types and NaN) into a
    plain-Python, JSON-serializable dict for storage in
    Transaction.feature_snapshot. NaN becomes None rather than being
    silently coerced to a string or dropped."""
    out = {}
    for k, v in row.items():
        if pd.isna(v):
            out[k] = None
        elif hasattr(v, "item"):  # numpy scalar
            out[k] = v.item()
        else:
            out[k] = v
    return out


def ingest_ieee_cis(n_rows: int, write_to_db: bool, db_sample_size: int = 50_000) -> dict:
    resolved = resolver.resolve_ieee_cis(n_rows_if_synthetic=n_rows)
    df = resolved.frame
    logger.info(
        "IEEE-CIS resolved: %s rows, synthetic=%s",
        len(df), resolved.is_synthetic,
    )

    category_vocab = preprocessing.fit_category_vocab(df)
    numeric_medians = preprocessing.fit_numeric_medians(df)
    X, y = preprocessing.build_feature_matrix(df, category_vocab=category_vocab, numeric_medians=numeric_medians)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    feature_path = PROCESSED_DIR / f"ieee_cis_features{'_synthetic' if resolved.is_synthetic else ''}.parquet"
    X.assign(isFraud=y).to_parquet(feature_path, index=False)
    logger.info("Persisted processed feature matrix -> %s (%s features)", feature_path, X.shape[1])

    # DB population uses a documented, deterministic systematic sample
    # rather than all 590,540 real rows: the model is trained on the
    # FULL real dataset above and in app/ml/train_fraud_model.py (that's
    # what the research results are based on) — this sample only
    # populates the live demo/investigation database with a manageable,
    # representative set of real transactions, so the app stays fast to
    # query and to hash-chain-seal on ingestion. No randomness: every
    # Nth row, fixed stride, fully reproducible.
    db_ingest_df = df
    sampling_metadata = {"sampling_method": "none (all rows written)", "sampled_rows": len(df)}
    if write_to_db and len(df) > db_sample_size:
        stride = max(1, len(df) // db_sample_size)
        db_ingest_df = df.iloc[::stride].reset_index(drop=True)
        sampling_metadata = {
            "sampling_method": "systematic (fixed stride, deterministic, no randomness)",
            "total_rows_in_source": len(df),
            "stride": stride,
            "sampled_rows": len(db_ingest_df),
            "target_rows_requested": db_sample_size,
        }
        logger.info("DB population sampling: %s", sampling_metadata)

    written = 0
    if write_to_db:
        source_tag = _source_tag("ieee_cis", resolved.is_synthetic)
        db = SessionLocal()
        try:
            previous_hash, next_seq = get_latest_hash_and_sequence(db)
            for _, row in db_ingest_df.iterrows():
                txn = Transaction(
                    external_ref=str(row["TransactionID"]),
                    customer_id=f"card_{row['card1']}",
                    merchant_id=f"product_{row['ProductCD']}",
                    merchant_category=str(row["ProductCD"]),
                    amount=float(row["TransactionAmt"]),
                    currency="USD",
                    timestamp=pd.Timestamp("2026-01-01") + pd.to_timedelta(int(row["TransactionDT"]), unit="s"),
                    device_type=row.get("DeviceType") if pd.notna(row.get("DeviceType")) else None,
                    card_type=row.get("card6") if pd.notna(row.get("card6")) else None,
                    country="US",
                    source_dataset=source_tag,
                    feature_snapshot=_json_safe_row(row),
                )
                previous_hash = seal_transaction_with_known_previous(txn, previous_hash, next_seq)
                next_seq += 1
                db.add(txn)
                written += 1
                if written % 500 == 0:
                    db.commit()
            db.commit()
        finally:
            db.close()
        logger.info("Wrote %s transactions to DB with source_dataset='%s'", written, source_tag)

    return {
        "rows": len(df),
        "is_synthetic": resolved.is_synthetic,
        "feature_columns": X.shape[1],
        "fraud_rate": float(y.mean()) if y is not None else None,
        "transactions_written": written,
        "db_sampling": sampling_metadata,
        "feature_path": str(feature_path),
    }


def ingest_ibm_credit(n_rows: int, write_to_db: bool, db_sample_size: int = 50_000) -> dict:
    is_real = loaders.real_data_available()["ibm_credit"]
    suffix = "" if is_real else "_synthetic"
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    if is_real:
        # The real file is 24.4M rows / ~2.35GB — cannot go through
        # resolver.resolve_ibm_credit() (which would call
        # get_ibm_credit_frame() and try to load it all into memory at
        # once). Baselines are computed by streaming the ENTIRE file in
        # chunks (full-dataset statistics, not a sample); DB population
        # uses a separate, documented systematic sample.
        logger.info("IBM Credit: real data detected, streaming full file for baselines (this takes a few minutes)")
        user_baselines, user_stream_stats = behavioral_features.compute_user_baselines_streaming(
            loaders.stream_ibm_credit_chunks()
        )
        merchant_baselines, merchant_stream_stats = behavioral_features.compute_merchant_baselines_streaming(
            loaders.stream_ibm_credit_chunks()
        )
        logger.info("Streamed %s real rows for user baselines, %s for merchant baselines",
                    user_stream_stats["total_rows_processed"], merchant_stream_stats["total_rows_processed"])

        db_ingest_df, sample_metadata = loaders.get_ibm_credit_sample_frame(target_rows=db_sample_size)
        total_row_count = user_stream_stats["total_rows_processed"]
        fraud_rate = None  # not computed from the full stream in this pass; see sample-based rate below if needed
    else:
        resolved = resolver.resolve_ibm_credit(n_rows_if_synthetic=n_rows)
        df = resolved.frame
        logger.info("IBM Credit resolved: %s rows, synthetic=%s", len(df), resolved.is_synthetic)
        user_baselines = behavioral_features.compute_user_baselines(df)
        merchant_baselines = behavioral_features.compute_merchant_baselines(df)
        db_ingest_df = df
        sample_metadata = {"sampling_method": "none (all rows written, small synthetic dataset)", "sampled_rows": len(df)}
        total_row_count = len(df)
        fraud_rate = float((df["Is Fraud?"] == "Yes").mean())

    user_path = PROCESSED_DIR / f"ibm_user_baselines{suffix}.parquet"
    user_baselines.to_parquet(user_path, index=False)
    logger.info("Persisted %s user baselines (min history enforced) -> %s", len(user_baselines), user_path)

    merchant_path = PROCESSED_DIR / f"ibm_merchant_baselines{suffix}.parquet"
    merchant_baselines.to_parquet(merchant_path, index=False)
    logger.info("Persisted %s merchant (MCC) baselines -> %s", len(merchant_baselines), merchant_path)

    written = 0
    if write_to_db:
        # IBM's "User" ID space has no real linkage to IEEE-CIS's card1-based
        # customer_id space — they are separate Kaggle datasets with
        # unrelated synthetic identifiers. Writing IBM rows as their own
        # transactions (rather than trying to attach IBM baselines to
        # IEEE-CIS transactions) is what makes behavioral context
        # something that can honestly exist for *some* real transaction
        # in the system, instead of a baseline table with nothing valid
        # to compare against.
        source_tag = _source_tag("ibm_credit", not is_real)
        db = SessionLocal()
        try:
            previous_hash, next_seq = get_latest_hash_and_sequence(db)
            for _, row in db_ingest_df.iterrows():
                try:
                    ts = pd.Timestamp(year=int(row["Year"]), month=int(row["Month"]), day=int(row["Day"]))
                    hour, minute = str(row["Time"]).split(":")
                    ts = ts + pd.Timedelta(hours=int(hour), minutes=int(minute))
                except (ValueError, TypeError):
                    ts = pd.Timestamp("2026-01-01")

                amount = float(str(row["Amount"]).replace("$", ""))
                txn = Transaction(
                    customer_id=f"ibm_user_{row['User']}",
                    merchant_id=f"ibm_mcc_{row['MCC']}",
                    merchant_category=str(row["MCC"]),
                    amount=amount,
                    currency="USD",
                    timestamp=ts,
                    device_type=None,
                    card_type=str(row.get("Use Chip")) if pd.notna(row.get("Use Chip")) else None,
                    country="US",
                    source_dataset=source_tag,
                    feature_snapshot=_json_safe_row(row),
                )
                previous_hash = seal_transaction_with_known_previous(txn, previous_hash, next_seq)
                next_seq += 1
                db.add(txn)
                written += 1
                if written % 500 == 0:
                    db.commit()
            db.commit()
        finally:
            db.close()
        logger.info("Wrote %s IBM-sourced transactions to DB with source_dataset='%s'", written, source_tag)

    return {
        "rows": total_row_count,
        "is_synthetic": not is_real,
        "users_with_sufficient_history": len(user_baselines),
        "merchants_with_sufficient_history": len(merchant_baselines),
        "transactions_written": written,
        "db_sampling": sample_metadata,
        "user_baseline_path": str(user_path),
        "merchant_baseline_path": str(merchant_path),
    }


def ingest_ethereum(n_addresses: int) -> dict:
    resolved = resolver.resolve_ethereum(n_addresses_if_synthetic=n_addresses)
    df = resolved.frame
    logger.info("Ethereum resolved: %s addresses, synthetic=%s", len(df), resolved.is_synthetic)

    nodes = ethereum_graph.build_node_table(df)
    edges = ethereum_graph.derive_edges(df)

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    suffix = "_synthetic" if resolved.is_synthetic else ""
    nodes_path = PROCESSED_DIR / f"ethereum_nodes{suffix}.parquet"
    edges_path = PROCESSED_DIR / f"ethereum_edges{suffix}.parquet"
    nodes.to_parquet(nodes_path, index=False)
    edges.to_parquet(edges_path, index=False)
    logger.info("Persisted graph: %s nodes, %s edges -> %s / %s", len(nodes), len(edges), nodes_path, edges_path)

    return {
        "addresses": len(df),
        "is_synthetic": resolved.is_synthetic,
        "nodes": len(nodes),
        "edges": len(edges),
        "flagged_addresses": int(df["FLAG"].sum()),
    }


def main():
    if settings.ENVIRONMENT == "local":
        Base.metadata.create_all(bind=engine)

    logger.info("=== QuantumFinGuard data ingestion starting ===")
    ieee_result = ingest_ieee_cis(n_rows=5000, write_to_db=True)
    ibm_result = ingest_ibm_credit(n_rows=5000, write_to_db=True)
    eth_result = ingest_ethereum(n_addresses=800)

    print("\n=== INGESTION SUMMARY ===")
    for name, result in [("IEEE-CIS", ieee_result), ("IBM Credit", ibm_result), ("Ethereum", eth_result)]:
        tag = "SYNTHETIC (labeled)" if result["is_synthetic"] else "REAL"
        print(f"{name}: {tag} — {result}")


if __name__ == "__main__":
    main()
