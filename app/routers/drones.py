from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
import httpx
import uuid

from app.database import get_db
from app.middleware.auth_middleware import get_current_user
from app.services import drone_service, s3_service, cache_service
from app.schemas.drone_pad import DronePadFilter, DronePadResponse, DronePadCategoryResponse
from app.schemas.common import success
from app.models.drone_pad import DroneType, MusicalKey

router = APIRouter(prefix="/drones", tags=["drones"])


@router.get("/categories")
async def list_drone_categories(db: AsyncSession = Depends(get_db)):
    cached = await cache_service.get("drone:categories")
    if cached is not None:
        return success(cached)
    categories = await drone_service.list_categories(db)
    data = [DronePadCategoryResponse.model_validate(c).model_dump() for c in categories]
    await cache_service.set("drone:categories", data, cache_service.TTL_DRONE_CATEGORIES)
    return success(data)


@router.get("/categories/{category_id}")
async def get_drone_category(category_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    cache_key = f"drone:category:{category_id}"
    cached = await cache_service.get(cache_key)
    if cached is not None:
        return success(cached)
    category = await drone_service.get_category(db, category_id)
    data = DronePadCategoryResponse.model_validate(category).model_dump()
    await cache_service.set(cache_key, data, cache_service.TTL_DRONE_CATEGORIES)
    return success(data)


@router.get("")
async def list_drones(
    key: MusicalKey | None = None,
    drone_type: DroneType | None = None,
    is_free: bool | None = None,
    page: int = 1,
    page_size: int = 50,
    db: AsyncSession = Depends(get_db),
):
    filters = DronePadFilter(
        key=key, drone_type=drone_type, is_free=is_free,
        page=page, page_size=page_size,
    )
    drones, total = await drone_service.list_drones(db, filters)
    return success({
        "items": [DronePadResponse.model_validate(d).model_dump() for d in drones],
        "total": total,
        "page": page,
        "page_size": page_size,
    })


@router.get("/{drone_id}")
async def get_drone(drone_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    drone = await drone_service.get_drone(db, drone_id)
    return success(DronePadResponse.model_validate(drone).model_dump())


@router.get("/{drone_id}/preview")
async def stream_preview(drone_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    drone = await drone_service.get_drone(db, drone_id)
    url = await s3_service.generate_presigned_url(drone.preview_s3_key, expiry_seconds=300)

    async def _stream():
        async with httpx.AsyncClient() as client:
            async with client.stream("GET", url) as resp:
                async for chunk in resp.aiter_bytes(8192):
                    yield chunk

    return StreamingResponse(_stream(), media_type="audio/mpeg")


@router.get("/{drone_id}/download")
async def download_drone(
    drone_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    drone = await drone_service.get_drone(db, drone_id)
    await drone_service.check_download_entitlement(db, user, drone)

    download_url = await s3_service.get_download_url(drone.file_s3_key, expiry_seconds=900)
    drone.download_count += 1
    await db.commit()

    return success({
        "signed_url": download_url,
        "aes_key": drone.aes_key,
        "aes_iv": drone.aes_iv,
        "expires_in_seconds": 900,
    })
