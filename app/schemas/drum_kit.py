import uuid
from datetime import datetime
from pydantic import BaseModel, field_validator


class DrumKitCreate(BaseModel):
    title: str
    description: str | None = None
    tags: list[str] = []
    is_free: bool = True


class DrumKitCategoryCreate(BaseModel):
    name: str


class DrumSampleResponse(BaseModel):
    id: uuid.UUID
    label: str
    duration: int
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class DrumKitCategoryResponse(BaseModel):
    id: uuid.UUID
    drum_kit_id: uuid.UUID
    name: str
    samples: list[DrumSampleResponse] = []
    created_at: datetime

    model_config = {"from_attributes": True}


class DrumKitResponse(BaseModel):
    id: uuid.UUID
    title: str
    slug: str
    description: str | None
    tags: list[str]
    is_free: bool
    categories: list[DrumKitCategoryResponse] = []
    created_at: datetime

    model_config = {"from_attributes": True}


class DrumKitFilter(BaseModel):
    search: str | None = None
    is_free: bool | None = None
    tags: list[str] | None = None
    page: int = 1
    page_size: int = 20

    @field_validator("page_size")
    @classmethod
    def cap_page_size(cls, v: int) -> int:
        return min(v, 100)
