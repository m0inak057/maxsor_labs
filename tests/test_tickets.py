import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.main import app
from src.database import Base, get_db
from src.schemas import AIDecision

TEST_DB_URL = "sqlite:///./test_tickets.db"
test_engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

MOCK_DECISION = AIDecision(
    action="REQUEST_PHOTOS",
    confidence=0.95,
    reason="Order value exceeds 2000 rupees so photos are required.",
    sources=["damaged_goods.md"],
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
    client.post("/register", json={"email": "alice@example.com", "password": "alicepass"})
    resp = client.post("/login", json={"email": "alice@example.com", "password": "alicepass"})
    return resp.json()["access_token"]


def test_create_ticket_returns_decision(client, alice_token):
    with patch("src.main.get_decision", return_value=MOCK_DECISION):
        resp = client.post(
            "/tickets",
            json={"message": "My order arrived damaged."},
            headers={"Authorization": f"Bearer {alice_token}"},
        )
    assert resp.status_code == 201
    data = resp.json()
    assert data["message"] == "My order arrived damaged."
    assert data["decision"]["action"] == "REQUEST_PHOTOS"
    assert data["decision"]["confidence"] == 0.95
    assert "damaged_goods.md" in data["decision"]["sources"]


def test_create_ticket_requires_auth(client):
    resp = client.post("/tickets", json={"message": "Test message."})
    assert resp.status_code == 403


def test_list_tickets_returns_only_own(client, alice_token):
    with patch("src.main.get_decision", return_value=MOCK_DECISION):
        client.post(
            "/tickets",
            json={"message": "Ticket one."},
            headers={"Authorization": f"Bearer {alice_token}"},
        )
        client.post(
            "/tickets",
            json={"message": "Ticket two."},
            headers={"Authorization": f"Bearer {alice_token}"},
        )

    resp = client.get("/tickets", headers={"Authorization": f"Bearer {alice_token}"})
    assert resp.status_code == 200
    tickets = resp.json()
    assert len(tickets) == 2
    assert all(t["decision"]["action"] == "REQUEST_PHOTOS" for t in tickets)


def test_get_ticket_by_id(client, alice_token):
    with patch("src.main.get_decision", return_value=MOCK_DECISION):
        create_resp = client.post(
            "/tickets",
            json={"message": "Specific ticket."},
            headers={"Authorization": f"Bearer {alice_token}"},
        )
    ticket_id = create_resp.json()["id"]

    resp = client.get(
        f"/tickets/{ticket_id}",
        headers={"Authorization": f"Bearer {alice_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["id"] == ticket_id


def test_get_nonexistent_ticket(client, alice_token):
    resp = client.get("/tickets/99999", headers={"Authorization": f"Bearer {alice_token}"})
    assert resp.status_code == 404
