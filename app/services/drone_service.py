import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from fastapi import UploadFile

from app.models.drone_pad import DronePad, DronePadCategory
from app.models.purchase import Purchase
from app.models.user import User
from app.schemas.drone_pad import DronePadCreate, DronePadCategoryCreate, DronePadFilter
from app.exceptions import NotFoundError, EntitlementError
from app.services import s3_service
from app.utils.audio_validator import validate_wav_upload


async def create_category(
    db: AsyncSession,
    data: DronePadCategoryCreate,
    created_by: uuid.UUID,
) -> DronePadCategory:
    existing = await db.scalar(
        select(DronePadCategory).where(DronePadCategory.name == data.name)
    )
    if existing:
        from app.exceptions import AppError
        raise AppError(f"Category '{data.name}' already exists", status_code=409)
    category = DronePadCategory(name=data.name, description=data.description, created_by=created_by)
    db.add(category)
    await db.commit()
    await db.refresh(category)
    return category


async def get_category(db: AsyncSession, category_id: uuid.UUID) -> DronePadCategory:
    category = await db.get(DronePadCategory, category_id)
    if not category:
        raise NotFoundError(f"Drone pad category {category_id} not found")
    return category


async def list_categories(db: AsyncSession) -> list[DronePadCategory]:
    result = await db.scalars(select(DronePadCategory).order_by(DronePadCategory.name))
    return list(result.all())


async def delete_category(db: AsyncSession, category_id: uuid.UUID) -> None:
    category = await get_category(db, category_id)
    # Nullify category_id on associated drones (ON DELETE SET NULL handles it at DB level,
    # but we do it explicitly so in-flight ORM objects stay consistent)
    await db.execute(
        DronePad.__table__.update()
        .where(DronePad.category_id == category_id)
        .values(category_id=None)
    )
    await db.delete(category)
    await db.commit()


async def create_drone(
    db: AsyncSession,
    file: UploadFile,
    data: DronePadCreate,
    created_by: uuid.UUID,
    thumbnail: UploadFile | None = None,
) -> DronePad:
    wav_bytes = await validate_wav_upload(file)

    drone_id = str(uuid.uuid4())
    raw_key = s3_service.s3_key_for_raw_drone(drone_id)
    await s3_service.upload_bytes(raw_key, wav_bytes, "audio/wav")

    thumb_key = None
    if thumbnail:
        thumb_bytes = await thumbnail.read()
        content_type = thumbnail.content_type or "image/jpeg"
        ext = content_type.split("/")[-1] if "/" in content_type else "jpg"
        thumb_key = s3_service.s3_key_for_drone_thumbnail(drone_id, ext)
        await s3_service.upload_bytes(thumb_key, thumb_bytes, content_type)

    drone = DronePad(
        id=uuid.UUID(drone_id),
        title=data.title,
        key=data.key,
        duration=0,
        price=data.price,
        is_free=data.is_free,
        category_id=data.category_id,
        thumbnail_s3_key=thumb_key,
        created_by=created_by,
        status="processing",
    )
    db.add(drone)
    await db.commit()
    await db.refresh(drone)
    return drone


async def get_drone(db: AsyncSession, drone_id: uuid.UUID) -> DronePad:
    drone = await db.get(DronePad, drone_id)
    if not drone:
        raise NotFoundError(f"Drone pad {drone_id} not found")
    return drone


async def list_drones(db: AsyncSession, filters: DronePadFilter) -> tuple[list[DronePad], int]:
    q = select(DronePad)
    if filters.key:
        q = q.where(DronePad.key == filters.key)
    if filters.is_free is not None:
        q = q.where(DronePad.is_free == filters.is_free)

    count_q = select(func.count()).select_from(q.subquery())
    total = await db.scalar(count_q)

    q = q.order_by(DronePad.key)
    q = q.offset((filters.page - 1) * filters.page_size).limit(filters.page_size)
    result = await db.scalars(q)
    return list(result.all()), total or 0


async def check_download_entitlement(
    db: AsyncSession, user: User, drone: DronePad
) -> None:
    if drone.is_free:
        return
    purchase = await db.scalar(
        select(Purchase).where(
            Purchase.user_id == user.id,
            Purchase.drone_pad_id == drone.id,
        )
    )
    if not purchase:
        raise EntitlementError()


async def delete_drone(db: AsyncSession, drone_id: uuid.UUID) -> None:
    drone = await get_drone(db, drone_id)
    if drone.file_s3_key:
        await s3_service.delete_object(drone.file_s3_key)
    if drone.preview_s3_key:
        await s3_service.delete_object(drone.preview_s3_key)
    if drone.thumbnail_s3_key:
        await s3_service.delete_object(drone.thumbnail_s3_key)
    await db.delete(drone)
    await db.commit()
