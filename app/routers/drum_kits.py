import asyncio
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
import uuid

from app.database import get_db
from app.middleware.auth_middleware import get_current_user
from app.services import drum_kit_service, s3_service, cache_service
from app.schemas.drum_kit import (
    DrumKitFilter, DrumKitResponse, DrumKitCategoryResponse,
    DrumKitDownloadResponse, DrumKitCategoryDownloadItem,
    DrumSampleDownloadItem, DOWNLOAD_EXPIRY_SECONDS,
)
from app.schemas.common import success
from app.models.drum_kit import DrumKit, DrumKitCategory
from app.models.download import Download
from app.models.purchase import Purchase
from app.exceptions import NotFoundError, EntitlementError, AppError

router = APIRouter(prefix="/drum-kits", tags=["drum-kits"])


def _list_cache_key(search, is_free, tags, page, page_size) -> str:
    return f"drum_kit:list:{search}:{is_free}:{tags}:{page}:{page_size}"


async def _kit_to_dict(kit) -> dict:
    data = DrumKitResponse.model_validate(kit).model_dump(mode="json")
    if kit.thumbnail_s3_key:
        data["thumbnail_url"] = await s3_service.get_download_url(kit.thumbnail_s3_key)
    return data


@router.get("")
async def list_drum_kits(
    search: str | None = None,
    is_free: bool | None = None,
    tags: str | None = None,
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
):
    cache_key = _list_cache_key(search, is_free, tags, page, page_size)
    cached = await cache_service.get(cache_key)
    if cached is not None:
        return success(cached)

    filters = DrumKitFilter(
        search=search,
        is_free=is_free,
        tags=[t.strip() for t in tags.split(",") if t.strip()] if tags else None,
        page=page,
        page_size=page_size,
    )
    kits, total = await drum_kit_service.list_drum_kits(db, filters)
    data = {
        "items": list(await asyncio.gather(*[_kit_to_dict(k) for k in kits])),
        "total": total,
        "page": page,
        "page_size": page_size,
    }
    await cache_service.set(cache_key, data, cache_service.TTL_DRUM_KIT_LIST)
    return success(data)


@router.get("/{kit_id}")
async def get_drum_kit(kit_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    cache_key = f"drum_kit:detail:{kit_id}"
    cached = await cache_service.get(cache_key)
    if cached is not None:
        return success(cached)

    result = await db.execute(
        select(DrumKit)
        .options(selectinload(DrumKit.categories).selectinload(DrumKitCategory.samples))
        .where(DrumKit.id == kit_id)
    )
    kit = result.scalar_one_or_none()
    if not kit:
        raise NotFoundError(f"Drum kit {kit_id} not found")

    data = await _kit_to_dict(kit)
    await cache_service.set(cache_key, data, cache_service.TTL_DRUM_KIT_DETAIL)
    return success(data)


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
        raise NotFoundError("Category not found")
    return success(DrumKitCategoryResponse.model_validate(category).model_dump())


@router.get("/{kit_id}/download")
async def download_drum_kit(
    kit_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    # Load kit with all categories and their ready samples
    result = await db.execute(
        select(DrumKit)
        .options(selectinload(DrumKit.categories).selectinload(DrumKitCategory.samples))
        .where(DrumKit.id == kit_id)
    )
    kit = result.scalar_one_or_none()
    if not kit:
        raise NotFoundError(f"Drum kit {kit_id} not found")

    # Entitlement check
    if not kit.is_free:
        purchase = await db.scalar(
            select(Purchase).where(
                Purchase.user_id == user.id,
                Purchase.drum_kit_id == kit.id,
            )
        )
        if not purchase:
            raise EntitlementError()

    # Build signed download URLs for every ready sample across all categories
    category_items: list[DrumKitCategoryDownloadItem] = []
    ready_sample_count = 0

    for category in kit.categories:
        sample_items: list[DrumSampleDownloadItem] = []
        for sample in category.samples:
            if sample.status != "ready" or not sample.file_s3_key:
                continue
            signed_url = await s3_service.get_download_url(
                sample.file_s3_key, expiry_seconds=DOWNLOAD_EXPIRY_SECONDS
            )
            sample_items.append(DrumSampleDownloadItem(
                id=sample.id,
                label=sample.label,
                signed_url=signed_url,
                aes_key=sample.aes_key,
                aes_iv=sample.aes_iv,
                duration=sample.duration,
            ))
            ready_sample_count += 1

        if sample_items:
            category_items.append(DrumKitCategoryDownloadItem(
                id=category.id,
                name=category.name,
                samples=sample_items,
            ))

    if ready_sample_count == 0:
        raise AppError("No ready samples available for download yet", status_code=409)

    # Record download
    dl = Download(
        user_id=user.id,
        drum_kit_id=kit.id,
        download_url=f"drum-kit:{kit.id}",  # logical reference; individual URLs are in the response
        expires_at=datetime.now(timezone.utc) + timedelta(seconds=DOWNLOAD_EXPIRY_SECONDS),
    )
    db.add(dl)
    kit.download_count += 1
    await db.commit()

    return success(DrumKitDownloadResponse(
        kit_id=kit.id,
        title=kit.title,
        categories=category_items,
    ).model_dump())
