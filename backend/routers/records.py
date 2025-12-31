import uuid
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from db import get_db
from models.models import Record, Farmer, RecordType
from models.schemas import (
    RecordCreate,
    RecordUpdate,
    RecordResponse,
    RecordType as RecordTypeSchema,
)

router = APIRouter(prefix="/api/records", tags=["records"])


@router.get("", response_model=List[RecordResponse])
def list_records(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    farmer_id: Optional[uuid.UUID] = None,
    record_type: Optional[RecordTypeSchema] = None,
    needs_followup: Optional[bool] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    db: Session = Depends(get_db),
):
    """List records with filters."""
    query = db.query(Record)

    if farmer_id:
        query = query.filter(Record.farmer_id == farmer_id)

    if record_type:
        query = query.filter(Record.record_type == record_type.value)

    if needs_followup is not None:
        query = query.filter(Record.needs_followup == needs_followup)

    if date_from:
        query = query.filter(Record.occurred_at >= date_from)

    if date_to:
        query = query.filter(Record.occurred_at <= date_to)

    records = (
        query.order_by(Record.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return records


@router.get("/followup", response_model=List[RecordResponse])
def list_records_needing_followup(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """List records that need follow-up."""
    records = (
        db.query(Record)
        .filter(Record.needs_followup == True)  # noqa: E712
        .order_by(Record.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return records


@router.get("/{record_id}", response_model=RecordResponse)
def get_record(
    record_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    """Get a record by ID."""
    record = db.query(Record).filter(Record.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")
    return record


@router.post("", response_model=RecordResponse, status_code=201)
def create_record(
    record_in: RecordCreate,
    db: Session = Depends(get_db),
):
    """Create a new record manually."""
    # Verify farmer exists
    farmer = db.query(Farmer).filter(Farmer.id == record_in.farmer_id).first()
    if not farmer:
        raise HTTPException(status_code=404, detail="Farmer not found")

    record = Record(
        farmer_id=record_in.farmer_id,
        record_type=RecordType(record_in.record_type.value),
        occurred_at=record_in.occurred_at,
        data=record_in.data,
        source_channel=record_in.source_channel,
        source_input_mode=record_in.source_input_mode,
        source_language=record_in.source_language,
        confidence=record_in.confidence,
        missing_fields=record_in.missing_fields,
        needs_followup=record_in.needs_followup,
        quality_notes=record_in.quality_notes,
        raw_transcript=record_in.raw_transcript,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@router.put("/{record_id}", response_model=RecordResponse)
def update_record(
    record_id: uuid.UUID,
    record_in: RecordUpdate,
    db: Session = Depends(get_db),
):
    """Update a record."""
    record = db.query(Record).filter(Record.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")

    update_data = record_in.model_dump(exclude_unset=True)

    # Handle record_type enum conversion
    if "record_type" in update_data and update_data["record_type"]:
        update_data["record_type"] = RecordType(update_data["record_type"].value)

    for field, value in update_data.items():
        setattr(record, field, value)

    db.commit()
    db.refresh(record)
    return record


@router.delete("/{record_id}", status_code=204)
def delete_record(
    record_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    """Delete a record."""
    record = db.query(Record).filter(Record.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")

    db.delete(record)
    db.commit()
    return None
