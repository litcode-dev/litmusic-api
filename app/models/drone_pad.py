import uuid
import enum
from datetime import datetime
from decimal import Decimal
from sqlalchemy import (
    String, Integer, Boolean, Numeric, Text,
    DateTime, Enum as SAEnum, ForeignKey, func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class DroneType(str, enum.Enum):
    warm = "warm"
    shimmer = "shimmer"
    dark = "dark"
    bright = "bright"
    orchestral = "orchestral"
    ethereal = "ethereal"


class MusicalKey(str, enum.Enum):
    C = "C"
    C_sharp = "C#"
    D = "D"
    D_sharp = "D#"
    E = "E"
    F = "F"
    F_sharp = "F#"
    G = "G"
    G_sharp = "G#"
    A = "A"
    A_sharp = "A#"
    B = "B"


class DronePad(Base):
    __tablename__ = "drone_pads"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    drone_type: Mapped[DroneType] = mapped_column(SAEnum(DroneType), nullable=False, index=True)
    key: Mapped[MusicalKey] = mapped_column(SAEnum(MusicalKey), nullable=False, index=True)
    duration: Mapped[int] = mapped_column(Integer, nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    is_free: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    file_s3_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    preview_s3_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    thumbnail_s3_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    aes_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    aes_iv: Mapped[str | None] = mapped_column(Text, nullable=True)
    download_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="ready", server_default="ready", nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
