"""
Shared pytest fixtures.

Deliberate choice: these fixtures bind to the ACTUAL configured
database (whatever DATABASE_URL points at — the real, already-ingested
quantumfinguard.db when run after `python -m scripts.ingest_data`), not
an isolated empty test database. That's what makes the integration
tests in tests/integration/ genuine tests against real data (real
transactions, the real trained model) rather than tests against a
synthetic fixture that happens to share the same schema. Unit tests in
tests/unit/ don't touch the database at all.

Running `pytest` without first running ingestion will still work for
unit tests and for integration tests that correctly handle the
"nothing ingested yet" state (many already do, by design — see the
codebase's own not_available/not_applicable patterns) — but tests that
assert on specific real-data facts (e.g. "at least one ieee_cis
transaction exists") require ingestion to have actually run first, and
are marked accordingly.
"""
import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db.session import SessionLocal
from app.models.user import User

API = "/api/v1"


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


def _register_and_login(client: TestClient, role: str | None = None) -> dict:
    email = f"pytest-{uuid.uuid4().hex[:10]}@quantumfinguard.dev"
    password = "correct-horse-battery"

    resp = client.post(f"{API}/auth/register", json={
        "email": email, "full_name": "Pytest User", "password": password,
    })
    assert resp.status_code == 201, resp.text

    if role and role != "analyst":
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.email == email).first()
            user.role = role
            db.commit()
        finally:
            db.close()

    resp = client.post(f"{API}/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    tokens = resp.json()
    return {"email": email, "access_token": tokens["access_token"], "refresh_token": tokens["refresh_token"]}


@pytest.fixture(scope="session")
def analyst_auth(client):
    return _register_and_login(client, role="analyst")


@pytest.fixture(scope="session")
def senior_analyst_auth(client):
    return _register_and_login(client, role="senior_analyst")


@pytest.fixture(scope="session")
def compliance_officer_auth(client):
    return _register_and_login(client, role="compliance_officer")


@pytest.fixture(scope="session")
def analyst_headers(analyst_auth):
    return {"Authorization": f"Bearer {analyst_auth['access_token']}"}


@pytest.fixture(scope="session")
def senior_analyst_headers(senior_analyst_auth):
    return {"Authorization": f"Bearer {senior_analyst_auth['access_token']}"}


@pytest.fixture(scope="session")
def compliance_officer_headers(compliance_officer_auth):
    return {"Authorization": f"Bearer {compliance_officer_auth['access_token']}"}


@pytest.fixture(scope="session")
def real_ieee_cis_transaction_id(client, analyst_headers):
    """Skips (rather than failing hard) if ingestion hasn't been run —
    this is a real-data integration fixture, not something that should
    silently fall back to fabricating a transaction."""
    resp = client.get(f"{API}/transactions", params={"page": 1, "page_size": 200}, headers=analyst_headers)
    assert resp.status_code == 200
    items = resp.json()["items"]
    ieee_items = [t for t in items if t["customer_id"].startswith("card_")]
    if not ieee_items:
        pytest.skip("No IEEE-CIS-sourced transaction found in the first 200 rows — has ingestion been run?")
    return ieee_items[0]["id"]


@pytest.fixture(scope="session")
def real_ibm_transaction(client, analyst_headers):
    """IEEE-CIS's synthetic-offset timestamps (all within Jan 2026) sort
    far more recent than IBM's real 2002-2020 transaction dates, so IBM
    rows only appear very deep in a timestamp-DESC paginated listing —
    scanning pages would need to walk ~50,000+ IEEE-CIS rows first.
    Querying the database directly for a known-real IBM row is the
    correct approach for a test fixture (the API's own correctness is
    what test_list_returns_real_records_after_ingestion etc. already
    cover; this fixture just needs *a* real IBM transaction id)."""
    from app.db.session import SessionLocal
    from app.models.transaction import Transaction

    db = SessionLocal()
    try:
        txn = db.query(Transaction).filter(Transaction.customer_id.like("ibm_user_%")).first()
    finally:
        db.close()

    if txn is None:
        pytest.skip("No IBM-sourced transaction in the database — has ingestion been run?")

    resp = client.get(f"{API}/transactions/{txn.id}", headers=analyst_headers)
    assert resp.status_code == 200
    return resp.json()
