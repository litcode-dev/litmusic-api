import pytest


@pytest.mark.asyncio
async def test_register_success(client):
    resp = await client.post("/api/v1/auth/register", json={
        "email": "new@test.com",
        "password": "securepass",
        "full_name": "Test User",
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "success"
    assert body["data"]["email"] == "new@test.com"


@pytest.mark.asyncio
async def test_register_duplicate_email(client):
    payload = {"email": "dup@test.com", "password": "pass1234", "full_name": "Dup"}
    await client.post("/api/v1/auth/register", json=payload)
    resp = await client.post("/api/v1/auth/register", json=payload)
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_login_returns_tokens(client):
    await client.post("/api/v1/auth/register", json={
        "email": "user@test.com", "password": "pass1234", "full_name": "User"
    })
    resp = await client.post("/api/v1/auth/login", json={
        "email": "user@test.com", "password": "pass1234"
    })
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "access_token" in data
    assert "refresh_token" in data


@pytest.mark.asyncio
async def test_login_wrong_password(client):
    await client.post("/api/v1/auth/register", json={
        "email": "x@test.com", "password": "correct", "full_name": "X"
    })
    resp = await client.post("/api/v1/auth/login", json={"email": "x@test.com", "password": "wrong"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_requires_auth(client):
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 403
