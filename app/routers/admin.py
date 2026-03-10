from fastapi import APIRouter, Depends, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from decimal import Decimal
from app.database import get_db
from app.middleware.auth_middleware import require_admin, require_producer
from app.services import loop_service, stem_pack_service, drone_service
from app.schemas.loop import LoopCreate, LoopUpdate, LoopResponse
from app.schemas.stem_pack import StemPackCreate, StemCreate, StemPackResponse, StemResponse
from app.schemas.drone_pad import DronePadCreate, DronePadResponse
from app.schemas.user import UserResponse
from app.schemas.common import success
from app.models.loop import Genre, TempoFeel
from app.models.drone_pad import DroneType, MusicalKey
from app.models.user import User, UserRole
from app.exceptions import NotFoundError
import uuid

router = APIRouter(prefix="/admin", tags=["admin"])


# --- Loop endpoints ---

@router.post("/loops")
async def upload_loop(
    file: UploadFile = File(...),
    thumbnail: UploadFile | None = File(None),
    title: str = Form(...),
    genre: Genre = Form(...),
    bpm: int = Form(...),
    key: str = Form(...),
    tempo_feel: TempoFeel = Form(...),
    price: Decimal = Form(...),
    is_free: bool = Form(False),
    tags: str = Form(""),  # comma-separated
    db: AsyncSession = Depends(get_db),
    producer=Depends(require_producer),
):
    data = LoopCreate(
        title=title, genre=genre, bpm=bpm, key=key,
        tempo_feel=tempo_feel, price=price, is_free=is_free,
        tags=[t.strip() for t in tags.split(",") if t.strip()],
    )
    loop = await loop_service.create_loop(db, file, data, producer.id, thumbnail=thumbnail)
    from app.tasks.upload_tasks import process_loop_upload
    process_loop_upload.delay(str(loop.id))
    return success(LoopResponse.model_validate(loop).model_dump(), "Loop upload queued")


@router.get("/loops/{loop_id}/status")
async def loop_upload_status(
    loop_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    producer=Depends(require_producer),
):
    loop = await loop_service.get_loop(db, loop_id)
    return success({"id": str(loop.id), "status": loop.status})


@router.put("/loops/{loop_id}")
async def update_loop(
    loop_id: uuid.UUID,
    body: LoopUpdate,
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_admin),
):
    loop = await loop_service.update_loop(db, loop_id, body)
    return success(LoopResponse.model_validate(loop).model_dump(), "Loop updated")


@router.delete("/loops/{loop_id}")
async def delete_loop(
    loop_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_admin),
):
    await loop_service.delete_loop(db, loop_id)
    return success(message="Loop deleted")


# --- StemPack endpoints ---

@router.post("/stem-packs")
async def create_stem_pack(
    body: StemPackCreate,
    db: AsyncSession = Depends(get_db),
    producer=Depends(require_producer),
):
    pack = await stem_pack_service.create_stem_pack(db, body, producer.id)
    return success(StemPackResponse.model_validate(pack).model_dump(), "StemPack created")


@router.post("/stem-packs/{pack_id}/stems")
async def add_stem(
    pack_id: uuid.UUID,
    file: UploadFile = File(...),
    label: str = Form(...),
    duration: int = Form(...),
    db: AsyncSession = Depends(get_db),
    producer=Depends(require_producer),
):
    data = StemCreate(label=label, duration=duration)
    stem = await stem_pack_service.add_stem_to_pack(db, pack_id, file, data)
    return success(StemResponse.model_validate(stem).model_dump(), "Stem added")


@router.put("/stem-packs/{pack_id}")
async def update_stem_pack(
    pack_id: uuid.UUID,
    body: StemPackCreate,
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_admin),
):
    from app.models.stem_pack import StemPack
    pack = await db.get(StemPack, pack_id)
    if not pack:
        raise NotFoundError("StemPack not found")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(pack, field, value)
    await db.commit()
    await db.refresh(pack)
    return success(StemPackResponse.model_validate(pack).model_dump(), "StemPack updated")


