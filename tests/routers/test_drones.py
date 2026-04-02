import pytest
import uuid
from decimal import Decimal
from unittest.mock import patch, AsyncMock
from app.models.drone_pad import DronePad, MusicalKey
from app.models.user import User, UserRole
from app.services.auth_service import hash_password, create_access_token


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
async def test_list_drones_grouped_by_title(client, db_session):
    user = await _create_user(db_session)
    # Two drones same title (different keys) + one with different title
    await _create_drone(db_session, user.id, title="Dark Piano Pad", key=MusicalKey.C)
    await _create_drone(db_session, user.id, title="Dark Piano Pad", key=MusicalKey.D)
    await _create_drone(db_session, user.id, title="Jazz Guitar Loop", key=MusicalKey.A)

    resp = await client.get("/api/v1/drones/titles")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["total"] == 2  # 2 distinct titles
    titles = [item["title"] for item in data["items"]]
    assert "Dark Piano Pad" in titles
    assert "Jazz Guitar Loop" in titles
    piano_group = next(i for i in data["items"] if i["title"] == "Dark Piano Pad")
    assert len(piano_group["drones"]) == 2


@pytest.mark.asyncio
async def test_list_drones_by_title_excludes_processing(client, db_session):
    user = await _create_user(db_session)
    await _create_drone(db_session, user.id, title="Cello Pad", status="processing")
    resp = await client.get("/api/v1/drones/titles")
    assert resp.status_code == 200
    data = resp.json()["data"]
    titles = [item["title"] for item in data["items"]]
    assert "Cello Pad" not in titles
