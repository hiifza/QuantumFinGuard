# Datasets

## Why three separate datasets, not one merged table

IEEE-CIS, IBM Credit Card Transactions, and the Ethereum Fraud
Detection dataset are three unrelated Kaggle datasets with different
schemas, different label semantics, and — critically — no shared
identifier space. A customer ID in IEEE-CIS (`card1`-derived) has no
real-world correspondence to an IBM `User` index or an Ethereum wallet
address. This system integrates them at the **platform/workflow
level**: each dataset feeds a distinct capability, and the code
actively guards against treating their identifiers as interchangeable
(see `app/services/behavioral_service.py`'s explicit dataset-mismatch
check, and `app/services/fraud_service.py`'s equivalent).

## IEEE-CIS Fraud Detection

**Real files used**: `train_transaction.csv` (590,540 rows, 394
columns) + `train_identity.csv` (144,233 rows, 41 columns), joined on
`TransactionID` via a **left join** (only ~24% of transactions have a
matching identity record — this is a real, documented characteristic
of the dataset, not a data quality issue).

**Correction made during real-data integration**: an earlier version
of this pipeline assumed `DeviceType`/`DeviceInfo` lived in the
transaction file. They're actually in the identity file. Fixed in
`app/data/loaders.py::get_ieee_cis_frame()`.

**Columns actually used** (of 394 real columns, most of which are
anonymized `V1`-`V339` PCA features not used here):
`TransactionID, isFraud, TransactionDT, TransactionAmt, ProductCD,
card1-6, addr1-2, dist1-2, P_emaildomain, R_emaildomain, C1-5, D1-5,
M1-4, DeviceType, DeviceInfo`.

**Real class balance**: 3.499% fraud (20,663 of 590,540 transactions).

**Used for**: fraud/risk model training (full dataset, no sampling),
SHAP explainability.

## IBM Credit Card Transactions

**Real file used**: `credit_card_transactions-ibm_v2.csv`, renamed to
`ibm_credit_card_transactions.csv` (24,386,900 rows, 15 columns).

**Memory strategy**: this file cannot be loaded into memory at once in
a constrained environment. Two separate real-data paths:
- **Behavioral baselines** (`app/data/behavioral_features.py`'s
  `compute_user_baselines_streaming` / `compute_merchant_baselines_streaming`):
  streams the **entire** 24.4M-row file in 500K-row chunks, accumulating
  per-user and per-merchant running sums. This is full-dataset
  statistics — every real row contributes — not a sample.
- **Database population**: a documented, deterministic **systematic
  sample** (`app/data/loaders.py::get_ibm_credit_sample_frame()`) —
  every Nth row, fixed stride, no randomness — of 50,076 rows (stride
  487, from 24,386,900 total). The sampling method, stride, and
  resulting size are recorded in the ingestion log and in this
  document, not left implicit. This sample exists so the live
  application has real IBM-sourced transactions to serve without
  writing 24.4M ORM-inserted rows.

**Columns**: `User, Card, Year, Month, Day, Time, Amount, Use Chip,
Merchant Name, Merchant City, Merchant State, Zip, MCC, Errors?, Is
Fraud?`.

**Used for**: per-customer and per-merchant behavioral baselines
(mean/stddev of transaction amount, minimum 20 historical transactions
required — 1,998 of ~2,000 real users qualify).

## Ethereum Fraud Detection Dataset

**Real file used**: `transaction_dataset.csv` (9,841 rows, address-level
aggregates — not a raw transaction log; this is the actual shape of
the public dataset).

**Graph derivation**: the real dataset provides per-address aggregate
stats (`Sent tnx`, `Unique Sent To Addresses`, `total Ether sent`,
etc.), not individual edges. `app/data/ethereum_graph.py::derive_edges()`
constructs a real, deterministic edge list consistent with each
address's own stated counterparty counts, with ~40% of edges
deliberately reusing other addresses already in the dataset (see
`docs/limitations.md` for why this matters — an earlier version
produced a graph with no multi-hop connectivity at all).

**Real class balance**: 2,179 of 9,841 addresses flagged (22.1%).

**Used for**: wallet lookup, multi-hop neighborhood traversal, flagged-
wallet listing (`app/services/graph_service.py`, `LocalGraphService`).

## Downloading the real datasets yourself

```
kaggle competitions download -c ieee-fraud-detection
kaggle datasets download -d ealtman2019/credit-card-transactions
kaggle datasets download -d vagifa/ethereum-frauddetection-dataset
```

See the backend README for exact file placement paths.
