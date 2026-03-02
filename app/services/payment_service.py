import stripe
import uuid
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.config import get_settings
from app.models.purchase import Purchase, PurchaseType
from app.models.loop import Loop
from app.models.stem_pack import StemPack
from app.models.user import User
from app.exceptions import NotFoundError, PaymentError
from app.schemas.purchase import CheckoutRequest

settings = get_settings()
stripe.api_key = settings.stripe_secret_key


async def create_checkout_session(
    db: AsyncSession,
    user: User,
    request: CheckoutRequest,
) -> dict:
    if request.loop_id:
        product = await db.get(Loop, request.loop_id)
        if not product:
            raise NotFoundError("Loop not found")
        name = product.title
        price_cents = int(product.price * 100)
        metadata = {"loop_id": str(request.loop_id), "user_id": str(user.id)}
    else:
        product = await db.get(StemPack, request.stem_pack_id)
        if not product:
            raise NotFoundError("StemPack not found")
        name = product.title
        price_cents = int(product.price * 100)
        metadata = {"stem_pack_id": str(request.stem_pack_id), "user_id": str(user.id)}

    try:
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{
                "price_data": {
                    "currency": "usd",
                    "unit_amount": price_cents,
                    "product_data": {"name": name},
                },
                "quantity": 1,
            }],
            mode="payment",
            metadata=metadata,
            customer_email=user.email,
            success_url="https://litmusic.app/success?session_id={CHECKOUT_SESSION_ID}",
            cancel_url="https://litmusic.app/cancel",
        )
        return {"checkout_url": session.url, "session_id": session.id}
    except stripe.StripeError as e:
        raise PaymentError(str(e))


async def handle_webhook(db: AsyncSession, payload: bytes, sig_header: str) -> None:
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.stripe_webhook_secret
        )
    except (ValueError, stripe.SignatureVerificationError):
        raise PaymentError("Invalid webhook signature")

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        metadata = session.get("metadata", {})
        user_id = metadata.get("user_id")
        loop_id = metadata.get("loop_id")
        stem_pack_id = metadata.get("stem_pack_id")
        amount = Decimal(session["amount_total"]) / 100

        existing = await db.scalar(
            select(Purchase).where(
                Purchase.stripe_payment_intent_id == session["payment_intent"]
            )
        )
        if existing:
            return

        purchase = Purchase(
            user_id=uuid.UUID(user_id),
            loop_id=uuid.UUID(loop_id) if loop_id else None,
            stem_pack_id=uuid.UUID(stem_pack_id) if stem_pack_id else None,
            stripe_payment_intent_id=session["payment_intent"],
            amount_paid=amount,
            purchase_type=PurchaseType.one_time,
        )
        db.add(purchase)
        await db.commit()

        from app.tasks.notification_tasks import send_purchase_confirmation
        send_purchase_confirmation.delay(str(user_id), str(purchase.id))
