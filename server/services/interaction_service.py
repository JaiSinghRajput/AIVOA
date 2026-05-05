from fastapi import HTTPException
from sqlmodel import Session, select
from datetime import datetime
import re

from llm import extract_entities
from models import Interaction
from services.hcp_service import get_or_create_hcp_by_name


def create_interaction_from_text(
    session: Session,
    text: str,
    hcp_id: int | None,
    parsed: dict[str, object] | None = None,
) -> Interaction:
    parsed = parsed or extract_entities(text)

    resolved_hcp_id = hcp_id
    parsed_hcp_name = parsed.get("hcp_name")
    if not resolved_hcp_id and isinstance(parsed_hcp_name, str) and parsed_hcp_name.strip():
        hcp = get_or_create_hcp_by_name(session, parsed_hcp_name.strip())
        resolved_hcp_id = hcp.id

    interaction = Interaction(
        hcp_id=resolved_hcp_id,
        interaction_type=parsed.get("interaction_type"),
        datetime=parsed.get("datetime"),
        attendees=parsed.get("attendees"),
        topics=parsed.get("topics"),
        materials_shared=parsed.get("materials_shared"),
        samples_distributed=parsed.get("samples_distributed"),
        sentiment=parsed.get("sentiment"),
        outcomes=parsed.get("outcomes"),
        follow_up=parsed.get("follow_up"),
        notes=parsed.get("notes") or text,
    )
    session.add(interaction)
    session.commit()
    session.refresh(interaction)
    return interaction


def get_interaction_or_404(session: Session, interaction_id: int) -> Interaction:
    interaction = session.get(Interaction, interaction_id)
    if not interaction:
        raise HTTPException(status_code=404, detail="Interaction not found")
    return interaction


def update_interaction(session: Session, interaction_id: int, payload: dict[str, object]) -> Interaction:
    interaction = get_interaction_or_404(session, interaction_id)
    for key, value in payload.items():
        if hasattr(interaction, key):
            setattr(interaction, key, value)

    session.add(interaction)
    session.commit()
    session.refresh(interaction)
    return interaction


def list_interactions(session: Session, hcp_id: int | None, limit: int) -> list[Interaction]:
    stmt = select(Interaction)
    if hcp_id:
        stmt = stmt.where(Interaction.hcp_id == hcp_id)
    return session.exec(stmt).all()[:limit]


def find_interactions_by_followup_date(
    session: Session, 
    query_text: str, 
    hcp_id: int | None = None,
    limit: int = 10
) -> list[Interaction]:
    """Find interactions with followups matching a date mentioned in the query."""
    # Extract target date from query (e.g., "tomorrow", "next week", "2026-05-06")
    query_lower = query_text.lower()
    
    # Get all interactions with followups
    stmt = select(Interaction).where(Interaction.follow_up != None)
    if hcp_id:
        stmt = stmt.where(Interaction.hcp_id == hcp_id)
    
    interactions = session.exec(stmt).all()
    
    if not interactions:
        return []
    
    # Filter by date mentioned in query
    matches: list[tuple[Interaction, int]] = []
    
    for interaction in interactions:
        if not interaction.follow_up:
            continue
            
        followup_lower = interaction.follow_up.lower()
        score = 0
        
        # Check if query mentions match followup text
        if "tomorrow" in query_lower and "tomorrow" in followup_lower:
            score = 100
        elif "today" in query_lower and "today" in followup_lower:
            score = 100
        elif "next week" in query_lower and ("next week" in followup_lower or "week" in followup_lower):
            score = 80
        elif "next month" in query_lower and ("next month" in followup_lower or "month" in followup_lower):
            score = 80
        elif any(day in query_lower for day in ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]):
            # Match day of week
            for day in ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]:
                if day in query_lower and day in followup_lower:
                    score = 90
                    break
        
        # General score for any date match
        if score == 0 and any(word in followup_lower for word in ["tomorrow", "today", "week", "month", "am", "pm"]):
            score = 10
        
        if score > 0:
            matches.append((interaction, score))
    
    # Sort by score (highest first) and return top matches
    matches.sort(key=lambda x: x[1], reverse=True)
    return [m[0] for m in matches[:limit]]


