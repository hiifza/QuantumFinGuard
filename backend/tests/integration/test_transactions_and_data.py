from tests.conftest import API


class TestTransactionsList:
    def test_list_requires_auth(self, client):
        assert client.get(f"{API}/transactions").status_code == 401

    def test_list_returns_real_records_after_ingestion(self, client, analyst_headers):
        resp = client.get(f"{API}/transactions", params={"page": 1, "page_size": 10}, headers=analyst_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] > 0, "expected real ingested transactions — has `python -m scripts.ingest_data` been run?"
        assert len(body["items"]) <= 10

    def test_pagination_page_size_respected(self, client, analyst_headers):
        resp = client.get(f"{API}/transactions", params={"page": 1, "page_size": 5}, headers=analyst_headers)
        assert len(resp.json()["items"]) <= 5

    def test_get_single_transaction_by_id(self, client, analyst_headers, real_ieee_cis_transaction_id):
        resp = client.get(f"{API}/transactions/{real_ieee_cis_transaction_id}", headers=analyst_headers)
        assert resp.status_code == 200
        assert resp.json()["id"] == real_ieee_cis_transaction_id

    def test_get_unknown_transaction_returns_404(self, client, analyst_headers):
        resp = client.get(f"{API}/transactions/00000000-0000-0000-0000-000000000000", headers=analyst_headers)
        assert resp.status_code == 404

    def test_ingested_transactions_are_hash_sealed(self, client, analyst_headers, real_ieee_cis_transaction_id):
        resp = client.get(f"{API}/transactions/{real_ieee_cis_transaction_id}", headers=analyst_headers)
        assert resp.json()["record_hash"] is not None


class TestDatasetStatus:
    def test_ingestion_status_reports_real_data(self, client, analyst_headers):
        """This is the specific check that distinguishes 'real data
        integrated' from 'synthetic fallback still active' — the whole
        point of the real-dataset integration pass."""
        resp = client.get(f"{API}/data/ingestion-status", headers=analyst_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["ieee_cis"]["real_data_available"] is True
        assert body["ibm_credit"]["real_data_available"] is True
        assert body["ethereum"]["real_data_available"] is True

    def test_source_breakdown_reports_real_not_synthetic(self, client, analyst_headers):
        resp = client.get(f"{API}/data/transactions/source-breakdown", headers=analyst_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) > 0
        for source, info in body.items():
            assert info["is_synthetic"] is False, f"{source} is marked synthetic — expected real data"
            assert info["count"] > 0

    def test_source_breakdown_includes_both_ieee_and_ibm(self, client, analyst_headers):
        resp = client.get(f"{API}/data/transactions/source-breakdown", headers=analyst_headers)
        body = resp.json()
        assert "ieee_cis" in body
        assert "ibm_credit" in body
