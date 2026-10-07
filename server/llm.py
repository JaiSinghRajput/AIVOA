import json
import os
import re
from datetime import datetime, timedelta
from typing import Any, Dict, TypedDict

from dotenv import load_dotenv
from langgraph.graph import END, START, StateGraph

load_dotenv()

GROQ_MODEL = os.environ.get("GROQ_MODEL", "gemma2-9b-it")
GROQ_FALLBACK_MODEL = "llama-3.1-8b-instant"


def _preprocess_text(text: str) -> str:
    normalized = re.sub(r"(?<=\d);(?=\d)", ":", text)
    for typo in ("tummarow", "tommorow", "tomarrow", "tommorrow"):
        normalized = re.sub(rf"\b{typo}\b", "tomorrow", normalized, flags=re.I)
    return normalized


def _has_time(text: str) -> bool:
    normalized = _preprocess_text(text)
    return bool(re.search(r"\b\d{1,2}(?::\d{2})?\s*(?:am|pm)\b|\b\d{1,2}:\d{2}\b", normalized, re.I))


def _extract_materials(text: str) -> str | None:
    matches: list[str] = []
    for pattern, label in (
        (r"\bbrochures?\b", "brochures"),
        (r"\bflyers?\b", "flyers"),
        (r"\bleaflets?\b", "leaflets"),
        (r"\bbanners?\b", "banners"),
        (r"\bhandouts?\b", "handouts"),
        (r"\bwhitepapers?\b", "whitepapers"),
        (r"\bpamphlets?\b", "pamphlets"),
        (r"\bpresentations?\b", "presentation materials"),
        (r"\bslides?\b", "slides"),
    ):
        if re.search(pattern, text, re.I):
            matches.append(label)

    if matches:
        unique_matches: list[str] = []
        for item in matches:
            if item not in unique_matches:
                unique_matches.append(item)
        return ", ".join(unique_matches)

    return None


def _split_followup_section(text: str) -> tuple[str, str]:
    normalized = _preprocess_text(text)
    match = re.search(r"\b(?:follow[- ]?up|follow up|next steps?)\b", normalized, re.I)
    if not match:
        match = re.search(
            r"\b(?:connect with|call|schedule|reach out to|meet with)\b(?=.*\b(?:today|tomorrow|yesterday|evening|morning|afternoon|\d{1,2}(?::\d{2})?\s*(?:am|pm)))",
            normalized,
            re.I,
        )
    if not match:
        return normalized, ""
    return normalized[: match.start()].strip(), normalized[match.start() :].strip()


def _clean_person_name(name: str) -> str | None:
    stop_words = {
        "also",
        "present",
        "attended",
        "joined",
        "was",
        "were",
        "with",
        "and",
        "he",
        "she",
        "said",
        "connect",
        "tomorrow",
        "today",
        "evening",
        "morning",
        "afternoon",
    }
    parts: list[str] = []
    for token in re.findall(r"[A-Za-z][A-Za-z'-]*", name):
        if token.lower() in stop_words:
            break
        parts.append(token)
        if len(parts) == 3:
            break

    if not parts:
        return None
    return " ".join(part.capitalize() for part in parts)


def _extract_attendees(text: str, hcp_name: str | None = None) -> str | None:
    attendees: list[str] = []
    title_name = r"(?:Mr\.?|Ms\.?|Mrs\.?|Dr\.?)\s+([A-Za-z][A-Za-z'-]*(?:\s+[A-Za-z][A-Za-z'-]*){0,4})"
    patterns = [
        rf"(?:also\s+present|was\s+also\s+present|were\s+also\s+present|also\s+attended|was\s+there)\s+{title_name}",
        rf"{title_name}\s+(?:was\s+also\s+present|was\s+present|were\s+present|attended|joined|also\s+present)",
        rf"\b(?:along with|together with)\s+{title_name}",
    ]

    for pattern in patterns:
        for name in re.findall(pattern, text, re.I):
            cleaned = _clean_person_name(name)
            if cleaned and cleaned not in attendees:
                attendees.append(cleaned)

    if hcp_name:
        hcp_lower = hcp_name.lower()
        attendees = [name for name in attendees if hcp_lower not in name.lower()]

    return ", ".join(attendees) if attendees else None


