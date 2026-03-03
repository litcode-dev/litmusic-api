import uuid
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from app.models.like import Like
from app.models.loop import Loop
from app.models.stem_pack import StemPack


async def like_loop(db: AsyncSession, user_id: uuid.UUID, loop_id: uuid.UUID) -> bool:
    """Like a loop. Returns True if liked, False if already liked."""
    like = Like(user_id=user_id, loop_id=loop_id)
    db.add(like)
    try:
        await db.commit()
        return True
    except IntegrityError:
        await db.rollback()
        return False


async def unlike_loop(db: AsyncSession, user_id: uuid.UUID, loop_id: uuid.UUID) -> bool:
    """Unlike a loop. Returns True if removed, False if not found."""
    like = await db.scalar(
        select(Like).where(Like.user_id == user_id, Like.loop_id == loop_id)
    )
    if not like:
        return False
    await db.delete(like)
    await db.commit()
    return True


async def like_stem_pack(db: AsyncSession, user_id: uuid.UUID, pack_id: uuid.UUID) -> bool:
    """Like a stem pack. Returns True if liked, False if already liked."""
    like = Like(user_id=user_id, stem_pack_id=pack_id)
    db.add(like)
    try:
        await db.commit()
        return True
    except IntegrityError:
        await db.rollback()
        return False


async def unlike_stem_pack(db: AsyncSession, user_id: uuid.UUID, pack_id: uuid.UUID) -> bool:
    """Unlike a stem pack. Returns True if removed, False if not found."""
    like = await db.scalar(
        select(Like).where(Like.user_id == user_id, Like.stem_pack_id == pack_id)
    )
    if not like:
        return False
    await db.delete(like)
    await db.commit()
    return True


async def get_liked_loops(
    db: AsyncSession, user_id: uuid.UUID, page: int = 1, page_size: int = 20
) -> tuple[list[Loop], int]:
    subq = (
        select(Like.loop_id)
        .where(Like.user_id == user_id, Like.loop_id.isnot(None))
        .subquery()
    )
    total = await db.scalar(select(func.count()).select_from(subq))
    q = (
        select(Loop)
        .where(Loop.id.in_(select(subq)))
        .order_by(Loop.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.scalars(q)
    return list(result.all()), total or 0


async def get_liked_stem_packs(
    db: AsyncSession, user_id: uuid.UUID, page: int = 1, page_size: int = 20
) -> tuple[list[StemPack], int]:
    subq = (
        select(Like.stem_pack_id)
        .where(Like.user_id == user_id, Like.stem_pack_id.isnot(None))
        .subquery()
    )
    total = await db.scalar(select(func.count()).select_from(subq))
    q = (
        select(StemPack)
        .where(StemPack.id.in_(select(subq)))
        .order_by(StemPack.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.scalars(q)
    return list(result.all()), total or 0
