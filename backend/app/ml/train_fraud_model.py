"""
Fraud/risk model training pipeline (Phase 5).

Trains and honestly compares four supervised classifiers on the
resolved IEEE-CIS data (real if available, labeled-synthetic
otherwise — see app/data/resolver.py), under explicit class-imbalance
handling, and evaluates on the metrics appropriate for a severely
imbalanced classification problem: precision, recall, F1, ROC-AUC,
PR-AUC, and the confusion matrix — never accuracy alone.

Run: python -m app.ml.train_fraud_model
"""
import json
import logging
import sys
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score, confusion_matrix, f1_score,
    precision_score, recall_score, roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.core.config import settings
from app.core.logging_config import configure_logging
from app.data import preprocessing, resolver
from app.ml.feature_alignment import save_feature_columns

configure_logging()
logger = logging.getLogger("quantumfinguard.train")

ARTIFACT_DIR = Path(settings.MODEL_ARTIFACT_DIR)
RANDOM_STATE = 42
TEST_SIZE = 0.2
VAL_SIZE = 0.125  # of the remaining 80% -> 10% of total


def load_training_frame(n_rows: int = 5000) -> tuple[pd.DataFrame, bool]:
    resolved = resolver.resolve_ieee_cis(n_rows_if_synthetic=n_rows)
    return resolved.frame, resolved.is_synthetic


def build_splits(df: pd.DataFrame):
    category_vocab = preprocessing.fit_category_vocab(df)
    numeric_medians = preprocessing.fit_numeric_medians(df)
    X, y = preprocessing.build_feature_matrix(df, category_vocab=category_vocab, numeric_medians=numeric_medians)
    X_train, X_temp, y_train, y_temp = train_test_split(
        X, y, test_size=TEST_SIZE + VAL_SIZE, stratify=y, random_state=RANDOM_STATE,
    )
    relative_val = VAL_SIZE / (TEST_SIZE + VAL_SIZE)
    X_val, X_test, y_val, y_test = train_test_split(
        X_temp, y_temp, test_size=(1 - relative_val), stratify=y_temp, random_state=RANDOM_STATE,
    )
    return X_train, X_val, X_test, y_train, y_val, y_test, category_vocab, numeric_medians


def evaluate(model, X_test, y_test, threshold: float = 0.5) -> dict:
    proba = model.predict_proba(X_test)[:, 1]
    preds = (proba >= threshold).astype(int)

    cm = confusion_matrix(y_test, preds, labels=[0, 1])
    tn, fp, fn, tp = cm.ravel()

    return {
        "precision": float(precision_score(y_test, preds, zero_division=0)),
        "recall": float(recall_score(y_test, preds, zero_division=0)),
        "f1": float(f1_score(y_test, preds, zero_division=0)),
        "roc_auc": float(roc_auc_score(y_test, proba)),
        "pr_auc": float(average_precision_score(y_test, proba)),
        "confusion_matrix": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
        "positive_rate_in_test": float(y_test.mean()),
        "test_size": int(len(y_test)),
    }


def train_all_models(X_train, y_train, X_val, y_val):
    """Returns {name: (fitted_model, val_metrics)}. LightGBM/XGBoost are
    imported lazily and skipped with an explicit note if unavailable,
    rather than silently omitted — matches the project rule to expose
    which models are actually available."""
    results = {}
    skipped = {}

    # --- Logistic Regression (scaled, calibrated baseline) ---
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_val_scaled = scaler.transform(X_val)
    lr = LogisticRegression(max_iter=2000, class_weight="balanced", random_state=RANDOM_STATE)
    t0 = time.time()
    lr.fit(X_train_scaled, y_train)
    logger.info("Logistic Regression trained in %.2fs", time.time() - t0)
    results["logistic_regression"] = {
        "model": lr, "scaler": scaler,
        "val_metrics": evaluate(_ScaledModel(lr, scaler), X_val, y_val),
    }

    # --- Random Forest ---
    rf = RandomForestClassifier(
        n_estimators=300, max_depth=12, class_weight="balanced_subsample",
        n_jobs=-1, random_state=RANDOM_STATE,
    )
    t0 = time.time()
    rf.fit(X_train, y_train)
    logger.info("Random Forest trained in %.2fs", time.time() - t0)
    results["random_forest"] = {"model": rf, "scaler": None, "val_metrics": evaluate(rf, X_val, y_val)}

    # --- XGBoost ---
    try:
        from xgboost import XGBClassifier
        pos = max(int(y_train.sum()), 1)
        neg = len(y_train) - pos
        xgb = XGBClassifier(
            n_estimators=300, max_depth=6, learning_rate=0.08,
            scale_pos_weight=neg / pos, eval_metric="logloss",
            random_state=RANDOM_STATE, n_jobs=-1,
        )
        t0 = time.time()
        xgb.fit(X_train, y_train)
        logger.info("XGBoost trained in %.2fs", time.time() - t0)
        results["xgboost"] = {"model": xgb, "scaler": None, "val_metrics": evaluate(xgb, X_val, y_val)}
    except ImportError as exc:
        skipped["xgboost"] = f"import failed: {exc}"
        logger.warning("XGBoost unavailable, skipping: %s", exc)

    # --- LightGBM ---
    try:
        from lightgbm import LGBMClassifier
        lgbm = LGBMClassifier(
            n_estimators=300, max_depth=8, learning_rate=0.08,
            class_weight="balanced", random_state=RANDOM_STATE, n_jobs=-1, verbosity=-1,
        )
        t0 = time.time()
        lgbm.fit(X_train, y_train)
        logger.info("LightGBM trained in %.2fs", time.time() - t0)
        results["lightgbm"] = {"model": lgbm, "scaler": None, "val_metrics": evaluate(lgbm, X_val, y_val)}
    except ImportError as exc:
        skipped["lightgbm"] = f"import failed: {exc}"
        logger.warning("LightGBM unavailable, skipping: %s", exc)

    return results, skipped


