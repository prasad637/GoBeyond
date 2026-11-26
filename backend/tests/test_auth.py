import pytest
import uuid
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "HEALTHY"
    assert data["default_city"] == "Hyderabad"


def test_readiness_check():
    response = client.get("/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["ready"] is True
    assert data["components"]["database"] == "CONNECTED"


def test_login_existing_seeded_admin():
    response = client.post(
        "/api/v1/auth/login",
        json={"login": "admin@gobeyond.com", "password": "Admin@123"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["role"] == "super_admin"
    assert data["email"] == "admin@gobeyond.com"


def test_login_existing_seeded_customer():
    response = client.post(
        "/api/v1/auth/login",
        json={"login": "customer@gobeyond.com", "password": "Customer@123"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["role"] == "customer"


def test_login_invalid_password():
    response = client.post(
        "/api/v1/auth/login",
        json={"login": "admin@gobeyond.com", "password": "WrongPassword!"}
    )
    assert response.status_code == 401
    assert "Invalid credentials" in response.json()["detail"]


def test_register_new_customer_and_get_me():
    suffix = uuid.uuid4().hex[:6]
    new_email = f"testuser_{suffix}@gobeyond.com"
    new_phone = f"91{suffix[:8].ljust(8, '0')}"
    register_res = client.post(
        "/api/v1/auth/register",
        json={
            "email": new_email,
            "phone": new_phone,
            "full_name": "Test User Hyderabad",
            "password": "SecurePassword@123",
            "role": "customer"
        }
    )
    assert register_res.status_code == 201
    reg_data = register_res.json()
    token = reg_data["access_token"]
    assert token is not None
    assert reg_data["role"] == "customer"

    # Call /me with token
    headers = {"Authorization": f"Bearer {token}"}
    me_res = client.get("/api/v1/auth/me", headers=headers)
    assert me_res.status_code == 200
    me_data = me_res.json()
    assert me_data["email"] == new_email
    assert me_data["phone"] == new_phone
    assert "customer" in me_data["roles"]


def test_duplicate_registration_fails():
    res = client.post(
        "/api/v1/auth/register",
        json={
            "email": "customer@gobeyond.com",
            "phone": "9999988888",
            "full_name": "Duplicate Tester",
            "password": "Password@123"
        }
    )
    assert res.status_code == 400
    assert "already exists" in res.json()["detail"]


def test_otp_flow_sandbox():
    phone = "9887766554"
    otp_res = client.post(
        "/api/v1/auth/request-otp",
        json={"phone": phone, "purpose": "login"}
    )
    assert otp_res.status_code == 200
    assert otp_res.json()["sandbox_code"] == "123456"

    verify_res = client.post(
        "/api/v1/auth/verify-otp",
        json={"phone": phone, "otp": "123456", "purpose": "login"}
    )
    assert verify_res.status_code == 200
    assert "access_token" in verify_res.json()