def _extract_topics(text: str) -> str | None:
    topics: list[str] = []

    discussed = re.search(r"discussed\s+(.+?)(?:\.|\n|$)", text, re.I)
    if discussed:
        raw = discussed.group(1).strip()
        if raw:
            topics.extend([part.strip() for part in re.split(r",| and | then ", raw) if part.strip()])

    about_matches = re.findall(r"(?:about|regarding|concerning)\s+(.+?)(?:\.|\n|,| and |$)", text, re.I)
    for raw in about_matches:
        topics.extend([part.strip() for part in re.split(r",| and ", raw) if part.strip()])

    interest_matches = re.findall(r"(?:interested in|interested with|focus(?:ed)? on|focused on)\s+(.+?)(?:\.|\n|,| and |$)", text, re.I)
    for raw in interest_matches:
        topics.extend([part.strip() for part in re.split(r",| and ", raw) if part.strip()])

    if re.search(r"\bpricing?\b", text, re.I):
        topics.append("pricing")
    if re.search(r"\bcost(s)?\b", text, re.I):
        topics.append("cost")
    if re.search(r"\binsulin delivery\b", text, re.I):
        topics.append("insulin delivery")

    if topics:
        unique_topics: list[str] = []
        for topic in topics:
            if topic and topic.lower() not in [existing.lower() for existing in unique_topics]:
                unique_topics.append(topic)
        return ", ".join(unique_topics)

    return None


def _extract_followup_text(text: str) -> str | None:
    normalized = _preprocess_text(text)
    match = re.search(r"\b(?:follow[- ]?up|follow up|next steps?)\b[:\-]?\s*(.+)$", normalized, re.I)
    if match:
        followup = re.sub(r"\s+(?:and|then)\s*$", "", match.group(1).strip(), flags=re.I)
        return followup if followup else None

    match = re.search(r"\b(?:said to\s+)?((?:connect with|call|schedule|reach out to|meet with)\s+.+)$", normalized, re.I)
    if match and re.search(r"\b(?:today|tomorrow|yesterday|evening|morning|afternoon|\d{1,2}(?::\d{2})?\s*(?:am|pm))\b", match.group(1), re.I):
        followup = re.sub(r"\s+(?:and|then)\s*$", "", match.group(1).strip(), flags=re.I)
        return followup if followup else None
    return None


def _extract_datetime_with_time_hint(text: str) -> str | None:
    parsed = _extract_datetime(text)
    if parsed:
        return parsed
    return None


def _extract_datetime(text: str) -> str | None:
    text = _preprocess_text(text)
    text_lower = text.lower()
    base_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    date_value: datetime | None = None
    if "tomorrow" in text_lower:
        date_value = base_date + timedelta(days=1)
    elif "yesterday" in text_lower:
        date_value = base_date - timedelta(days=1)
    elif "today" in text_lower:
        date_value = base_date

    if date_value is None:
        explicit_date = re.search(
            r"\b((?:\d{4}-\d{2}-\d{2})|(?:\d{1,2}/\d{1,2}/\d{2,4})|(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?\s+\d{1,2}(?:,\s*\d{4})?)\b",
            text,
            re.I,
        )
        if explicit_date:
            try:
                raw_date = explicit_date.group(1).strip()
                if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw_date):
                    date_value = datetime.fromisoformat(raw_date)
                else:
                    date_value = datetime.strptime(raw_date, "%m/%d/%Y")
            except ValueError:
                try:
                    date_value = datetime.strptime(raw_date, "%m/%d/%y")
                except ValueError:
                    date_value = None

    time_match = re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b", text, re.I)
    if not time_match:
        time_match = re.search(r"\b(\d{1,2}):(\d{2})\b", text)

    if date_value is None and time_match is None:
        return None

    if date_value is None:
        date_value = base_date

    hour = 0
    minute = 0
    if time_match:
        hour = int(time_match.group(1))
        minute = int(time_match.group(2) or 0)
        meridiem = time_match.group(3).lower() if time_match.lastindex and time_match.lastindex >= 3 and time_match.group(3) else None
        if meridiem == "pm" and hour != 12:
            hour += 12
        if meridiem == "am" and hour == 12:
            hour = 0
        if meridiem is None and re.search(r"\b(evening|night)\b", text, re.I) and 1 <= hour < 12:
            hour += 12

    combined = date_value.replace(hour=hour, minute=minute, second=0, microsecond=0)
    return combined.isoformat(timespec="minutes")