@router.delete("/stem-packs/{pack_id}")
async def delete_stem_pack(
    pack_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_admin),
):
    from app.models.stem_pack import StemPack, Stem
    from app.services import s3_service
    pack = await db.get(StemPack, pack_id)
    if not pack:
        raise NotFoundError("StemPack not found")
    stems = await db.scalars(select(Stem).where(Stem.stem_pack_id == pack_id))
    for stem in stems.all():
        if stem.file_s3_key:
            await s3_service.delete_object(stem.file_s3_key)
        await db.delete(stem)
    await db.delete(pack)
    await db.commit()
    return success(message="StemPack deleted")


# --- User management endpoints (admin only) ---

@router.get("/users")
async def list_users(
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_admin),
):
    offset = (page - 1) * page_size
    total = await db.scalar(select(func.count()).select_from(User))
    users = await db.scalars(select(User).offset(offset).limit(page_size))
    return success({
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [UserResponse.model_validate(u).model_dump() for u in users.all()],
    })


@router.put("/users/{user_id}/role")
async def change_user_role(
    user_id: uuid.UUID,
    role: UserRole,
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_admin),
):
    user = await db.get(User, user_id)
    if not user:
        raise NotFoundError("User not found")
    user.role = role
    await db.commit()
    await db.refresh(user)
    return success(UserResponse.model_validate(user).model_dump(), "Role updated")


# --- AI administration ---

@router.put("/users/{user_id}/ai-enabled")
async def toggle_user_ai(
    user_id: uuid.UUID,
    enabled: bool,
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_admin),
):
    user = await db.get(User, user_id)
    if not user:
        raise NotFoundError("User not found")
    user.ai_enabled = enabled
    await db.commit()
    return success(
        {"ai_enabled": user.ai_enabled},
        f"AI {'enabled' if enabled else 'disabled'} for user",
    )


@router.get("/ai/generations")
async def list_all_generations(
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_admin),
):
    from app.models.ai_generation import AIGeneration
    from app.schemas.ai_generation import AIGenerationResponse
    offset = (page - 1) * page_size
    total = await db.scalar(select(func.count()).select_from(AIGeneration))
    gens = await db.scalars(
        select(AIGeneration)
        .order_by(AIGeneration.created_at.desc())
        .offset(offset).limit(page_size)
    )
    return success({
        "items": [AIGenerationResponse.model_validate(g).model_dump() for g in gens.all()],
        "total": total or 0,
        "page": page,
        "page_size": page_size,
    })


# --- Drone pad administration ---

@router.post("/drones")
async def upload_drone(
    file: UploadFile = File(...),
    thumbnail: UploadFile | None = File(None),
    title: str = Form(...),
    drone_type: DroneType = Form(...),
    key: MusicalKey = Form(...),
    price: Decimal = Form(...),
    is_free: bool = Form(False),
    db: AsyncSession = Depends(get_db),
    producer=Depends(require_producer),
):
    data = DronePadCreate(title=title, drone_type=drone_type, key=key, price=price, is_free=is_free)
    drone = await drone_service.create_drone(db, file, data, producer.id, thumbnail=thumbnail)
    from app.tasks.upload_tasks import process_drone_upload
    process_drone_upload.delay(str(drone.id))
    return success(DronePadResponse.model_validate(drone).model_dump(), "Drone pad upload queued")


@router.get("/drones/{drone_id}/status")
async def drone_upload_status(
    drone_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    producer=Depends(require_producer),
):
    drone = await drone_service.get_drone(db, drone_id)
    return success({"id": str(drone.id), "status": drone.status})


@router.delete("/drones/{drone_id}")
async def delete_drone(
    drone_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_admin),
):
    await drone_service.delete_drone(db, drone_id)
    return success(message="Drone pad deleted")
