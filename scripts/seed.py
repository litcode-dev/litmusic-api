"""
Seed the database with test users and loops.
Run: python -m scripts.seed
"""
import asyncio
import uuid
from decimal import Decimal
from sqlalchemy import select
from app.database import AsyncSessionLocal, engine, Base
from app.models.user import User, UserRole
from app.models.loop import Loop, Genre, TempoFeel
from app.services.auth_service import hash_password


async def seed():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:
        # Skip users that already exist
        existing_emails = set(
            await db.scalars(select(User.email))
        )

        users_to_add = []
        if "admin@litmusic.app" not in existing_emails:
            users_to_add.append(User(
                id=uuid.uuid4(),
                email="admin@litmusic.app",
                password_hash=await hash_password("admin1234"),
                full_name="LitMusic Admin",
                role=UserRole.admin,
            ))
        if "producer@litmusic.app" not in existing_emails:
            users_to_add.append(User(
                id=uuid.uuid4(),
                email="producer@litmusic.app",
                password_hash=await hash_password("producer1234"),
                full_name="Test Producer",
                role=UserRole.producer,
            ))

        if users_to_add:
            db.add_all(users_to_add)
            await db.flush()

        # Resolve admin id for loop FK
        admin = await db.scalar(select(User).where(User.email == "admin@litmusic.app"))

        # Skip loop if already seeded
        existing_loop = await db.scalar(
            select(Loop).where(Loop.slug == "afro-vibes-loop-1-seed")
        )
        if not existing_loop:
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
