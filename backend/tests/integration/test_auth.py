import uuid

from tests.conftest import API


class TestRegisterLogin:
    def test_register_creates_analyst_role_by_default(self, client):
        email = f"newuser-{uuid.uuid4().hex[:8]}@quantumfinguard.dev"
        resp = client.post(f"{API}/auth/register", json={
            "email": email, "full_name": "New User", "password": "correct-horse-battery",
        })
        assert resp.status_code == 201
        body = resp.json()
        assert body["role"] == "analyst"
        assert body["is_active"] is True

    def test_duplicate_registration_rejected(self, client):
        email = f"dup-{uuid.uuid4().hex[:8]}@quantumfinguard.dev"
        payload = {"email": email, "full_name": "Dup User", "password": "correct-horse-battery"}
        first = client.post(f"{API}/auth/register", json=payload)
        assert first.status_code == 201
        second = client.post(f"{API}/auth/register", json=payload)
        assert second.status_code == 409

    def test_login_with_wrong_password_rejected(self, client):
        email = f"wrongpw-{uuid.uuid4().hex[:8]}@quantumfinguard.dev"
        client.post(f"{API}/auth/register", json={"email": email, "full_name": "X", "password": "correct-horse-battery"})
        resp = client.post(f"{API}/auth/login", json={"email": email, "password": "wrong-password-entirely"})
        assert resp.status_code == 401

    def test_login_nonexistent_user_rejected(self, client):
        resp = client.post(f"{API}/auth/login", json={"email": "nobody@nowhere.dev", "password": "whatever12345"})
        assert resp.status_code == 401

    def test_me_requires_authentication(self, client):
        resp = client.get(f"{API}/auth/me")
        assert resp.status_code == 401

    def test_me_returns_correct_user(self, client, analyst_auth, analyst_headers):
        resp = client.get(f"{API}/auth/me", headers=analyst_headers)
        assert resp.status_code == 200
        assert resp.json()["email"] == analyst_auth["email"]

    def test_password_too_short_rejected(self, client):
        resp = client.post(f"{API}/auth/register", json={
            "email": f"shortpw-{uuid.uuid4().hex[:8]}@quantumfinguard.dev",
            "full_name": "X", "password": "short",
        })
        assert resp.status_code == 422


class TestRefresh:
    def test_refresh_issues_new_access_token(self, client, analyst_auth):
        resp = client.post(f"{API}/auth/refresh", json={"refresh_token": analyst_auth["refresh_token"]})
        assert resp.status_code == 200
        new_tokens = resp.json()
        assert new_tokens["access_token"] != analyst_auth["access_token"]

    def test_refresh_with_garbage_token_rejected(self, client):
        resp = client.post(f"{API}/auth/refresh", json={"refresh_token": "not-a-real-token"})
        assert resp.status_code == 401

    def test_access_token_cannot_be_used_as_refresh_token(self, client, analyst_auth):
        resp = client.post(f"{API}/auth/refresh", json={"refresh_token": analyst_auth["access_token"]})
        assert resp.status_code == 401


class TestAuthorizationHeaderHandling:
    def test_missing_token_returns_401(self, client):
        resp = client.get(f"{API}/transactions")
        assert resp.status_code == 401

    def test_malformed_token_returns_401(self, client):
        resp = client.get(f"{API}/transactions", headers={"Authorization": "Bearer garbage.not.a.jwt"})
        assert resp.status_code == 401

    def test_role_gated_endpoint_rejects_insufficient_role(self, client, analyst_headers):
        """analyst role is below senior_analyst — full-chain verify requires senior_analyst+."""
        resp = client.get(f"{API}/security/integrity/verify", headers=analyst_headers)
        assert resp.status_code == 403

    def test_role_gated_endpoint_accepts_sufficient_role(self, client, senior_analyst_headers):
        resp = client.get(f"{API}/security/integrity/verify", headers=senior_analyst_headers)
        assert resp.status_code == 200
