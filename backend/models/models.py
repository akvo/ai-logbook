import uuid
import enum
from datetime import datetime, date
from typing import Optional, List

from sqlalchemy import (
    String,
    Text,
    Float,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Enum as SQLEnum,
    ARRAY,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db import Base


class RecordType(str, enum.Enum):
    SEED_PURCHASE_AND_SOWING = "seed_purchase_and_sowing"
    HAZARD_EVALUATION = "hazard_evaluation"
    CHEMICAL_SPRAY = "chemical_spray"
    CHEMICAL_PURCHASE = "chemical_purchase"
    CHEMICAL_DISPOSAL = "chemical_disposal"
    POST_HARVEST_CHEMICAL_USAGE = "post_harvest_chemical_usage"
    FERTILIZER_APPLICATION = "fertilizer_application"
    IRRIGATION = "irrigation"
    SPRAYING_TOOL_SANITATION = "spraying_tool_sanitation"
    HARVEST_AND_PACKAGING = "harvest_and_packaging"
    TRAINING_UPDATE = "training_update"
    CORRECTION_REPORT = "correction_report"
    UNKNOWN = "unknown"


class MessageDirection(str, enum.Enum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class Farmer(Base):
    __tablename__ = "farmers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    external_id: Mapped[str] = mapped_column(
        String(100), unique=True, index=True
    )
    name: Mapped[str] = mapped_column(String(255))
    phone_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    records: Mapped[List["Record"]] = relationship(
        "Record", back_populates="farmer", cascade="all, delete-orphan"
    )
    messages: Mapped[List["Message"]] = relationship(
        "Message", back_populates="farmer", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Farmer {self.external_id}: {self.name}>"


class Record(Base):
    __tablename__ = "records"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    farmer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("farmers.id", ondelete="CASCADE")
    )
    message_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("messages.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Record data
    record_type: Mapped[RecordType] = mapped_column(
        SQLEnum(RecordType), index=True
    )
    occurred_at: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    data: Mapped[dict] = mapped_column(JSONB, default=dict)

    # Source info
    source_channel: Mapped[str] = mapped_column(
        String(50), default="whatsapp"
    )
    source_input_mode: Mapped[str] = mapped_column(
        String(20), default="text"
    )
    source_language: Mapped[str] = mapped_column(
        String(10), default="unknown"
    )

    # Quality metrics
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    missing_fields: Mapped[List[str]] = mapped_column(
        ARRAY(String), default=list
    )
    needs_followup: Mapped[bool] = mapped_column(Boolean, default=False)
    quality_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Audit
    raw_transcript: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )

    # Relationships
    farmer: Mapped["Farmer"] = relationship("Farmer", back_populates="records")
    message: Mapped[Optional["Message"]] = relationship(
        "Message", back_populates="records"
    )

    def __repr__(self) -> str:
        return f"<Record {self.record_type.value} @ {self.occurred_at}>"


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    farmer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("farmers.id", ondelete="CASCADE")
    )
    twilio_message_sid: Mapped[str] = mapped_column(
        String(100), unique=True, index=True
    )
    direction: Mapped[MessageDirection] = mapped_column(
        SQLEnum(MessageDirection)
    )
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    media_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    processed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )

    # Relationships
    farmer: Mapped["Farmer"] = relationship("Farmer", back_populates="messages")
    records: Mapped[List["Record"]] = relationship(
        "Record", back_populates="message"
    )

    def __repr__(self) -> str:
        return f"<Message {self.twilio_message_sid} ({self.direction.value})>"
