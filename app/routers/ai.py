import uuid
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.database import get_db
from app.middleware.auth_middleware import get_current_user
from app.middleware.rate_limit import ai_limiter
from app.services import subscription_service
from app.models.ai_generation import AIGeneration, AIGenerationStatus
from app.schemas.ai_generation import AIGenerateRequest, AIGenerationResponse
from app.schemas.common import success
from app.exceptions import ForbiddenError, PaymentError, NotFoundError

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/generate")
@ai_limiter.limit("10/minute")
async def generate_loop(
    request: Request,
    body: AIGenerateRequest,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    # Guard 1: per-user AI toggle
    if not user.ai_enabled:
        raise ForbiddenError("AI generation has been disabled for your account")

    # Guard 2: active subscription
    sub = await subscription_service.get_active_subscription(db, user.id)
    if not sub:
        raise PaymentError("Premium subscription required for AI generation")

    # Guard 3: quota check
    is_extra = False
    if sub.ai_quota_used >= sub.ai_quota:
        if user.ai_extra_credits <= 0:
            raise PaymentError(
                "Monthly AI quota exhausted. Purchase extra credits to continue."
            )
        user.ai_extra_credits -= 1
        is_extra = True
    else:
        sub.ai_quota_used += 1

    gen = AIGeneration(
        user_id=user.id,
        subscription_id=sub.id if not is_extra else None,
        provider=body.provider,
        prompt=body.prompt,
        style_prompt=body.style_prompt,
        status=AIGenerationStatus.pending,
        is_extra=is_extra,
    )
    db.add(gen)
    await db.commit()
    await db.refresh(gen)

    from app.tasks.ai_tasks import generate_ai_loop_task
    generate_ai_loop_task.delay(str(gen.id))

    return success(AIGenerationResponse.model_validate(gen).model_dump(), "Generation started")


@router.get("/generations")
async def list_my_generations(
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    offset = (page - 1) * page_size
    total = await db.scalar(
        select(func.count()).select_from(AIGeneration).where(AIGeneration.user_id == user.id)
    )
    gens = await db.scalars(
        select(AIGeneration)
        .where(AIGeneration.user_id == user.id)
        .order_by(AIGeneration.created_at.desc())
        .offset(offset).limit(page_size)
    )
    return success({
        "items": [AIGenerationResponse.model_validate(g).model_dump() for g in gens.all()],
        "total": total or 0,
        "page": page,
        "page_size": page_size,
    })


@router.get("/generations/{generation_id}")
async def get_generation(
    generation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    gen = await db.get(AIGeneration, generation_id)
    if not gen:
        raise NotFoundError("Generation not found")
    if gen.user_id != user.id:
        raise ForbiddenError()
    return success(AIGenerationResponse.model_validate(gen).model_dump())
