import uuid
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel
from app.models.loop import Genre


class StemPackCreate(BaseModel):
    title: str
    loop_id: uuid.UUID | None = None
    genre: Genre
    bpm: int
    key: str
    tags: list[str] = []
    price: Decimal
    description: str | None = None


class StemCreate(BaseModel):
    label: str
    duration: int


class StemResponse(BaseModel):
    id: uuid.UUID
    label: str
    duration: int
    created_at: datetime

    model_config = {"from_attributes": True}


class StemPackResponse(BaseModel):
    id: uuid.UUID
    title: str
    slug: str
    loop_id: uuid.UUID | None
    genre: Genre
    bpm: int
    key: str
    tags: list[str]
    price: Decimal
    description: str | None
    stems: list[StemResponse] = []
    created_at: datetime

    model_config = {"from_attributes": True}
