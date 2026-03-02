from fastapi import APIRouter, Depends, Request, Header
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.middleware.auth_middleware import get_current_user
from app.middleware.rate_limit import limiter
from app.services import payment_service
from app.schemas.purchase import CheckoutRequest
from app.schemas.common import success

router = APIRouter(prefix="/payments", tags=["payments"])


@router.post("/create-checkout")
@limiter.limit("10/minute")
async def create_checkout(
    request: Request,
    body: CheckoutRequest,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    result = await payment_service.create_checkout_session(db, user, body)
    return success(result, "Checkout session created")


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    stripe_signature: str = Header(None, alias="stripe-signature"),
):
    payload = await request.body()
    await payment_service.handle_webhook(db, payload, stripe_signature)
    return {"received": True}
