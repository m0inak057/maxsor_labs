import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.main import app
from src.database import Base, get_db
from src.schemas import AIDecision

TEST_DB_URL = "sqlite:///./test_authz.db"
test_engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

MOCK_DECISION = AIDecision(
    action="APPROVE_RETURN",
    confidence=0.9,
    reason="Eligible for return.",
    sources=["returns.md"],
)


def override_get_db():
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=test_engine)
    app.dependency_overrides[get_db] = override_get_db
    yield
    Base.metadata.drop_all(bind=test_engine)
    app.dependency_overrides.clear()


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def alice_token(client):
    client.post("/register", json={"email": "alice@test.com", "password": "alicepass"})
    resp = client.post("/login", json={"email": "alice@test.com", "password": "alicepass"})
    return resp.json()["access_token"]


@pytest.fixture
def bob_token(client):
    client.post("/register", json={"email": "bob@test.com", "password": "bobpass"})
    resp = client.post("/login", json={"email": "bob@test.com", "password": "bobpass"})
    return resp.json()["access_token"]


def test_alice_cannot_read_bobs_ticket(client, alice_token, bob_token):
    with patch("src.main.get_decision", return_value=MOCK_DECISION):
        create_resp = client.post(
            "/tickets",
            json={"message": "Bob's private ticket."},
            headers={"Authorization": f"Bearer {bob_token}"},
        )
    bob_ticket_id = create_resp.json()["id"]

    resp = client.get(
        f"/tickets/{bob_ticket_id}",
        headers={"Authorization": f"Bearer {alice_token}"},
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "Access denied"


def test_bob_cannot_read_alices_ticket(client, alice_token, bob_token):
    with patch("src.main.get_decision", return_value=MOCK_DECISION):
        create_resp = client.post(
            "/tickets",
            json={"message": "Alice's private ticket."},
            headers={"Authorization": f"Bearer {alice_token}"},
        )
    alice_ticket_id = create_resp.json()["id"]

    resp = client.get(
        f"/tickets/{alice_ticket_id}",
        headers={"Authorization": f"Bearer {bob_token}"},
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "Access denied"


def test_alice_can_read_her_own_ticket(client, alice_token):
    with patch("src.main.get_decision", return_value=MOCK_DECISION):
        create_resp = client.post(
            "/tickets",
            json={"message": "Alice's own ticket."},
            headers={"Authorization": f"Bearer {alice_token}"},
        )
    alice_ticket_id = create_resp.json()["id"]

    resp = client.get(
        f"/tickets/{alice_ticket_id}",
        headers={"Authorization": f"Bearer {alice_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["id"] == alice_ticket_id


def test_bob_list_does_not_include_alices_tickets(client, alice_token, bob_token):
    with patch("src.main.get_decision", return_value=MOCK_DECISION):
        client.post(
            "/tickets",
            json={"message": "Alice's ticket."},
            headers={"Authorization": f"Bearer {alice_token}"},
        )
        client.post(
            "/tickets",
            json={"message": "Bob's ticket."},
            headers={"Authorization": f"Bearer {bob_token}"},
        )

    resp = client.get("/tickets", headers={"Authorization": f"Bearer {bob_token}"})
    assert resp.status_code == 200
    tickets = resp.json()
    assert len(tickets) == 1
    assert tickets[0]["message"] == "Bob's ticket."
