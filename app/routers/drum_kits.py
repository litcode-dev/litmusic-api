from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
import uuid

from app.database import get_db
from app.services import drum_kit_service, s3_service
from app.schemas.drum_kit import DrumKitFilter, DrumKitResponse, DrumKitCategoryResponse
from app.schemas.common import success
from app.models.drum_kit import DrumKit, DrumKitCategory

router = APIRouter(prefix="/drum-kits", tags=["drum-kits"])


@router.get("")
async def list_drum_kits(
    search: str | None = None,
    is_free: bool | None = None,
    tags: str | None = None,
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
):
    filters = DrumKitFilter(
        search=search,
        is_free=is_free,
        tags=[t.strip() for t in tags.split(",") if t.strip()] if tags else None,
        page=page,
        page_size=page_size,
    )
    kits, total = await drum_kit_service.list_drum_kits(db, filters)
    return success({
        "items": [DrumKitResponse.model_validate(k).model_dump() for k in kits],
        "total": total,
        "page": page,
        "page_size": page_size,
    })


@router.get("/{kit_id}")
async def get_drum_kit(kit_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(DrumKit)
        .options(selectinload(DrumKit.categories).selectinload(DrumKitCategory.samples))
        .where(DrumKit.id == kit_id)
    )
    kit = result.scalar_one_or_none()
    if not kit:
        from app.exceptions import NotFoundError
        raise NotFoundError(f"Drum kit {kit_id} not found")
    return success(DrumKitResponse.model_validate(kit).model_dump())


@router.get("/{kit_id}/categories/{category_id}")
async def get_category(
    kit_id: uuid.UUID,
    category_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(DrumKitCategory)
        .options(selectinload(DrumKitCategory.samples))
        .where(
            DrumKitCategory.id == category_id,
            DrumKitCategory.drum_kit_id == kit_id,
        )
    )
    category = result.scalar_one_or_none()
    if not category:
        from app.exceptions import NotFoundError
        raise NotFoundError("Category not found")
    return success(DrumKitCategoryResponse.model_validate(category).model_dump())