def _extract_first_datetime(text: str) -> str | None:
    return _extract_datetime(text)


def _extract_interaction_datetime(text: str) -> str | None:
    if not _has_time(text):
        return None
    return _extract_datetime(text)


def _normalize_interaction_type(value: Any) -> str | None:
    if not isinstance(value, str):
        return None

    stripped = value.strip()
    if not stripped:
        return None

    mapping = {
        "meeting": "Meeting",
        "call": "Call",
        "email": "Email",
        "event": "Event",
    }
    return mapping.get(stripped.lower(), stripped)


def _heuristic_extract(text: str) -> Dict[str, Any]:
    text = _preprocess_text(text)
    out: Dict[str, Any] = {}
    if re.search(r"\b(meeting|met|visited|visit)\b", text, re.I):
        out["interaction_type"] = "Meeting"
    elif re.search(r"\b(call|called|phone|dialed)\b", text, re.I):
        out["interaction_type"] = "Call"
    elif re.search(r"\b(email|emailed|mail)\b", text, re.I):
        out["interaction_type"] = "Email"
    elif re.search(r"\b(event|conference|symposium|booth)\b", text, re.I):
        out["interaction_type"] = "Event"

    main_text, followup_text = _split_followup_section(text)

    datetime_value = _extract_interaction_datetime(main_text)
    if datetime_value:
        out["datetime"] = datetime_value

    # Extract main HCP - look for "Met with Dr. X" or first doctor mention
    m = re.search(r"(?:met with|visited|called|meet(?:ed)? with)\s+(Dr\.?\s+)?([A-Z][a-zA-Z'-]+(?:\s+[A-Z][a-zA-Z'-]+)*)", main_text, re.I)
    if m:
        out["hcp_name"] = m.group(2).strip()
    else:
        # Fallback: just look for Dr. pattern
        m = re.search(r"Dr\.?\s+([A-Z][a-zA-Z'-]+(?:\s+[A-Z][a-zA-Z'-]+)*)", main_text)
        if m:
            out["hcp_name"] = m.group(1)

    attendees = _extract_attendees(main_text, out.get("hcp_name"))
    if attendees:
        out["attendees"] = attendees

    # Extract sentiment: check explicit negative cues before positive to avoid "not positive" being tagged positive.
    if re.search(r"\b(not positive|not interested|uninterested|dismissive|negative|didn't|did not|dislike|objection|concern|concerned)\b", text, re.I):
        out["sentiment"] = "negative"
    elif re.search(r"\b(interested|positive|good|liked|likes|love|support|committed|enthusiastic|great)\b", text, re.I):
        out["sentiment"] = "positive"
    else:
        out["sentiment"] = "neutral"

    topics = _extract_topics(main_text)
    if topics:
        out["topics"] = topics

    # Extract materials shared
    materials = _extract_materials(text)
    if materials:
        out["materials_shared"] = materials

    # Extract samples distributed
    s = re.search(r"\b(samples?|starter packs?|kits?)\b(?:\s+(?:distributed|shared|left|given|provided|requested))?", text, re.I)
    if s:
        out["samples_distributed"] = "yes"

    # Extract outcomes - look for commitments, agreements
    o = re.search(r"(?:committed to|agreed to|will|outcome[s]?[:\-]?\s*)([^\.]+)", main_text, re.I)
    if o:
        outcome_text = o.group(1).strip()
        if len(outcome_text) > 5:  # Only if meaningful
            out["outcomes"] = outcome_text

    # Extract follow-up
    followup = _extract_followup_text(followup_text)
    if followup:
        out["follow_up"] = followup

    if followup_text:
        followup_dt = _extract_datetime(followup_text)
        if followup_dt:
            out["follow_up_datetime"] = followup_dt

    out["notes"] = text
    return out

    dt = re.search(
        r"\b(?:on\s+)?((?:\d{4}-\d{2}-\d{2})|(?:\d{1,2}/\d{1,2}/\d{2,4})|(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?\s+\d{1,2}(?:,\s*\d{4})?)\b",
        text,
        re.I,
    )
    if dt:
        out["datetime"] = dt.group(1).strip()

    time = re.search(r"\b(\d{1,2}:\d{2}\s*(?:am|pm)?)\b", text, re.I)
    if time and "datetime" not in out:
        out["datetime"] = time.group(1).strip()

    out["notes"] = text
    return out


