import uuid
from datetime import datetime, date
from typing import Optional, List, Any
from enum import Enum

from pydantic import BaseModel, Field


class RecordType(str, Enum):
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


class InputMode(str, Enum):
    VOICE = "voice"
    TEXT = "text"


class SourceLanguage(str, Enum):
    ID = "id"
    EN = "en"
    MY = "my"
    UNKNOWN = "unknown"


# Farmer schemas
class FarmerBase(BaseModel):
    external_id: str = Field(..., max_length=100)
    name: str = Field(..., max_length=255)
    phone_number: Optional[str] = Field(None, max_length=50)


class FarmerCreate(FarmerBase):
    pass


class FarmerUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    phone_number: Optional[str] = Field(None, max_length=50)


class FarmerResponse(FarmerBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class FarmerWithRecords(FarmerResponse):
    records: List["RecordResponse"] = []


# Quality schema (matches prompt.txt structure)
class QualityInfo(BaseModel):
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    missing_fields: List[str] = Field(default_factory=list)
    needs_followup: bool = False
    notes: Optional[str] = None


# Source schema (matches prompt.txt structure)
class SourceInfo(BaseModel):
    channel: str = "whatsapp"
    input_mode: InputMode = InputMode.TEXT
    language: SourceLanguage = SourceLanguage.UNKNOWN
    message_id: Optional[str] = None


# Record schemas
class RecordBase(BaseModel):
    record_type: RecordType
    occurred_at: Optional[date] = None
    data: dict = Field(default_factory=dict)


class RecordCreate(RecordBase):
    farmer_id: uuid.UUID
    source_channel: str = "whatsapp"
    source_input_mode: str = "text"
    source_language: str = "unknown"
    confidence: float = 0.0
    missing_fields: List[str] = Field(default_factory=list)
    needs_followup: bool = False
    quality_notes: Optional[str] = None
    raw_transcript: Optional[str] = None


class RecordUpdate(BaseModel):
    record_type: Optional[RecordType] = None
    occurred_at: Optional[date] = None
    data: Optional[dict] = None
    confidence: Optional[float] = None
    missing_fields: Optional[List[str]] = None
    needs_followup: Optional[bool] = None
    quality_notes: Optional[str] = None


class RecordResponse(RecordBase):
    id: uuid.UUID
    farmer_id: uuid.UUID
    message_id: Optional[uuid.UUID] = None
    source_channel: str
    source_input_mode: str
    source_language: str
    confidence: float
    missing_fields: List[str]
    needs_followup: bool
    quality_notes: Optional[str]
    raw_transcript: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


# Message schemas
class MessageResponse(BaseModel):
    id: uuid.UUID
    farmer_id: uuid.UUID
    twilio_message_sid: str
    direction: str
    content: Optional[str]
    media_url: Optional[str]
    processed: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# Extraction schemas (for manual testing endpoint)
class ExtractionRequest(BaseModel):
    farmer_id: str
    farmer_name: str
    input_mode: InputMode = InputMode.TEXT
    transcript: str


class ExtractedRecord(BaseModel):
    record_type: RecordType
    farmer: dict
    occurred_at: Optional[str] = None
    source: SourceInfo
    data: dict
    quality: QualityInfo


class ExtractionResponse(BaseModel):
    success: bool
    records: List[ExtractedRecord] = Field(default_factory=list)
    error: Optional[str] = None


# Transcription response
class TranscriptionResponse(BaseModel):
    text: str
    language: Optional[str] = None
    duration: Optional[float] = None


# Pagination
class PaginatedResponse(BaseModel):
    items: List[Any]
    total: int
    page: int
    size: int
    pages: int
