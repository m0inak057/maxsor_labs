import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.main import app
from src.database import Base, get_db

TEST_DB_URL = "sqlite:///./test.db"
test_engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


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


def test_register_success(client):
    resp = client.post("/register", json={"email": "test@example.com", "password": "password123"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == "test@example.com"
    assert "id" in data
    assert "password_hash" not in data


def test_register_duplicate_email(client):
    client.post("/register", json={"email": "dup@example.com", "password": "password123"})
    resp = client.post("/register", json={"email": "dup@example.com", "password": "password123"})
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Email already registered"


def test_login_success(client):
    client.post("/register", json={"email": "login@example.com", "password": "password123"})
    resp = client.post("/login", json={"email": "login@example.com", "password": "password123"})
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_wrong_password(client):
    client.post("/register", json={"email": "wrong@example.com", "password": "password123"})
    resp = client.post("/login", json={"email": "wrong@example.com", "password": "wrongpassword"})
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid email or password"


def test_login_unknown_email(client):
    resp = client.post("/login", json={"email": "nobody@example.com", "password": "password123"})
    assert resp.status_code == 401


def test_me_authenticated(client):
    client.post("/register", json={"email": "me@example.com", "password": "password123"})
    login_resp = client.post("/login", json={"email": "me@example.com", "password": "password123"})
    token = login_resp.json()["access_token"]
    resp = client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["email"] == "me@example.com"


def test_me_no_token(client):
    resp = client.get("/me")
    assert resp.status_code == 403


def test_me_invalid_token(client):
    resp = client.get("/me", headers={"Authorization": "Bearer invalidtoken"})
    assert resp.status_code == 401
