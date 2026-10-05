"""
Feature column alignment.

One-hot encoding at inference time (a single transaction) will not
naturally produce the same columns as one-hot encoding at training time
(thousands of transactions with more category diversity). This module
is the explicit, auditable fix: persist the training-time column list,
and reindex any future feature matrix onto it — missing dummy columns
filled with 0, unexpected columns dropped. Without this step, a single
scored transaction could silently break the model's expected input
shape or (worse) shift what each column index means.
"""
import json
from pathlib import Path

import pandas as pd


def save_feature_columns(columns: list[str], path: Path) -> None:
    path.write_text(json.dumps(columns))


def load_feature_columns(path: Path) -> list[str]:
    return json.loads(path.read_text())


def align_to_training_columns(X: pd.DataFrame, training_columns: list[str]) -> pd.DataFrame:
    return X.reindex(columns=training_columns, fill_value=0)
