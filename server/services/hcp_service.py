from typing import Optional

from sqlmodel import Session, select

from models import HCP


def get_or_create_hcp_by_name(session: Session, name: str) -> HCP:
    stmt = select(HCP).where(HCP.name == name)
    existing = session.exec(stmt).first()
    if existing:
        return existing

    hcp = HCP(name=name)
    session.add(hcp)
    session.commit()
    session.refresh(hcp)
    return hcp


def search_hcps(session: Session, query: Optional[str], limit: int) -> list[HCP]:
    stmt = select(HCP)
    if query:
        stmt = stmt.where(HCP.name.ilike(f"%{query}%"))
    return session.exec(stmt).all()[:limit]


def create_hcp(session: Session, name: str, specialty: Optional[str], location: Optional[str]) -> HCP:
    hcp = HCP(name=name, specialty=specialty, location=location)
    session.add(hcp)
    session.commit()
    session.refresh(hcp)
    return hcp
