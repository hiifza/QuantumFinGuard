"""
Authoritative schema definitions for the three project datasets.

These match the real, published column sets for each Kaggle dataset so
that:
  (a) the loaders can validate a downloaded file is actually what it
      claims to be, and
  (b) the synthetic generator produces data that is structurally
      indistinguishable from the real thing (same columns, same dtypes,
      same value domains) — which is what makes it useful for pipeline
      development at all.

Source datasets (not redistributable — see loaders.py for why they
must be downloaded by the user, not fetched automatically):
  - IEEE-CIS Fraud Detection: https://www.kaggle.com/competitions/ieee-fraud-detection
  - IBM TabFormer Credit Card Transactions: https://www.kaggle.com/datasets/ealtman2019/credit-card-transactions
  - Ethereum Fraud Detection Dataset (transaction-level):
    https://www.kaggle.com/datasets/vagifa/ethereum-frauddetection-dataset
"""

# --- IEEE-CIS Fraud Detection ---
# The real Kaggle release ships as TWO separate files joined on
# TransactionID: train_transaction.csv (the transaction-level fields)
# and train_identity.csv (device/identity fields, including DeviceType
# and DeviceInfo — NOT present in train_transaction.csv). Only ~144k of
# the 590k transactions have a matching identity record; the join must
# be a left join on TransactionID, keeping all transactions and leaving
# identity fields null where absent. This was verified against the real
# uploaded files, not assumed — an earlier version of this schema
# incorrectly listed DeviceType/DeviceInfo as transaction-file columns.
IEEE_CIS_TRANSACTION_REQUIRED_COLUMNS = [
    "TransactionID", "isFraud", "TransactionDT", "TransactionAmt",
    "ProductCD", "card1", "card2", "card3", "card4", "card5", "card6",
    "addr1", "addr2", "dist1", "dist2",
    "P_emaildomain", "R_emaildomain",
    "C1", "C2", "C3", "C4", "C5",
    "D1", "D2", "D3", "D4", "D5",
    "M1", "M2", "M3", "M4",
]
IEEE_CIS_IDENTITY_REQUIRED_COLUMNS = ["TransactionID", "DeviceType", "DeviceInfo"]

# Combined column set used for post-merge validation/typing elsewhere.
IEEE_CIS_REQUIRED_COLUMNS = IEEE_CIS_TRANSACTION_REQUIRED_COLUMNS + ["DeviceType", "DeviceInfo"]

IEEE_CIS_CATEGORICAL = ["ProductCD", "card4", "card6", "P_emaildomain", "R_emaildomain",
                         "M1", "M2", "M3", "M4", "DeviceType", "DeviceInfo"]
IEEE_CIS_TARGET = "isFraud"

# --- IBM Credit Card Transactions (TabFormer) ---
IBM_CREDIT_REQUIRED_COLUMNS = [
    "User", "Card", "Year", "Month", "Day", "Time",
    "Amount", "Use Chip", "Merchant Name", "Merchant City", "Merchant State",
    "Zip", "MCC", "Errors?", "Is Fraud?",
]
IBM_CREDIT_TARGET = "Is Fraud?"

# --- Ethereum Fraud Detection Dataset (address-level with tx aggregates) ---
ETHEREUM_REQUIRED_COLUMNS = [
    "Address", "FLAG",
    "Avg min between sent tnx", "Avg min between received tnx",
    "Sent tnx", "Received Tnx",
    "total transactions (including tnx to create contract",
    "total Ether sent", "total ether received", "total ether balance",
    "Unique Received From Addresses", "Unique Sent To Addresses",
]
ETHEREUM_TARGET = "FLAG"  # 1 = flagged/fraudulent address


class SchemaValidationError(Exception):
    pass


def validate_columns(df_columns: list[str], required: list[str], dataset_name: str) -> None:
    missing = [c for c in required if c not in df_columns]
    if missing:
        raise SchemaValidationError(
            f"{dataset_name}: file is missing expected columns: {missing}. "
            f"This does not look like the real {dataset_name} export — check the download."
        )
