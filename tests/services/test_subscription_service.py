import pytest
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from app.models.subscription import Subscription, SubscriptionStatus, SubscriptionPlan
from app.models.purchase import PaymentProvider
from app.models.user import User, UserRole
from app.services.auth_service import hash_password
from app.services import subscription_service


async def _create_user(db):
    user = User(
        id=uuid.uuid4(), email=f"{uuid.uuid4()}@test.com",
        password_hash=await hash_password("pass"), full_name="Test",
        role=UserRole.user,
    )
    db.add(user)
    await db.commit()
    return user


@pytest.mark.asyncio
async def test_create_subscription(db_session):
    user = await _create_user(db_session)
    sub = await subscription_service.create_subscription(
        db_session, user.id, PaymentProvider.paystack, "ref-001", Decimal("2000")
    )
    assert sub.status == SubscriptionStatus.active
    assert sub.ai_quota == 10
    assert sub.ai_quota_used == 0
    assert sub.expires_at > datetime.now(timezone.utc)


@pytest.mark.asyncio
async def test_get_active_subscription_returns_none_when_expired(db_session):
    user = await _create_user(db_session)
    now = datetime.now(timezone.utc)
    expired_sub = Subscription(
        id=uuid.uuid4(), user_id=user.id, plan=SubscriptionPlan.premium,
        status=SubscriptionStatus.active, provider=PaymentProvider.paystack,
        payment_reference="expired-ref", amount_paid=Decimal("2000"),
        ai_quota=10, ai_quota_used=0,
        billing_period_start=now - timedelta(days=31),
        expires_at=now - timedelta(days=1),
    )
    db_session.add(expired_sub)
    await db_session.commit()
    result = await subscription_service.get_active_subscription(db_session, user.id)
    assert result is None


@pytest.mark.asyncio
async def test_renew_creates_new_row_and_expires_old(db_session):
    user = await _create_user(db_session)
    sub = await subscription_service.create_subscription(
        db_session, user.id, PaymentProvider.paystack, "ref-002", Decimal("2000")
    )
    sub.ai_quota_used = 7
    await db_session.commit()

    new_sub = await subscription_service.renew_subscription(
        db_session, user.id, PaymentProvider.paystack, "ref-003", Decimal("2000")
    )
    await db_session.refresh(sub)
    assert sub.status == SubscriptionStatus.expired
    assert new_sub.ai_quota_used == 0
    assert new_sub.status == SubscriptionStatus.active
