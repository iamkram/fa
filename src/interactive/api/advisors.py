"""Advisor API endpoints for managing FA profiles"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from src.shared.database.connection import db_manager
from src.shared.models.database import Advisor

router = APIRouter(prefix="/api/advisors", tags=["advisors"])

class AdvisorResponse(BaseModel):
    advisor_id: str
    fa_id: str
    name: str
    email: Optional[str]
    firm_name: Optional[str]
    preferences: Optional[dict]

class CreateAdvisorRequest(BaseModel):
    fa_id: str
    name: str
    email: Optional[str] = None
    firm_name: Optional[str] = None
    preferences: Optional[dict] = None

@router.get("/{fa_id}", response_model=AdvisorResponse)
def get_advisor(fa_id: str):
    """Get advisor by FA ID"""
    with db_manager.get_session() as session:
        advisor = session.query(Advisor).filter(Advisor.fa_id == fa_id).first()
        if not advisor:
            raise HTTPException(status_code=404, detail=f"Advisor {fa_id} not found")
        return AdvisorResponse(
            advisor_id=str(advisor.advisor_id),
            fa_id=advisor.fa_id,
            name=advisor.name,
            email=advisor.email,
            firm_name=advisor.firm_name,
            preferences=advisor.preferences or {}
        )

@router.post("/", response_model=AdvisorResponse)
def create_advisor(request: CreateAdvisorRequest):
    """Create new advisor"""
    with db_manager.get_session() as session:
        # Check if advisor already exists
        existing = session.query(Advisor).filter(Advisor.fa_id == request.fa_id).first()
        if existing:
            raise HTTPException(status_code=400, detail=f"Advisor {request.fa_id} already exists")

        advisor = Advisor(
            fa_id=request.fa_id,
            name=request.name,
            email=request.email,
            firm_name=request.firm_name,
            preferences=request.preferences or {"watchlist": []}
        )
        session.add(advisor)
        session.commit()
        session.refresh(advisor)

        return AdvisorResponse(
            advisor_id=str(advisor.advisor_id),
            fa_id=advisor.fa_id,
            name=advisor.name,
            email=advisor.email,
            firm_name=advisor.firm_name,
            preferences=advisor.preferences
        )

@router.put("/{fa_id}/preferences", response_model=AdvisorResponse)
def update_preferences(fa_id: str, preferences: dict):
    """Update advisor preferences (watchlist, etc.)"""
    with db_manager.get_session() as session:
        advisor = session.query(Advisor).filter(Advisor.fa_id == fa_id).first()
        if not advisor:
            raise HTTPException(status_code=404, detail=f"Advisor {fa_id} not found")

        advisor.preferences = preferences
        session.commit()
        session.refresh(advisor)

        return AdvisorResponse(
            advisor_id=str(advisor.advisor_id),
            fa_id=advisor.fa_id,
            name=advisor.name,
            email=advisor.email,
            firm_name=advisor.firm_name,
            preferences=advisor.preferences
        )
