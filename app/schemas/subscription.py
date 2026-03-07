import uuid
from datetime import datetime
from pydantic import BaseModel
from app.models.subscription import SubscriptionPlan, SubscriptionStatus
from app.models.purchase import PaymentProvider


class SubscriptionInitiateRequest(BaseModel):
    provider: PaymentProvider


class ExtraCreditsInitiateRequest(BaseModel):
    provider: PaymentProvider


class SubscriptionResponse(BaseModel):
    id: uuid.UUID
    plan: SubscriptionPlan
    status: SubscriptionStatus
    ai_quota: int
    ai_quota_used: int
    billing_period_start: datetime
    expires_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}