def _normalize_output(parsed: Dict[str, Any], text: str) -> Dict[str, Any]:
    normalized: Dict[str, Any] = {}
    text = _preprocess_text(text)
    text_lower = text.lower()
    main_text, followup_text = _split_followup_section(text)

    hcp_name = parsed.get("hcp_name")
    if isinstance(hcp_name, str) and hcp_name.strip():
        normalized["hcp_name"] = hcp_name.strip()

    sentiment = str(parsed.get("sentiment", "neutral")).strip().lower()
    if sentiment not in {"positive", "neutral", "negative"}:
        sentiment = "neutral"
    normalized["sentiment"] = sentiment

    interaction_type = parsed.get("interaction_type")
    normalized_interaction_type = _normalize_interaction_type(interaction_type)
    if normalized_interaction_type:
        normalized["interaction_type"] = normalized_interaction_type

    inferred_main_datetime = _extract_interaction_datetime(main_text)
    datetime_value = parsed.get("datetime")
    if inferred_main_datetime:
        normalized["datetime"] = inferred_main_datetime
    elif isinstance(datetime_value, str) and datetime_value.strip():
        normalized_datetime = _extract_first_datetime(datetime_value)
        followup_datetime = _extract_datetime(followup_text) if followup_text else None
        raw_datetime = datetime_value.strip()
        is_followup_datetime = bool(followup_datetime and normalized_datetime == followup_datetime)

        if normalized_datetime and not is_followup_datetime:
            normalized["datetime"] = normalized_datetime
        elif not is_followup_datetime and not followup_text:
            normalized["datetime"] = datetime_value.strip()

        # If the parsed datetime lost the time component, recover it from the full text.
        if normalized.get("datetime") and re.search(r"T00:00$| 00:00$|^\d{4}-\d{2}-\d{2}$", raw_datetime) and _has_time(main_text):
            inferred_full_datetime = _extract_datetime_with_time_hint(main_text)
            if inferred_full_datetime:
                normalized["datetime"] = inferred_full_datetime
    else:
        inferred_datetime = _extract_interaction_datetime(main_text)
        if inferred_datetime:
            normalized["datetime"] = inferred_datetime

    attendees = parsed.get("attendees")
    if isinstance(attendees, str) and attendees.strip() and not re.search(r"\b(?:said|connect|tomorrow|today|present and|there are|their are)\b", attendees, re.I):
        normalized["attendees"] = attendees.strip()
    else:
        extracted_attendees = _extract_attendees(text, normalized.get("hcp_name"))
        if extracted_attendees:
            normalized["attendees"] = extracted_attendees

    topics = parsed.get("topics")
    if isinstance(topics, str) and topics.strip():
        normalized["topics"] = topics.strip()
    else:
        extracted_topics = _extract_topics(text)
        if extracted_topics:
            normalized["topics"] = extracted_topics

    materials = parsed.get("materials_shared")
    if isinstance(materials, str) and materials.strip():
        normalized["materials_shared"] = materials.strip().lower()

    extracted_materials = _extract_materials(text)
    if extracted_materials:
        normalized["materials_shared"] = extracted_materials
    elif re.search(r"\b(brochure|flyer|leaflet|whitepaper|pamphlet|presentation|slides?|materials?)\b", text_lower):
        normalized["materials_shared"] = "yes"

    samples_distributed = parsed.get("samples_distributed")
    if isinstance(samples_distributed, str) and samples_distributed.strip():
        normalized["samples_distributed"] = samples_distributed.strip()

    if re.search(r"\b(samples?|starter packs?|kits?)\b", text_lower):
        normalized["samples_distributed"] = "yes"

    outcomes = parsed.get("outcomes")
    if isinstance(outcomes, str) and outcomes.strip():
        normalized["outcomes"] = outcomes.strip()
    else:
        if re.search(r"\b(committed to|agreed to|will)\b", text, re.I):
            outcome_text = re.search(r"(?:committed to|agreed to|will)\s+([^\.]+)", text, re.I)
            if outcome_text:
                normalized["outcomes"] = outcome_text.group(1).strip()

    follow_up = parsed.get("follow_up")
    if isinstance(follow_up, str) and follow_up.strip():
        normalized["follow_up"] = follow_up.strip()
    else:
        extracted_follow_up = _extract_followup_text(followup_text)
        if extracted_follow_up:
            normalized["follow_up"] = extracted_follow_up
        else:
            extracted_follow_up = _extract_followup_text(text)
            if extracted_follow_up:
                normalized["follow_up"] = extracted_follow_up

    notes = parsed.get("notes")
    normalized["notes"] = notes.strip() if isinstance(notes, str) and notes.strip() else text

    return normalized


