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


@router.post("/webhook/flutterwave")
async def flutterwave_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    verif_hash: str = Header(None, alias="verif-hash"),
):
    payload = await request.body()
    await payment_service.handle_flutterwave_webhook(db, payload, verif_hash)
    return {"received": True}


@router.post("/webhook/paystack")
async def paystack_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    x_paystack_signature: str = Header(None, alias="x-paystack-signature"),
):
    payload = await request.body()
    await payment_service.handle_paystack_webhook(db, payload, x_paystack_signature)
    return {"received": True}
