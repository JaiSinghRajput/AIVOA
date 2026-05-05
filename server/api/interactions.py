from typing import Optional

from fastapi import APIRouter

from db import get_session
from schemas import InteractionUpdateRequest
from services.interaction_service import (
    build_followup_recommendations,
    build_interaction_summary,
    get_interaction_or_404,
    list_interactions,
    update_interaction,
)

router = APIRouter(prefix="/interactions", tags=["interactions"])


@router.get("/{interaction_id}")
def get_interaction(interaction_id: int):
    with get_session() as session:
        return get_interaction_or_404(session=session, interaction_id=interaction_id)


@router.put("/{interaction_id}")
def edit_interaction(interaction_id: int, payload: InteractionUpdateRequest):
    with get_session() as session:
        updates = payload.model_dump(exclude_none=True)
        return update_interaction(session=session, interaction_id=interaction_id, payload=updates)


@router.get("")
def list_interactions_endpoint(hcp_id: Optional[int] = None, limit: int = 50):
    with get_session() as session:
        return list_interactions(session=session, hcp_id=hcp_id, limit=limit)


@router.get("/{interaction_id}/summary")
def interaction_summary(interaction_id: int) -> dict[str, object]:
    with get_session() as session:
        interaction = get_interaction_or_404(session=session, interaction_id=interaction_id)
        return {
            "summary": build_interaction_summary(interaction),
            "interaction": interaction
        }


@router.get("/{interaction_id}/followups")
def followup_recommendations(interaction_id: int) -> dict[str, object]:
    with get_session() as session:
        interaction = get_interaction_or_404(session=session, interaction_id=interaction_id)
        return {
            "recommendations": build_followup_recommendations(interaction),
            "interaction": interaction
        }