def _extract_with_groq(text: str) -> Dict[str, Any]:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is not set")

    from groq import Groq

    client = Groq(api_key=api_key)
    prompt = (
        "Extract the fields from this HCP interaction note and return ONLY a JSON object with keys: "
        "hcp_name, interaction_type, datetime, attendees, sentiment (positive/neutral/negative), topics, materials_shared, samples_distributed, outcomes, follow_up, notes. "
        "For attendees, return only person names. For materials_shared, return the material names such as brochures, not yes/no. "
        "For samples_distributed, return yes or no. Put planned next contact in follow_up, not datetime.\n\n"
        f"Text:\n{text}"
    )
    content = ""
    last_error: Exception | None = None
    for model in (GROQ_MODEL, GROQ_FALLBACK_MODEL):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You extract structured fields from HCP interaction notes and return only valid JSON."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0,
                response_format={"type": "json_object"},
            )
            content = (response.choices[0].message.content or "").strip()
            break
        except Exception as exc:
            last_error = exc
            content = ""
    if not content:
        if last_error is not None:
            raise last_error
        raise ValueError("No JSON object returned by model")
    match = re.search(r"\{.*\}", content, re.S)
    if not match:
        raise ValueError("No JSON object returned by model")
    parsed = json.loads(match.group(0))
    if not isinstance(parsed, dict):
        raise ValueError("Model output was not a JSON object")
    return _normalize_output(parsed, text)


class ExtractionState(TypedDict):
    text: str
    result: Dict[str, Any]


def _extract_node(state: ExtractionState) -> ExtractionState:
    text = state.get("text", "")
    try:
        result = _extract_with_groq(text)
    except Exception:
        result = _heuristic_extract(text)
    return {"text": text, "result": result}


_builder = StateGraph(ExtractionState)
_builder.add_node("extract", _extract_node)
_builder.add_edge(START, "extract")
_builder.add_edge("extract", END)
_graph = _builder.compile()


def extract_entities(text: str) -> Dict[str, Any]:
    """Entity extraction pipeline orchestrated by LangGraph."""
    state = _graph.invoke({"text": text or "", "result": {}})
    result = state.get("result")
    if isinstance(result, dict) and result:
        return result
    return _heuristic_extract(text or "")
