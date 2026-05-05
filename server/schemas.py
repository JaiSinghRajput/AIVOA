from typing import Optional

from pydantic import BaseModel


class LogRequest(BaseModel):
    text: Optional[str] = None
    hcp_id: Optional[int] = None


class AssistantRequest(BaseModel):
    text: Optional[str] = None
    hcp_id: Optional[int] = None
    interaction_id: Optional[int] = None


class InteractionUpdateRequest(BaseModel):
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


class HCPCreateRequest(BaseModel):
    name: str
    specialty: Optional[str] = None
    location: Optional[str] = None
