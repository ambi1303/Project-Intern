from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.db.base_class import Base
from app.db.session import get_db
from app.core.config import settings

# Create test database
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)

def test_register_user():
    response = client.post(
        "/api/v1/register",
        json={
            "email": "test@example.com",
            "password": "testpassword",
            "full_name": "Test User"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "test@example.com"
    assert data["full_name"] == "Test User"
    assert "id" in data

def test_login():
    response = client.post(
        "/api/v1/login",
        data={
            "username": "test@example.com",
            "password": "testpassword"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

def test_get_wallet():
    # First login to get token
    login_response = client.post(
        "/api/v1/login",
        data={
            "username": "test@example.com",
            "password": "testpassword"
        }
    )
    token = login_response.json()["access_token"]
    
    # Get wallet with token
    response = client.get(
        "/api/v1/wallet",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "balance" in data
    assert "currency" in data

def test_create_transaction():
    # First login to get token
    login_response = client.post(
        "/api/v1/login",
        data={
            "username": "test@example.com",
            "password": "testpassword"
        }
    )
    token = login_response.json()["access_token"]
    
    # Create deposit transaction
    response = client.post(
        "/api/v1/transactions",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "amount": 100.0,
            "transaction_type": "deposit",
            "description": "Test deposit"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["amount"] == 100.0
    assert data["transaction_type"] == "deposit"
    assert data["status"] == "completed"

def test_insufficient_balance():
    # First login to get token
    login_response = client.post(
        "/api/v1/login",
        data={
            "username": "test@example.com",
            "password": "testpassword"
        }
    )
    token = login_response.json()["access_token"]
    
    # Try to withdraw more than balance
    response = client.post(
        "/api/v1/transactions",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "amount": 1000.0,
            "transaction_type": "withdrawal",
            "description": "Test withdrawal"
        }
    )
    assert response.status_code == 400
    assert "Insufficient balance" in response.json()["detail"] 