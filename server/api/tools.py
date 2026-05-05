from fastapi import APIRouter, HTTPException

from db import get_session
from schemas import AssistantRequest, LogRequest
from services.interaction_service import (
    create_interaction_from_text,
    build_interaction_summary,
    build_followup_recommendations,
)
from services.assistant_service import run_assistant_request
from llm import extract_entities

router = APIRouter(prefix="/tools", tags=["tools"])


@router.post("/log")
def log_interaction(req: LogRequest) -> dict[str, object]:
    """Log an interaction from raw chat text with AI-powered extraction and insights."""
    if not req.text and not req.hcp_id:
        raise HTTPException(status_code=400, detail="Provide text or hcp_id")

    with get_session() as session:
        extracted = extract_entities(req.text or "")
        interaction = create_interaction_from_text(
            session=session,
            text=req.text or "",
            hcp_id=req.hcp_id,
            parsed=extracted,
        )
        
        # Return interaction with extracted fields and initial insights
        return {
            "interaction": interaction,
            "extracted": extracted,
            "summary": build_interaction_summary(interaction),
            "recommendations": build_followup_recommendations(interaction),
        }


@router.post("/chat")
def chat_assistant(req: AssistantRequest) -> dict[str, object]:
    if not req.text and not req.hcp_id and req.interaction_id is None:
        raise HTTPException(status_code=400, detail="Provide text, hcp_id, or interaction_id")

    with get_session() as session:
        return run_assistant_request(
            session=session,
            text=req.text or "",
            hcp_id=req.hcp_id,
            interaction_id=req.interaction_id,
        )
