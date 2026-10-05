"""
Unit tests for app/data/preprocessing.py.

These test pure functions against small, hand-constructed DataFrames —
no database, no real dataset files required. Includes regression tests
for two real bugs found during real-data integration: the DeviceInfo
cardinality explosion, and the LightGBM special-character column name
crash.
"""
import pandas as pd

from app.data import preprocessing


def _minimal_ieee_row(**overrides) -> dict:
    base = {
        "TransactionID": 1, "isFraud": 0, "TransactionDT": 86400, "TransactionAmt": 100.0,
        "ProductCD": "W", "card1": 1000, "card2": 200.0, "card3": 150.0, "card4": "visa",
        "card5": 100.0, "card6": "debit", "addr1": 200.0, "addr2": 87.0, "dist1": 10.0, "dist2": 5.0,
        "P_emaildomain": "gmail.com", "R_emaildomain": None,
        "C1": 1.0, "C2": 1.0, "C3": 0.0, "C4": 0.0, "C5": 0.0,
        "D1": 5.0, "D2": 3.0, "D3": 2.0, "D4": 1.0, "D5": 0.0,
        "M1": "T", "M2": "T", "M3": "T", "M4": "M0",
        "DeviceType": "desktop", "DeviceInfo": "Windows",
    }
    base.update(overrides)
    return base


class TestFeatureEngineering:
    def test_engineer_features_adds_expected_columns(self):
        df = pd.DataFrame([_minimal_ieee_row()])
        out = preprocessing.engineer_features(df)
        for col in preprocessing.ENGINEERED_FEATURES:
            assert col in out.columns, f"missing engineered column: {col}"

    def test_amt_log_is_log1p_of_amount(self):
        df = pd.DataFrame([_minimal_ieee_row(TransactionAmt=99.0)])
        out = preprocessing.engineer_features(df)
        import numpy as np
        assert abs(out["amt_log"].iloc[0] - np.log1p(99.0)) < 1e-9

    def test_hour_of_day_bounded_0_to_23(self):
        df = pd.DataFrame([_minimal_ieee_row(TransactionDT=t) for t in [0, 3600, 90000, 999999]])
        out = preprocessing.engineer_features(df)
        assert out["hour_of_day"].between(0, 23).all()


class TestBuildFeatureMatrix:
    def test_no_nan_after_imputation_on_multi_row_batch(self):
        """Median imputation is only meaningful across multiple rows (a
        median of one value is degenerate — see the dedicated
        single-row tests below for that case). This tests the realistic
        training-time scenario: a batch with some missing values, where
        the batch's own median correctly fills the gaps."""
        rows = [_minimal_ieee_row(TransactionID=i, card2=None if i == 0 else 200.0 + i,
                                    D1=None if i == 1 else 5.0, P_emaildomain=None if i == 2 else "gmail.com")
                for i in range(10)]
        df = pd.DataFrame(rows)
        X, y = preprocessing.build_feature_matrix(df)
        assert not X.isna().any().any()

    def test_target_column_extracted_correctly(self):
        df = pd.DataFrame([_minimal_ieee_row(isFraud=1), _minimal_ieee_row(TransactionID=2, isFraud=0)])
        X, y = preprocessing.build_feature_matrix(df)
        assert list(y) == [1, 0]

    def test_no_target_column_returns_none(self):
        row = _minimal_ieee_row()
        del row["isFraud"]
        df = pd.DataFrame([row])
        X, y = preprocessing.build_feature_matrix(df)
        assert y is None

    def test_high_cardinality_device_info_bucketed_not_exploded(self):
        """Regression test for the real bug: DeviceInfo had 1,786 unique
        real values, and one-hot encoding it directly produced a 1,963-
        column feature matrix. With a fitted vocab capping it to top-20 +
        'other', a large synthetic set of distinct DeviceInfo values
        must NOT blow up the column count."""
        rows = [_minimal_ieee_row(TransactionID=i, DeviceInfo=f"device_{i}") for i in range(200)]
        df = pd.DataFrame(rows)
        vocab = preprocessing.fit_category_vocab(df, columns=["DeviceInfo"], max_categories=20)
        X, _ = preprocessing.build_feature_matrix(df, category_vocab=vocab)
        device_info_columns = [c for c in X.columns if c.startswith("DeviceInfo_")]
        # top-20 + 1 "other" bucket = at most 21 dummy columns, never 200+
        assert len(device_info_columns) <= 21, f"expected bucketing to cap columns, got {len(device_info_columns)}"

    def test_column_names_sanitized_for_lightgbm_compatibility(self):
        """Regression test: real DeviceInfo values like 'rv:11.0'
        (Firefox-style version strings) produced one-hot column names
        containing ':', which LightGBM rejects at training time. No
        output column name may contain LightGBM's disallowed characters."""
        df = pd.DataFrame([
            _minimal_ieee_row(TransactionID=1, DeviceInfo="rv:11.0"),
            _minimal_ieee_row(TransactionID=2, DeviceInfo='weird"name'),
            _minimal_ieee_row(TransactionID=3, DeviceInfo="normal"),
        ])
        X, _ = preprocessing.build_feature_matrix(df)
        import re
        bad = [c for c in X.columns if re.search(r'[",\'\[\]{}:\\]', str(c))]
        assert bad == [], f"unsanitized column names found: {bad}"

    def test_numeric_medians_used_at_single_row_inference(self):
        """Regression test: the median of a single-row DataFrame is
        degenerate (median of one value is that value; if NaN, filling
        with it is a no-op). A persisted training median must actually
        be applied when the single inference row's own value is missing."""
        train_df = pd.DataFrame([_minimal_ieee_row(TransactionID=i, card2=200.0) for i in range(10)])
        medians = preprocessing.fit_numeric_medians(train_df)
        assert medians["card2"] == 200.0

        single_row = pd.DataFrame([_minimal_ieee_row(TransactionID=99, card2=None)])
        X, _ = preprocessing.build_feature_matrix(single_row, numeric_medians=medians)
        assert X["card2"].iloc[0] == 200.0  # filled from persisted median, not left NaN

    def test_without_persisted_medians_single_row_nan_stays_nan(self):
        """Documents the degenerate behavior this regression test guards
        against: WITHOUT a persisted median, a single all-NaN-for-that-
        column row has no meaningful median to fall back on."""
        single_row = pd.DataFrame([_minimal_ieee_row(TransactionID=99, card2=None)])
        X, _ = preprocessing.build_feature_matrix(single_row, numeric_medians=None)
        assert pd.isna(X["card2"].iloc[0])


class TestCategoryVocab:
    def test_vocab_only_contains_high_cardinality_columns(self):
        df = pd.DataFrame([_minimal_ieee_row(DeviceInfo=f"d{i}") for i in range(30)])
        vocab = preprocessing.fit_category_vocab(df)
        assert set(vocab.keys()) == set(preprocessing.HIGH_CARDINALITY_COLUMNS)

    def test_vocab_caps_at_max_categories(self):
        df = pd.DataFrame([_minimal_ieee_row(TransactionID=i, DeviceInfo=f"d{i}") for i in range(100)])
        vocab = preprocessing.fit_category_vocab(df, max_categories=5)
        assert len(vocab["DeviceInfo"]) == 5
