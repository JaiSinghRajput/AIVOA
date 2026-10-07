from fastapi import HTTPException
from sqlmodel import Session, select
from datetime import datetime, timedelta
import re
import os
from dotenv import load_dotenv

from llm import extract_entities
from models import Interaction
from services.hcp_service import get_or_create_hcp_by_name

load_dotenv()


def create_interaction_from_text(
    session: Session,
    text: str,
    hcp_id: int | None,
    parsed: dict[str, object] | None = None,
) -> Interaction:
    parsed = parsed or extract_entities(text)
    parsed_datetime = parsed.get("datetime")
    if not isinstance(parsed_datetime, str) or not parsed_datetime.strip():
        # For new entries with no date/time context in text, use current timestamp.
        parsed["datetime"] = datetime.now().isoformat(timespec="minutes")

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


def _clean_date_text(text: str) -> str:
    cleaned = re.sub(r"(?<=\d);(?=\d)", ":", text or "")
    for typo in ("tummarow", "tummarrow", "tommorow", "tomarrow", "tommorrow"):
        cleaned = re.sub(rf"\b{typo}\b", "tomorrow", cleaned, flags=re.I)
    return cleaned


def _parse_relative_datetime(text: str) -> datetime | None:
    cleaned = _clean_date_text(text)
    lower = cleaned.lower()
    base = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    date_value: datetime | None = None
    if "tomorrow" in lower:
        date_value = base + timedelta(days=1)
    elif "today" in lower:
        date_value = base
    elif "yesterday" in lower:
        date_value = base - timedelta(days=1)
    else:
        iso_date = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", cleaned)
        if iso_date:
            try:
                date_value = datetime.fromisoformat(iso_date.group(1))
            except ValueError:
                date_value = None

    if date_value is None:
        return None

    hour = 0
    minute = 0
    time_match = re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b", cleaned, re.I)
    if not time_match:
        time_match = re.search(r"\b(\d{1,2}):(\d{2})\b", cleaned)

    if time_match:
        hour = int(time_match.group(1))
        minute = int(time_match.group(2) or 0)
        meridiem = time_match.group(3).lower() if time_match.lastindex and time_match.lastindex >= 3 and time_match.group(3) else None
        if meridiem == "pm" and hour != 12:
            hour += 12
        if meridiem == "am" and hour == 12:
            hour = 0
        if meridiem is None and re.search(r"\b(evening|night)\b", cleaned, re.I) and 1 <= hour < 12:
            hour += 12

    return date_value.replace(hour=hour, minute=minute)


def _query_date_window(query_text: str) -> tuple[datetime, datetime] | None:
    lower = _clean_date_text(query_text).lower()
    base = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    if "tomorrow" in lower:
        start = base + timedelta(days=1)
        return start, start + timedelta(days=1)
    if "today" in lower:
        return base, base + timedelta(days=1)
    if "this week" in lower:
        return base, base + timedelta(days=7)
    if "next week" in lower:
        start = base + timedelta(days=7)
        return start, start + timedelta(days=7)
    if "next month" in lower:
        start = base + timedelta(days=30)
        return start, start + timedelta(days=30)

    explicit = _parse_relative_datetime(lower)
    if explicit:
        start = explicit.replace(hour=0, minute=0)
        return start, start + timedelta(days=1)

    return None


def find_interactions_by_followup_date(
    session: Session, 
    query_text: str, 
    hcp_id: int | None = None,
    limit: int = 10
) -> list[Interaction]:
    """Find interactions with followups matching a date mentioned in the query."""
    query_lower = _clean_date_text(query_text).lower()
    window = _query_date_window(query_text)
    
    # Get all interactions with followups
    stmt = select(Interaction).where(Interaction.follow_up != None)
    if hcp_id:
        stmt = stmt.where(Interaction.hcp_id == hcp_id)
    
    interactions = session.exec(stmt).all()
    
    if not interactions:
        return []
    
    matches: list[tuple[Interaction, int, datetime]] = []
    
    for interaction in interactions:
        if not interaction.follow_up:
            continue
            
        followup_lower = _clean_date_text(interaction.follow_up).lower()
        followup_dt = _parse_relative_datetime(interaction.follow_up) or datetime.max.replace(microsecond=0)
        score = 0

        if window and followup_dt != datetime.max.replace(microsecond=0):
            start, end = window
            if start <= followup_dt < end:
                score = 200
        
        # Check if query mentions match followup text
        if score == 0 and "tomorrow" in query_lower and "tomorrow" in followup_lower:
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
            matches.append((interaction, score, followup_dt))
    
    # Sort by strongest date match first, then nearest scheduled time.
    matches.sort(key=lambda x: (-x[1], x[2], x[0].id or 0))
    return [m[0] for m in matches[:limit]]


def build_interaction_summary(interaction: Interaction) -> str:
    """Build a concise, non-duplicative summary using the LLM API with safe fallback."""
    api_key = os.environ.get("GROQ_API_KEY")
    if api_key:
        try:
            from groq import Groq

            client = Groq(api_key=api_key)
            model = os.environ.get("GROQ_MODEL", "gemma2-9b-it")
            fallback_model = "llama-3.1-8b-instant"
            compact_payload = {
                "interaction_type": interaction.interaction_type,
                "datetime": interaction.datetime,
                "attendees": interaction.attendees,
                "topics": interaction.topics,
                "materials_shared": interaction.materials_shared,
                "samples_distributed": interaction.samples_distributed,
                "sentiment": interaction.sentiment,
                "outcomes": interaction.outcomes,
                "follow_up": interaction.follow_up,
                "notes": interaction.notes,
            }
            prompt = (
                "Create a concise meeting summary from CRM data. "
                "Do not copy raw notes verbatim, do not repeat duplicate statements, and do not list field labels. "
                "Write 3-5 short sentences covering: discussion focus, HCP response/sentiment, outcomes, and next follow-up action.\n\n"
                f"Data:\n{compact_payload}"
            )
            for candidate_model in (model, fallback_model):
                try:
                    response = client.chat.completions.create(
                        model=candidate_model,
                        messages=[
                            {"role": "system", "content": "You are a medical CRM assistant that writes concise professional summaries."},
                            {"role": "user", "content": prompt},
                        ],
                        temperature=0.2,
                    )
                    content = (response.choices[0].message.content or "").strip()
                    if content:
                        return content
                except Exception:
                    continue
        except Exception:
            pass

    # Fallback summary if LLM is unavailable.
    parts: list[str] = []
    if interaction.interaction_type:
        parts.append(f"{interaction.interaction_type} interaction")
    if interaction.topics:
        parts.append(f"focused on {interaction.topics}")
    if interaction.sentiment:
        parts.append(f"with {interaction.sentiment} sentiment")
    if interaction.outcomes:
        parts.append(f"Outcome: {interaction.outcomes}.")
    if interaction.follow_up:
        parts.append(f"Next action: {interaction.follow_up}.")
    if not parts and interaction.notes:
        short_notes = re.sub(r"\s+", " ", interaction.notes).strip()
        return short_notes[:240] + ("..." if len(short_notes) > 240 else "")
    return " ".join(parts).strip() or "No summary available."


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
