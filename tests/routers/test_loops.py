import pytest
import uuid
from decimal import Decimal
from app.models.loop import Loop, Genre, TempoFeel
from app.models.user import User, UserRole
from app.services.auth_service import hash_password, create_access_token


async def _create_user(db, role=UserRole.free):
    user = User(
        id=uuid.uuid4(), email=f"{uuid.uuid4()}@test.com",
        password_hash=await hash_password("pass"), full_name="Test", role=role,
    )
    db.add(user)
    await db.commit()
    return user


async def _create_loop(db, user_id, is_free=True):
    loop = Loop(
        id=uuid.uuid4(), title="Test Loop", slug=f"test-loop-{uuid.uuid4().hex[:6]}",
        genre=Genre.afrobeat, bpm=100, key="C major", duration=30,
        tempo_feel=TempoFeel.mid, tags=["test"], price=Decimal("4.99"),
        is_free=is_free, is_paid=not is_free, created_by=user_id,
    )
    db.add(loop)
    await db.commit()
    return loop


@pytest.mark.asyncio
async def test_list_loops_public(client, db_session):
    user = await _create_user(db_session)
    await _create_loop(db_session, user.id)
    resp = await client.get("/api/v1/loops")
    assert resp.status_code == 200
    assert resp.json()["data"]["total"] >= 1


@pytest.mark.asyncio
async def test_get_loop_not_found(client):
    resp = await client.get(f"/api/v1/loops/{uuid.uuid4()}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_download_free_loop_requires_auth(client, db_session):
    user = await _create_user(db_session)
    loop = await _create_loop(db_session, user.id, is_free=True)
    resp = await client.get(f"/api/v1/loops/{loop.id}/download")
    assert resp.status_code == 403  # no auth header
