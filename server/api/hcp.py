from typing import Optional

from fastapi import APIRouter

from db import get_session
from models import HCP
from schemas import HCPCreateRequest
from services.hcp_service import create_hcp, search_hcps
from sqlmodel import Session, select

router = APIRouter(prefix="/hcp", tags=["hcp"])


@router.get("")
def list_hcps():
    """Get all HCPs"""
    with get_session() as session:
        hcps = session.exec(select(HCP)).all()
        return hcps


@router.get("/search")
def hcp_search(q: Optional[str] = None, limit: int = 10):
    with get_session() as session:
        return search_hcps(session=session, query=q, limit=limit)


@router.post("")
def create_hcp_endpoint(payload: HCPCreateRequest):
    with get_session() as session:
        return create_hcp(
            session=session,
            name=payload.name,
            specialty=payload.specialty,
            location=payload.location,
        )
