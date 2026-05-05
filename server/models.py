from typing import Optional
from sqlmodel import SQLModel, Field


class HCP(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    specialty: Optional[str] = None
    location: Optional[str] = None


class Interaction(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    hcp_id: Optional[int] = Field(default=None, foreign_key="hcp.id")
    interaction_type: Optional[str] = None
    datetime: Optional[str] = None
    attendees: Optional[str] = None
    topics: Optional[str] = None
    materials_shared: Optional[str] = None
    samples_distributed: Optional[str] = None
    sentiment: Optional[str] = None
    outcomes: Optional[str] = None
    follow_up: Optional[str] = None
    notes: Optional[str] = None
