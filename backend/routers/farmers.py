import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from db import get_db
from models.models import Farmer
from models.schemas import (
    FarmerCreate,
    FarmerUpdate,
    FarmerResponse,
    FarmerWithRecords,
)

router = APIRouter(prefix="/api/farmers", tags=["farmers"])


@router.get("", response_model=List[FarmerResponse])
def list_farmers(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    search: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """List all farmers with optional search."""
    query = db.query(Farmer)

    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            (Farmer.name.ilike(search_pattern))
            | (Farmer.external_id.ilike(search_pattern))
        )

    farmers = query.offset(skip).limit(limit).all()
    return farmers


@router.get("/{farmer_id}", response_model=FarmerWithRecords)
def get_farmer(
    farmer_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    """Get a farmer by ID with their records."""
    farmer = db.query(Farmer).filter(Farmer.id == farmer_id).first()
    if not farmer:
        raise HTTPException(status_code=404, detail="Farmer not found")
    return farmer


@router.get("/external/{external_id}", response_model=FarmerResponse)
def get_farmer_by_external_id(
    external_id: str,
    db: Session = Depends(get_db),
):
    """Get a farmer by external ID (e.g., phone number)."""
    farmer = db.query(Farmer).filter(Farmer.external_id == external_id).first()
    if not farmer:
        raise HTTPException(status_code=404, detail="Farmer not found")
    return farmer


@router.post("", response_model=FarmerResponse, status_code=201)
def create_farmer(
    farmer_in: FarmerCreate,
    db: Session = Depends(get_db),
):
    """Create a new farmer."""
    # Check if external_id already exists
    existing = db.query(Farmer).filter(
        Farmer.external_id == farmer_in.external_id
    ).first()
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Farmer with external_id '{farmer_in.external_id}' already exists",
        )

    farmer = Farmer(**farmer_in.model_dump())
    db.add(farmer)
    db.commit()
    db.refresh(farmer)
    return farmer


@router.put("/{farmer_id}", response_model=FarmerResponse)
def update_farmer(
    farmer_id: uuid.UUID,
    farmer_in: FarmerUpdate,
    db: Session = Depends(get_db),
):
    """Update a farmer."""
    farmer = db.query(Farmer).filter(Farmer.id == farmer_id).first()
    if not farmer:
        raise HTTPException(status_code=404, detail="Farmer not found")

    update_data = farmer_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(farmer, field, value)

    db.commit()
    db.refresh(farmer)
    return farmer


@router.delete("/{farmer_id}", status_code=204)
def delete_farmer(
    farmer_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    """Delete a farmer and all their records."""
    farmer = db.query(Farmer).filter(Farmer.id == farmer_id).first()
    if not farmer:
        raise HTTPException(status_code=404, detail="Farmer not found")

    db.delete(farmer)
    db.commit()
    return None


def get_or_create_farmer(
    db: Session,
    external_id: str,
    name: str,
    phone_number: Optional[str] = None,
) -> Farmer:
    """Get existing farmer or create new one."""
    farmer = db.query(Farmer).filter(Farmer.external_id == external_id).first()

    if not farmer:
        farmer = Farmer(
            external_id=external_id,
            name=name,
            phone_number=phone_number,
        )
        db.add(farmer)
        db.commit()
        db.refresh(farmer)

    return farmer
