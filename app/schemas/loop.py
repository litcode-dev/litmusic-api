import uuid
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, field_validator
from app.models.loop import Genre, TempoFeel


class LoopCreate(BaseModel):
    title: str
    genre: Genre
    bpm: int
    key: str
    tempo_feel: TempoFeel
    tags: list[str] = []
    price: Decimal
    is_free: bool = False

    @field_validator("bpm")
    @classmethod
    def bpm_range(cls, v: int) -> int:
        if not (60 <= v <= 140):
            raise ValueError("BPM must be between 60 and 140")
        return v


class LoopUpdate(BaseModel):
    title: str | None = None
    genre: Genre | None = None
    bpm: int | None = None
    key: str | None = None
    tempo_feel: TempoFeel | None = None
    tags: list[str] | None = None
    price: Decimal | None = None
    is_free: bool | None = None

    @field_validator("bpm")
    @classmethod
    def bpm_range(cls, v: int | None) -> int | None:
        if v is not None and not (60 <= v <= 140):
            raise ValueError("BPM must be between 60 and 140")
        return v


class LoopResponse(BaseModel):
    id: uuid.UUID
    title: str
    slug: str
    genre: Genre
    bpm: int
    key: str
    duration: int
    tempo_feel: TempoFeel
    tags: list[str]
    price: Decimal
    is_free: bool
    is_paid: bool
    preview_s3_key: str | None
    waveform_data: list | None
    download_count: int
    play_count: int
    created_at: datetime

    model_config = {"from_attributes": True}


class LoopFilter(BaseModel):
    genre: Genre | None = None
    bpm_min: int | None = None
    bpm_max: int | None = None
    key: str | None = None
    tempo_feel: TempoFeel | None = None
    tags: list[str] | None = None
    is_free: bool | None = None
    sort: str = "newest"
    page: int = 1
    page_size: int = 20