def build_interaction_summary(interaction: Interaction) -> str:
    """Build a comprehensive summary of an interaction."""
    parts: list[str] = []
    
    # Core details
    if interaction.interaction_type:
        parts.append(f"Type: {interaction.interaction_type}")
    if interaction.datetime:
        parts.append(f"Date: {interaction.datetime}")
    
    # Main content
    if interaction.notes:
        parts.append(f"Notes: {interaction.notes}")
    
    # Discussion details
    if interaction.topics:
        parts.append(f"Topics: {interaction.topics}")
    if interaction.attendees:
        parts.append(f"Attendees: {interaction.attendees}")
    
    # Materials and sentiment
    if interaction.materials_shared:
        parts.append(f"Materials Shared: {interaction.materials_shared}")
    if interaction.samples_distributed:
        parts.append(f"Samples: {interaction.samples_distributed}")
    if interaction.sentiment:
        parts.append(f"Sentiment: {interaction.sentiment.upper()}")
    
    # Outcomes and follow-ups
    if interaction.outcomes:
        parts.append(f"Outcomes: {interaction.outcomes}")
    if interaction.follow_up:
        parts.append(f"Follow-up: {interaction.follow_up}")
    
    return " | ".join(parts)


def build_followup_recommendations(interaction: Interaction) -> list[str]:
    """Generate intelligent, context-aware follow-up recommendations."""
    recommendations: list[str] = []
    
    # Sentiment-based primary action
    if interaction.sentiment == "positive":
        recommendations.append("🎯 Strong Interest: Send detailed pricing, ROI data, and clinical evidence.")
        recommendations.append("📅 Schedule a follow-up meeting to discuss implementation timeline.")
        if interaction.topics and "sample" in interaction.topics.lower():
            recommendations.append("📦 Prepare additional samples or starter packs for next meeting.")
        recommendations.append("💼 Propose pilot program or volume discount for commitment.")
    elif interaction.sentiment == "negative":
        recommendations.append("⚠️ Address Concerns: Prepare responses to objections raised.")
        recommendations.append("💡 Compile competitive analysis and cost-benefit comparison.")
        recommendations.append("🤝 Consider escalation to senior stakeholder or offering alternatives.")
        recommendations.append("📧 Follow up with personalized proposal addressing specific concerns.")
    else:  # neutral
        recommendations.append("🔄 Continue Engagement: Provide additional information and resources.")
        recommendations.append("📋 Share case studies and success stories from similar institutions.")
        recommendations.append("⏰ Plan follow-up in 1-2 weeks to maintain momentum.")
        recommendations.append("🎁 Send introductory materials and offer a product demonstration.")
    
    # Topic-specific follow-ups
    if interaction.topics:
        topics_lower = interaction.topics.lower()
        if "price" in topics_lower or "cost" in topics_lower:
            recommendations.append("💰 Prepare flexible pricing options and volume discounts.")
        if "sample" in topics_lower or "trial" in topics_lower:
            recommendations.append("🧪 Track sample usage and request feedback on efficacy.")
        if "competitor" in topics_lower:
            recommendations.append("📊 Compile competitive differentiation and unique value proposition.")
        recommendations.append(f"✅ Follow up specifically on: {interaction.topics[:50]}...")
    
    # Materials-based follow-ups
    if interaction.materials_shared:
        recommendations.append("📮 Send promised materials and track delivery confirmation.")
    
    # Generic next step
    if not interaction.outcomes:
        recommendations.append("📞 Confirm next meeting date/time before closing conversation.")
    elif "demo" in interaction.outcomes.lower():
        recommendations.append("🎬 Schedule product demonstration within 3-5 business days.")
    elif "proposal" in interaction.outcomes.lower():
        recommendations.append("📄 Send formal proposal and allow 1 week for review and feedback.")
    
    # Remove duplicates while preserving order
    seen = set()
    unique_recommendations = []
    for rec in recommendations:
        if rec not in seen:
            seen.add(rec)
            unique_recommendations.append(rec)
    
    return unique_recommendations[:8]  # Return top 8 recommendations
