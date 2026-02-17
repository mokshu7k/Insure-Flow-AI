"""
E2E Tests: Full API flow using FastAPI TestClient + SQLite in-memory.
Tests: register → login → consent → claim submission → fraud gate.
"""
import pytest
import uuid
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.db.session import get_db
from app.models.base import Base
# Import all models so Base.metadata has every table
import app.models  # noqa: F401

SQLITE_URL = "sqlite://"   # pure in-memory

engine = create_engine(
    SQLITE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

# SQLite doesn't enforce FK by default — enable it
@event.listens_for(engine, "connect")
def _set_sqlite_pragma(conn, _):
    conn.execute("PRAGMA foreign_keys=ON")

TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


# ── helpers ──────────────────────────────────────────────────────────────────

def register_and_login(client, role="CUSTOMER"):
    suffix = uuid.uuid4().hex[:8]
    email = f"{role.lower()}_{suffix}@test.com"
    client.post("/api/v1/auth/register", json={
        "email": email, "password": "Test@1234!", "role": role,
    })
    r = client.post("/api/v1/auth/login", json={
        "email": email, "password": "Test@1234!",
    })
    return r.json()["access_token"], email


def auth(token):
    return {"Authorization": f"Bearer {token}"}


# ── Auth ──────────────────────────────────────────────────────────────────────

class TestAuth:
    def test_register_201(self, client):
        r = client.post("/api/v1/auth/register", json={
            "email": f"u{uuid.uuid4().hex[:6]}@t.com",
            "password": "Test@1234!", "role": "CUSTOMER",
        })
        assert r.status_code == 201
        assert "id" in r.json()

    def test_duplicate_email_409(self, client):
        email = f"dup_{uuid.uuid4().hex[:6]}@t.com"
        client.post("/api/v1/auth/register", json={
            "email": email, "password": "Test@1234!", "role": "CUSTOMER",
        })
        r = client.post("/api/v1/auth/register", json={
            "email": email, "password": "Test@1234!", "role": "CUSTOMER",
        })
        assert r.status_code == 409

    def test_login_returns_tokens(self, client):
        email = f"l{uuid.uuid4().hex[:6]}@t.com"
        client.post("/api/v1/auth/register", json={
            "email": email, "password": "Test@1234!", "role": "CUSTOMER",
        })
        r = client.post("/api/v1/auth/login", json={
            "email": email, "password": "Test@1234!",
        })
        assert r.status_code == 200
        assert "access_token" in r.json()
        assert "refresh_token" in r.json()

    def test_wrong_password_401(self, client):
        email = f"w{uuid.uuid4().hex[:6]}@t.com"
        client.post("/api/v1/auth/register", json={
            "email": email, "password": "Right@1234!", "role": "CUSTOMER",
        })
        r = client.post("/api/v1/auth/login", json={
            "email": email, "password": "Wrong@1234!",
        })
        assert r.status_code == 401

    def test_me_no_auth_403(self, client):
        r = client.get("/api/v1/auth/me")
        assert r.status_code == 403

    def test_me_with_token(self, client):
        token, _ = register_and_login(client, "CUSTOMER")
        r = client.get("/api/v1/auth/me", headers=auth(token))
        assert r.status_code == 200
        assert r.json()["role"] == "CUSTOMER"


# ── Consent ───────────────────────────────────────────────────────────────────

class TestConsent:
    def test_consent_text_public(self, client):
        r = client.get("/api/v1/compliance/consent/text")
        assert r.status_code == 200
        assert "text" in r.json()

    def test_give_consent_confirm_false_400(self, client):
        token, _ = register_and_login(client, "CUSTOMER")
        r = client.post("/api/v1/compliance/consent/give",
                        json={"confirm": False}, headers=auth(token))
        assert r.status_code == 400

    def test_give_consent_succeeds(self, client):
        token, _ = register_and_login(client, "CUSTOMER")
        r = client.post("/api/v1/compliance/consent/give",
                        json={"confirm": True}, headers=auth(token))
        assert r.status_code == 200
        assert "consent_id" in r.json()

    def test_consent_status_after_giving(self, client):
        token, _ = register_and_login(client, "CUSTOMER")
        client.post("/api/v1/compliance/consent/give",
                    json={"confirm": True}, headers=auth(token))
        r = client.get("/api/v1/compliance/consent/status", headers=auth(token))
        assert r.status_code == 200
        assert r.json()["has_valid_consent"] is True


# ── Claim ─────────────────────────────────────────────────────────────────────

class TestClaims:
    def test_claim_without_consent_403(self, client):
        token, _ = register_and_login(client, "CUSTOMER")
        # No consent given
        r = client.post("/api/v1/claims/", json={
            "policy_number": "POL-TEST-001",
            "claim_type": "HEALTH",
            "claim_amount": 50_000.0,
        }, headers=auth(token))
        assert r.status_code == 403
        assert "consent" in r.json()["detail"].lower()

    def test_claim_with_consent_201(self, client):
        token, _ = register_and_login(client, "CUSTOMER")
        # Give consent first
        client.post("/api/v1/compliance/consent/give",
                    json={"confirm": True}, headers=auth(token))
        r = client.post("/api/v1/claims/", json={
            "policy_number": "POL-TEST-002",
            "claim_type": "HEALTH",
            "claim_amount": 50_000.0,
        }, headers=auth(token))
        assert r.status_code == 201
        data = r.json()
        assert data["status"] == "SUBMITTED"
        assert data["policy_number"] == "POL-TEST-002"

    def test_unauthenticated_claim_403(self, client):
        r = client.post("/api/v1/claims/", json={
            "policy_number": "X", "claim_type": "HEALTH", "claim_amount": 1000,
        })
        assert r.status_code == 403


# ── Health ────────────────────────────────────────────────────────────────────

class TestHealthCheck:
    def test_health(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "healthy"