import pytest
import uuid
from decimal import Decimal
from unittest.mock import patch, AsyncMock
from app.models.drone_pad import DronePad, MusicalKey
from app.models.user import User, UserRole
from app.services.auth_service import hash_password, create_access_token
from app.schemas.drone_pad import DronePadFilter


async def _create_user(db, role=UserRole.user):
    user = User(
        id=uuid.uuid4(), email=f"{uuid.uuid4()}@test.com",
        password_hash=await hash_password("pass"), full_name="Test", role=role,
    )
    db.add(user)
    await db.commit()
    return user


async def _create_drone(db, user_id, title="Dark Piano Pad", key=MusicalKey.C, is_free=True, status="ready"):
    drone = DronePad(
        id=uuid.uuid4(), title=title, key=key,
        duration=30, price=Decimal("0.00"), is_free=is_free,
        created_by=user_id, status=status,
    )
    db.add(drone)
    await db.commit()
    return drone


@pytest.mark.asyncio
async def test_list_drones_filter_by_title(client, db_session):
    user = await _create_user(db_session)
    await _create_drone(db_session, user.id, title="Dark Piano Pad")
    await _create_drone(db_session, user.id, title="Jazz Guitar Loop")
    resp = await client.get("/api/v1/drones?title=piano")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["total"] == 1
    assert data["items"][0]["title"] == "Dark Piano Pad"


@pytest.mark.asyncio
async def test_download_by_title_returns_items_for_free_drones(client, db_session):
    user = await _create_user(db_session)
    await _create_drone(db_session, user.id, title="Dark Piano Pad", key=MusicalKey.C, is_free=True, status="ready")

    # Give the drone a fake file_s3_key so it qualifies for download
    from sqlalchemy import select
    drone = (await db_session.scalars(select(DronePad).where(DronePad.title == "Dark Piano Pad"))).first()
    drone.file_s3_key = "drones/fake-key.wav"
    await db_session.commit()

    token = create_access_token({"sub": str(user.id), "role": user.role.value})
    with patch(
        "app.services.s3_service.get_download_url",
        new=AsyncMock(return_value="https://signed.url/file.wav"),
    ):
        resp = await client.get(
            "/api/v1/drones/download?title=piano",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["total"] == 1
    assert data["items"][0]["title"] == "Dark Piano Pad"
    assert data["items"][0]["signed_url"] == "https://signed.url/file.wav"
    assert data["items"][0]["expires_in_seconds"] == 900


@pytest.mark.asyncio
async def test_download_by_title_requires_auth(client):
    resp = await client.get("/api/v1/drones/download?title=piano")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_download_by_title_empty_string_returns_400(client, db_session):
    user = await _create_user(db_session)
    token = create_access_token({"sub": str(user.id), "role": user.role.value})
    resp = await client.get(
        "/api/v1/drones/download?title=",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_download_by_title_missing_param_returns_422(client, db_session):
    user = await _create_user(db_session)
    token = create_access_token({"sub": str(user.id), "role": user.role.value})
    resp = await client.get(
        "/api/v1/drones/download",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_download_by_title_no_match_returns_empty(client, db_session):
    user = await _create_user(db_session)
    token = create_access_token({"sub": str(user.id), "role": user.role.value})
    resp = await client.get(
        "/api/v1/drones/download?title=nonexistentxyz",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["total"] == 0
    assert data["items"] == []


@pytest.mark.asyncio
async def test_download_by_title_excludes_unpurchased_paid_drone(client, db_session):
    user = await _create_user(db_session)
    paid_drone = await _create_drone(
        db_session, user.id, title="Paid Cello Pad", key=MusicalKey.C, is_free=False, status="ready"
    )
    # Give it a file_s3_key
    paid_drone.file_s3_key = "drones/paid-key.wav"
    await db_session.commit()

    token = create_access_token({"sub": str(user.id), "role": user.role.value})
    resp = await client.get(
        "/api/v1/drones/download?title=cello",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["total"] == 0
    assert data["items"] == []
