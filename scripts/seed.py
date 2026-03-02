"""
Seed the database with test users and loops.
Run: python scripts/seed.py
"""
import asyncio
import uuid
from decimal import Decimal
from app.database import AsyncSessionLocal, engine, Base
from app.models.user import User, UserRole
from app.models.loop import Loop, Genre, TempoFeel
from app.services.auth_service import hash_password


async def seed():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:
        admin = User(
            id=uuid.uuid4(),
            email="admin@litmusic.app",
            password_hash=await hash_password("admin1234"),
            full_name="LitMusic Admin",
            role=UserRole.admin,
        )
        user = User(
            id=uuid.uuid4(),
            email="producer@litmusic.app",
            password_hash=await hash_password("producer1234"),
            full_name="Test Producer",
            role=UserRole.free,
        )
        db.add_all([admin, user])
        await db.flush()

        loop = Loop(
            id=uuid.uuid4(),
            title="Afro Vibes Loop 1",
            slug="afro-vibes-loop-1-seed",
            genre=Genre.afrobeat,
            bpm=100,
            key="A minor",
            duration=32,
            tempo_feel=TempoFeel.mid,
            tags=["afrobeat", "drums", "vibes"],
            price=Decimal("4.99"),
            is_free=True,
            is_paid=False,
            created_by=admin.id,
        )
        db.add(loop)
        await db.commit()
        print("Seed complete.")
        print("  Admin:    admin@litmusic.app / admin1234")
        print("  Producer: producer@litmusic.app / producer1234")


if __name__ == "__main__":
    asyncio.run(seed())
