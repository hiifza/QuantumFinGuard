# Testing

## Structure

```
tests/
  unit/          # no DB, no API, no real dataset files required
  integration/   # FastAPI TestClient against the real ingested database
                 # (requires `python -m scripts.ingest_data` and
                 # `python -m app.ml.train_fraud_model` to have been run
                 # first; tests that need real data fixtures skip with a
                 # clear message if it hasn't been, rather than silently
                 # substituting fake data and passing anyway)
  e2e/           # sequential full-workflow smoke tests, plus the
                 # original bash-script smoke tests from earlier
                 # development phases
```

## Actual results (this run)

```
104 passed in 8.87s
```

Breakdown: 35 unit tests (preprocessing, integrity hashing, PQC
primitives, RAG retrieval), 67 integration tests (auth, transactions,
dataset status, fraud/SHAP, behavioral, blockchain, investigation,
security/PQC/copilot, API error handling), 2 e2e tests.

## Real bugs found by writing and running these tests, not by inspection

1. `/fraud/status` and `/blockchain/status` had no authentication
   requirement, inconsistent with every other endpoint in the API.
   Found by test_unauthenticated_requests_consistently_rejected.
   Fixed by adding the get_current_user dependency to both.
2. JWT tokens issued within the same second were byte-identical (no
   jti/nonce claim). Found by test_refresh_issues_new_access_token
   failing because a login immediately followed by a refresh (as the
   test itself does) produced two identical tokens. Fixed by adding a
   jti: str(uuid4()) claim to every issued token (standard JWT
   practice, RFC 7519 4.1.7).

## Regression tests for the real-data integration bugs

Explicitly present, one per bug (see tests/unit/test_preprocessing.py
docstrings for the full explanation of each):

1. IEEE-CIS transaction + identity join -- covered implicitly by every
   integration test that exercises a real IEEE-CIS transaction (the
   join must succeed for DeviceType/DeviceInfo to be populated at all).
2. test_high_cardinality_device_info_bucketed_not_exploded
3. test_column_names_sanitized_for_lightgbm_compatibility
4. Stale-synthetic-parquet-shadowing-real-data -- NOT currently covered
   by an automated test. This was caught by manual inspection of a
   suspicious wallet address during development, documented in
   docs/limitations.md. A proper regression test would need to simulate
   both a real and a stale synthetic parquet file coexisting, which the
   current fixtures don't set up. Flagged here as a real testing gap,
   not silently omitted.
5. SHAP-service caching is exercised implicitly (every SHAP-dependent
   integration test would be prohibitively slow if the cache didn't
   work), but there's no dedicated timing assertion.
6. test_numeric_medians_used_at_single_row_inference and
   test_without_persisted_medians_single_row_nan_stays_nan.

## What's NOT tested (stated plainly)

- No load/performance testing.
- No test isolates a fresh empty database -- integration tests run
  against whatever real data is currently ingested, which is the right
  choice for testing real-data behavior but means these tests are not
  independent of ingestion having been run first.
- Frontend has no automated test suite (TypeScript compilation +
  production build + manual/scripted API-contract verification only).
- No CI pipeline configured; tests are run manually.
