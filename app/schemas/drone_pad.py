import uuid
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, model_validator, Field
from app.models.drone_pad import DroneType, MusicalKey


class DronePadCreate(BaseModel):
    title: str
    drone_type: DroneType
    key: MusicalKey
    price: Decimal
    is_free: bool = False


class DronePadResponse(BaseModel):
    id: uuid.UUID
    title: str
    drone_type: DroneType
    key: MusicalKey
    duration: int
    price: Decimal
    is_free: bool
    preview_s3_key: str | None = Field(default=None, exclude=True)
    thumbnail_s3_key: str | None = Field(default=None, exclude=True)
    preview_url: str | None = None
    thumbnail_url: str | None = None
    download_count: int
    created_at: datetime

    model_config = {"from_attributes": True}

    @model_validator(mode="after")
    def build_urls(self) -> "DronePadResponse":
        from app.config import get_settings
        base = get_settings().s3_cloudfront_url.rstrip("/")
        if self.preview_s3_key:
            self.preview_url = f"{base}/{self.preview_s3_key}" if base else self.preview_s3_key
        if self.thumbnail_s3_key:
            self.thumbnail_url = f"{base}/{self.thumbnail_s3_key}" if base else self.thumbnail_s3_key
        return self


class DronePadFilter(BaseModel):
    key: MusicalKey | None = None
    drone_type: DroneType | None = None
    is_free: bool | None = None
    page: int = 1
    page_size: int = 50
