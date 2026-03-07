import uuid
from datetime import datetime
from pydantic import BaseModel
from app.models.ai_generation import AIProvider, AIGenerationStatus


class AIGenerateRequest(BaseModel):
    prompt: str
    style_prompt: str | None = None
    provider: AIProvider


class AIGenerationResponse(BaseModel):
    id: uuid.UUID
    provider: AIProvider
    prompt: str
    style_prompt: str | None
    status: AIGenerationStatus
    result_loop_id: uuid.UUID | None
    is_extra: bool
    error_message: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
