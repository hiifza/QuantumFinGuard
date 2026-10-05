from tests.conftest import API


class TestBehavioralAnalytics:
    def test_customer_context_on_real_ibm_transaction(self, client, analyst_headers, real_ibm_transaction):
        resp = client.get(
            f"{API}/behavioral/customers/{real_ibm_transaction['customer_id']}/context",
            params={"transaction_id": real_ibm_transaction["id"]},
            headers=analyst_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["entity_type"] == "customer"
        assert body["history_sample_size"] >= 20  # MIN_HISTORY_FOR_BASELINE
        assert len(body["signals"]) > 0
        sig = body["signals"][0]
        assert "deviation_sigma" in sig
        assert isinstance(sig["is_unusual"], bool)

    def test_mismatched_customer_id_path_param_rejected(self, client, analyst_headers, real_ibm_transaction):
        resp = client.get(
            f"{API}/behavioral/customers/wrong_customer_id/context",
            params={"transaction_id": real_ibm_transaction["id"]},
            headers=analyst_headers,
        )
        assert resp.status_code == 400


class TestBlockchain:
    def test_status_reports_active_backend(self, client, analyst_headers):
        resp = client.get(f"{API}/blockchain/status", headers=analyst_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["ready"] is True
        assert body["backend"] in ("LocalGraphService", "Neo4jGraphService")

    def test_flagged_wallets_returns_real_addresses(self, client, analyst_headers):
        resp = client.get(f"{API}/blockchain/wallets/flagged", params={"limit": 5}, headers=analyst_headers)
        assert resp.status_code == 200
        wallets = resp.json()
        assert len(wallets) > 0
        for w in wallets:
            assert w["address"].startswith("0x")
            assert w["is_flagged"] is True

    def test_wallet_lookup_for_known_flagged_address(self, client, analyst_headers):
        flagged = client.get(f"{API}/blockchain/wallets/flagged", params={"limit": 1}, headers=analyst_headers).json()
        address = flagged[0]["address"]
        resp = client.get(f"{API}/blockchain/wallets/{address}", headers=analyst_headers)
        assert resp.status_code == 200
        assert resp.json()["address"] == address

    def test_unknown_wallet_returns_503_not_fabricated(self, client, analyst_headers):
        resp = client.get(f"{API}/blockchain/wallets/0xdoesnotexist000000000000000000000000000", headers=analyst_headers)
        assert resp.status_code == 503

    def test_neighborhood_expansion_grows_with_depth(self, client, analyst_headers):
        flagged = client.get(f"{API}/blockchain/wallets/flagged", params={"limit": 1}, headers=analyst_headers).json()
        address = flagged[0]["address"]
        depth1 = client.get(f"{API}/blockchain/wallets/{address}/neighborhood", params={"depth": 1}, headers=analyst_headers).json()
        depth2 = client.get(f"{API}/blockchain/wallets/{address}/neighborhood", params={"depth": 2}, headers=analyst_headers).json()
        assert len(depth2["nodes"]) >= len(depth1["nodes"])

    def test_neighborhood_depth_capped_at_3(self, client, analyst_headers):
        flagged = client.get(f"{API}/blockchain/wallets/flagged", params={"limit": 1}, headers=analyst_headers).json()
        address = flagged[0]["address"]
        resp = client.get(f"{API}/blockchain/wallets/{address}/neighborhood", params={"depth": 10}, headers=analyst_headers)
        assert resp.status_code == 422


class TestInvestigationView:
    def test_ieee_transaction_shows_available_risk_and_explanation(self, client, analyst_headers, real_ieee_cis_transaction_id):
        resp = client.get(f"{API}/investigation/transactions/{real_ieee_cis_transaction_id}", headers=analyst_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["risk_assessment"]["status"] == "available"
        assert body["explanation"]["status"] == "available"
        assert body["security_context"]["status"] == "available"
        assert body["security_context"]["hash_recomputation_matches"] is True

    def test_ieee_transaction_behavioral_honestly_not_available(self, client, analyst_headers, real_ieee_cis_transaction_id):
        resp = client.get(f"{API}/investigation/transactions/{real_ieee_cis_transaction_id}", headers=analyst_headers)
        body = resp.json()
        assert body["behavioral_context"]["status"] == "not_available"
        assert "ibm" in body["behavioral_context"]["reason"].lower() or "dataset" in body["behavioral_context"]["reason"].lower()

    def test_blockchain_context_not_applicable_for_card_transaction(self, client, analyst_headers, real_ieee_cis_transaction_id):
        resp = client.get(f"{API}/investigation/transactions/{real_ieee_cis_transaction_id}", headers=analyst_headers)
        body = resp.json()
        assert body["blockchain_context"]["status"] == "not_applicable"

    def test_ibm_transaction_shows_available_behavioral(self, client, analyst_headers, real_ibm_transaction):
        resp = client.get(f"{API}/investigation/transactions/{real_ibm_transaction['id']}", headers=analyst_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["behavioral_context"]["status"] == "available"

    def test_ibm_transaction_risk_honestly_not_available(self, client, analyst_headers, real_ibm_transaction):
        resp = client.get(f"{API}/investigation/transactions/{real_ibm_transaction['id']}", headers=analyst_headers)
        body = resp.json()
        assert body["risk_assessment"]["status"] == "not_available"

    def test_summary_is_deterministic_not_ai_labeled(self, client, analyst_headers, real_ieee_cis_transaction_id):
        resp = client.get(f"{API}/investigation/transactions/{real_ieee_cis_transaction_id}", headers=analyst_headers)
        summary = resp.json()["investigation_summary"]
        assert "not an ai-generated" in summary.lower() or "not a fraud determination" in summary.lower()

    def test_unknown_transaction_returns_404(self, client, analyst_headers):
        resp = client.get(f"{API}/investigation/transactions/00000000-0000-0000-0000-000000000000", headers=analyst_headers)
        assert resp.status_code == 404
