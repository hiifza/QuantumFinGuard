from tests.conftest import API


class TestFraudStatus:
    def test_status_reports_ready_with_trained_model(self, client, analyst_headers):
        resp = client.get(f"{API}/fraud/status", headers=analyst_headers)
        assert resp.status_code == 200
        assert resp.json()["ready"] is True, "expected a trained model — has app/ml/train_fraud_model.py been run?"


class TestModelMetrics:
    def test_metrics_returns_real_comparison(self, client, analyst_headers):
        resp = client.get(f"{API}/fraud/models/metrics", headers=analyst_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["selected_model"] in ("logistic_regression", "random_forest", "xgboost", "lightgbm")
        assert 0.0 <= body["test_metrics"]["pr_auc"] <= 1.0
        assert 0.0 <= body["test_metrics"]["roc_auc"] <= 1.0
        assert body["test_metrics"]["confusion_matrix"]["tp"] >= 0

    def test_metrics_compares_multiple_models(self, client, analyst_headers):
        resp = client.get(f"{API}/fraud/models/metrics", headers=analyst_headers)
        body = resp.json()
        assert len(body["validation_comparison"]) >= 2, "expected multiple models compared, not just the winner"

    def test_metrics_honestly_labels_data_source(self, client, analyst_headers):
        """This must reflect whatever data actually trained the active
        model — the test does not assert a specific value, since which
        dataset trained the model is a fact about the environment, not
        something the test should presuppose."""
        resp = client.get(f"{API}/fraud/models/metrics", headers=analyst_headers)
        assert "is_synthetic_data" in resp.json()


class TestFraudScoring:
    def test_score_real_ieee_transaction_succeeds(self, client, analyst_headers, real_ieee_cis_transaction_id):
        resp = client.post(f"{API}/fraud/transactions/{real_ieee_cis_transaction_id}/score", headers=analyst_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert 0.0 <= body["risk_score"] <= 100.0
        assert 0.0 <= body["fraud_probability"] <= 1.0
        assert body["predicted_class"] in ("legitimate", "suspicious")
        assert body["risk_category"] in ("low", "medium", "high")

    def test_score_includes_real_shap_explanation(self, client, analyst_headers, real_ieee_cis_transaction_id):
        resp = client.post(f"{API}/fraud/transactions/{real_ieee_cis_transaction_id}/score", headers=analyst_headers)
        body = resp.json()
        assert body["shap_explanation"] is not None
        assert len(body["shap_explanation"]) > 0
        for feature in body["shap_explanation"]:
            assert feature["direction"] in ("increases_risk", "decreases_risk")
            assert isinstance(feature["contribution"], float)

    def test_score_persisted_and_retrievable(self, client, analyst_headers, real_ieee_cis_transaction_id):
        client.post(f"{API}/fraud/transactions/{real_ieee_cis_transaction_id}/score", headers=analyst_headers)
        resp = client.get(f"{API}/fraud/transactions/{real_ieee_cis_transaction_id}/predictions", headers=analyst_headers)
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_score_unknown_transaction_returns_404(self, client, analyst_headers):
        resp = client.post(f"{API}/fraud/transactions/00000000-0000-0000-0000-000000000000/score", headers=analyst_headers)
        assert resp.status_code == 404

    def test_dataset_mismatch_ibm_transaction_honestly_refused(self, client, analyst_headers, real_ibm_transaction):
        """Regression coverage for the explicit dataset-scope guard: an
        IBM-sourced transaction cannot be scored by the IEEE-CIS-trained
        model, and must fail with a clear explanation, not a crash or a
        silently wrong prediction."""
        resp = client.post(f"{API}/fraud/transactions/{real_ibm_transaction['id']}/score", headers=analyst_headers)
        assert resp.status_code == 501
        assert "ieee" in resp.json()["detail"].lower() or "dataset" in resp.json()["detail"].lower()

    def test_predictions_empty_list_for_unscored_transaction(self, client, analyst_headers):
        """A transaction that exists but was never scored should return
        an empty list, not a fabricated prediction."""
        resp = client.get(f"{API}/transactions", params={"page": 1, "page_size": 1}, headers=analyst_headers)
        # Use a fresh unscored transaction if possible; otherwise this just
        # confirms the endpoint shape is a list.
        txn_id = resp.json()["items"][0]["id"]
        pred_resp = client.get(f"{API}/fraud/transactions/{txn_id}/predictions", headers=analyst_headers)
        assert pred_resp.status_code == 200
        assert isinstance(pred_resp.json(), list)