class _ScaledModel:
    """Wraps a model that needs its input scaled (Logistic Regression) so
    evaluate() can call predict_proba(X) uniformly across all models."""
    def __init__(self, model, scaler):
        self.model, self.scaler = model, scaler

    def predict_proba(self, X):
        return self.model.predict_proba(self.scaler.transform(X))


def select_best(results: dict) -> str:
    """PR-AUC is the selection metric: with a ~3.5% positive rate, ROC-AUC
    is easy to inflate and PR-AUC is the standard recommendation for
    severely imbalanced classification (consistent with Section II-A of
    the accompanying paper)."""
    return max(results, key=lambda name: results[name]["val_metrics"]["pr_auc"])


def main():
    logger.info("=== QuantumFinGuard fraud model training starting ===")
    df, is_synthetic = load_training_frame(n_rows=5000)
    logger.info("Training data resolved: %s rows, synthetic=%s, fraud_rate=%.4f", len(df), is_synthetic, df["isFraud"].mean())

    X_train, X_val, X_test, y_train, y_val, y_test, category_vocab, numeric_medians = build_splits(df)
    logger.info("Split sizes -> train: %s, val: %s, test: %s", len(X_train), len(X_val), len(X_test))
    logger.info("Category vocab (high-cardinality columns bucketed to top-N): %s",
                {k: len(v) for k, v in category_vocab.items()})

    results, skipped = train_all_models(X_train, y_train, X_val, y_val)
    if not results:
        raise RuntimeError("No models trained successfully — aborting rather than persisting nothing.")

    best_name = select_best(results)
    best = results[best_name]
    logger.info("Best model by validation PR-AUC: %s (PR-AUC=%.4f)", best_name, best["val_metrics"]["pr_auc"])

    # Final, honest test-set evaluation of the selected model only —
    # val set was used for selection, so test metrics are the reported number.
    if best["scaler"] is not None:
        test_metrics = evaluate(_ScaledModel(best["model"], best["scaler"]), X_test, y_test)
    else:
        test_metrics = evaluate(best["model"], X_test, y_test)
    logger.info("Test-set metrics for selected model (%s): %s", best_name, test_metrics)

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    model_version = f"{best_name}-{'synthetic' if is_synthetic else 'real'}-v1"

    model_path = ARTIFACT_DIR / f"{model_version}.joblib"
    joblib.dump(best["model"], model_path)

    scaler_path = None
    if best["scaler"] is not None:
        scaler_path = ARTIFACT_DIR / f"{model_version}.scaler.joblib"
        joblib.dump(best["scaler"], scaler_path)

    columns_path = ARTIFACT_DIR / f"{model_version}.columns.json"
    save_feature_columns(list(X_train.columns), columns_path)

    vocab_path = ARTIFACT_DIR / f"{model_version}.category_vocab.json"
    vocab_path.write_text(json.dumps(category_vocab, indent=2))

    medians_path = ARTIFACT_DIR / f"{model_version}.numeric_medians.json"
    medians_path.write_text(json.dumps(numeric_medians, indent=2))

    all_model_comparison = {
        name: {"val_metrics": r["val_metrics"]} for name, r in results.items()
    }
    metrics_record = {
        "model_version": model_version,
        "selected_model": best_name,
        "is_synthetic_data": is_synthetic,
        "selection_metric": "pr_auc",
        "selection_set": "validation",
        "test_metrics": test_metrics,
        "validation_comparison": all_model_comparison,
        "skipped_models": skipped,
        "training_rows": len(df),
        "fraud_rate_full_dataset": float(df["isFraud"].mean()),
        "trained_at": pd.Timestamp.utcnow().isoformat(),
    }
    metrics_path = ARTIFACT_DIR / f"{model_version}.metrics.json"
    metrics_path.write_text(json.dumps(metrics_record, indent=2))

    # Active-model registry: the fraud service checks this file rather
    # than requiring a manual .env edit, so "trained" and "wired up" can't
    # drift out of sync.
    registry = {
        "model_version": model_version,
        "model_path": str(model_path),
        "scaler_path": str(scaler_path) if scaler_path else None,
        "columns_path": str(columns_path),
        "category_vocab_path": str(vocab_path),
        "numeric_medians_path": str(medians_path),
        "metrics_path": str(metrics_path),
        "is_synthetic_data": is_synthetic,
    }
    (ARTIFACT_DIR / "active_model.json").write_text(json.dumps(registry, indent=2))

    print("\n=== TRAINING SUMMARY ===")
    for name, r in results.items():
        m = r["val_metrics"]
        print(f"{name:20s} | val PR-AUC={m['pr_auc']:.4f} ROC-AUC={m['roc_auc']:.4f} "
              f"P={m['precision']:.3f} R={m['recall']:.3f} F1={m['f1']:.3f}")
    if skipped:
        print(f"Skipped: {skipped}")
    print(f"\nSelected: {best_name} ({model_version})")
    print(f"Test metrics: {test_metrics}")
    print(f"Artifacts written to: {ARTIFACT_DIR}")


if __name__ == "__main__":
    main()
