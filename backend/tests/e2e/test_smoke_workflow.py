"""
End-to-end smoke test: one sequential analyst workflow, exercising the
system the way a real user would rather than one isolated endpoint at
a time. This is deliberately a thinner check than tests/integration/
(which covers edge cases and error paths in depth) — its job is to
prove the pieces work together in sequence, on real data, through the
real API.
"""
from tests.conftest import API


class TestFullAnalystWorkflow:
    def test_register_login_investigate_secure_workflow(self, client):
        # 1. Register and log in.
        register = client.post(f"{API}/auth/register", json={
            "email": "e2e-smoke@quantumfinguard.dev", "full_name": "E2E Smoke", "password": "correct-horse-battery",
        })
        assert register.status_code in (201, 409)  # 409 if a previous run already created this user

        login = client.post(f"{API}/auth/login", json={"email": "e2e-smoke@quantumfinguard.dev", "password": "correct-horse-battery"})
        assert login.status_code == 200
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        # 2. Confirm real data is actually present.
        ingestion = client.get(f"{API}/data/ingestion-status", headers=headers).json()
        assert ingestion["ieee_cis"]["real_data_available"] is True

        # 3. List transactions, pick a real one.
        txns = client.get(f"{API}/transactions", params={"page": 1, "page_size": 10}, headers=headers).json()
        assert txns["total"] > 0
        txn_id = txns["items"][0]["id"]

        # 4. Open the full investigation view.
        investigation = client.get(f"{API}/investigation/transactions/{txn_id}", headers=headers)
        assert investigation.status_code == 200

        # 5. Ask the copilot about it.
        copilot = client.post(f"{API}/copilot/ask", json={"question": "Summarize this transaction", "transaction_id": txn_id}, headers=headers)
        assert copilot.status_code == 200
        assert copilot.json()["mode"] in ("llm_generated", "evidence_digest")

        # 6. Check the security center reflects real state.
        overview = client.get(f"{API}/security/center/overview", headers=headers)
        assert overview.status_code == 200
        assert overview.json()["blockchain_integrity"]["sealed_transactions"] > 0

        # 7. Check blockchain graph is honestly reporting its backend.
        blockchain_status = client.get(f"{API}/blockchain/status", headers=headers)
        assert blockchain_status.json()["backend"] in ("LocalGraphService", "Neo4jGraphService")

    def test_unauthenticated_requests_consistently_rejected(self, client):
        """A single check across several representative endpoints — full
        per-endpoint auth coverage lives in tests/integration/test_auth.py."""
        for path in ["/transactions", "/fraud/status", "/blockchain/status", "/security/center/overview", "/copilot/status"]:
            resp = client.get(f"{API}{path}")
            assert resp.status_code == 401, f"{path} should require authentication"
