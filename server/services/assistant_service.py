from __future__ import annotations

import json
import os
import re
from typing import Any, Literal, TypedDict

from dotenv import load_dotenv
from langgraph.graph import END, START, StateGraph
from sqlmodel import Session, select

from llm import extract_entities
from models import Interaction
from services.hcp_service import get_or_create_hcp_by_name, search_hcps
from services.interaction_service import (
    build_followup_recommendations,
    build_interaction_summary,
    create_interaction_from_text,
    find_interactions_by_followup_date,
    get_interaction_or_404,
    list_interactions,
    update_interaction,
)

load_dotenv()

GROQ_MODEL = os.environ.get("GROQ_MODEL", "gemma2-9b-it")
GROQ_FALLBACK_MODEL = "llama-3.1-8b-instant"

Intent = Literal["log", "summary", "followup", "search", "update", "generic"]


class AssistantState(TypedDict, total=False):
    text: str
    hcp_id: int | None
    interaction_id: int | None
    intent: str
    query: str
    request_text: str
    assistant_message: str
    summary: str
    recommendations: list[str]
    search_results: list[Any]
    interaction: Any
    extracted: dict[str, Any]


def _classify_with_groq(text: str) -> dict[str, str]:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is not set")

    from groq import Groq

    client = Groq(api_key=api_key)
    prompt = (
        "Classify the user's request into one of these intents: log, summary, followup, search, update, generic. "
        "Return ONLY a JSON object with keys: intent, query, reason. "
        "Use followup for upcoming follow-up questions, summary for recap/overview requests, search for HCP lookups, "
        "update for edits or corrections, and log for new interaction notes to record.\n\n"
        f"Text:\n{text}"
    )

    content = ""
    last_error: Exception | None = None
    for model in (GROQ_MODEL, GROQ_FALLBACK_MODEL):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You classify CRM chat requests and return only valid JSON."},
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

    parsed = json.loads(content)
    if not isinstance(parsed, dict):
        raise ValueError("Model output was not a JSON object")

    intent = str(parsed.get("intent", "generic")).strip().lower()
    if intent not in {"log", "summary", "followup", "search", "update", "generic"}:
        intent = "generic"

    query = str(parsed.get("query", "")).strip()
    return {"intent": intent, "query": query}


def _heuristic_classify(text: str) -> dict[str, str]:
    normalized = text.lower().strip()
    intent: Intent = "log"
    query = text.strip()

    if re.search(r"\b(summary|overview|recap)\b", normalized):
        intent = "summary"
    elif re.search(r"\b(follow|follow-up|follow up|next steps?|action(s)?|upcoming)\b", normalized):
        intent = "followup"
    elif re.search(r"\b(search|find|look up|lookup|locate)\b", normalized):
        intent = "search"
    elif re.search(r"\b(update|edit|change|modify|correct|fix)\b", normalized):
        intent = "update"
    elif re.search(r"\b(log|record|capture|save)\b", normalized):
        intent = "log"

    query_match = re.search(r"(?:search|find|look up|lookup|locate)\s+(.*)$", text, re.I)
    if query_match:
      query = query_match.group(1).strip()

    if intent == "summary" and not query_match:
        query = ""

    return {"intent": intent, "query": query}


def _classify_request(text: str) -> dict[str, str]:
    return _classify_with_groq(text)


def _latest_interaction(session: Session, hcp_id: int | None) -> Interaction | None:
    stmt = select(Interaction).order_by(Interaction.id.desc())
    if hcp_id is not None:
        stmt = stmt.where(Interaction.hcp_id == hcp_id)
    return session.exec(stmt).first()


def _resolve_target_interaction(
    session: Session,
    interaction_id: int | None,
    hcp_id: int | None,
) -> Interaction | None:
    if interaction_id is not None:
        try:
            return get_interaction_or_404(session, interaction_id)
        except Exception:
            return None
    return _latest_interaction(session, hcp_id)


def _build_message(intent: str, **context: Any) -> str:
    if intent == "log":
        hcp_name = context.get("hcp_name") or "the selected HCP"
        interaction_type = context.get("interaction_type") or "interaction"
        return f"Logged a {interaction_type.lower()} for {hcp_name}."

    if intent == "summary":
        target = context.get("target")
        if target is None:
            return "I could not find an interaction to summarize."
        hcp_part = f" for {target.hcp_id}" if target.hcp_id else ""
        return f"Here is the summary{hcp_part}."

    if intent == "followup":
        target = context.get("target")
        recommendations = context.get("recommendations") or []
        if target is None:
            return "I could not find an interaction to suggest follow-ups for."
        if recommendations:
            return f"I found {len(recommendations)} follow-up suggestion(s) for the latest interaction."
        return "I could not find any follow-up suggestions for that interaction."

    if intent == "search":
        results = context.get("search_results") or []
        query = context.get("query") or "the request"
        if results:
            return f"Found {len(results)} HCP match(es) for '{query}'."
        return f"No HCPs matched '{query}'."

    if intent == "update":
        target = context.get("target")
        if target is None:
            return "I could not find an interaction to update."
        # Build a more informative message about what was updated
        updates = []
        if target.attendees:
            updates.append(f"attendees: {target.attendees}")
        if target.topics:
            updates.append(f"topics: {target.topics}")
        if target.outcomes:
            updates.append(f"outcomes: {target.outcomes}")
        if target.follow_up:
            updates.append(f"follow-up: {target.follow_up}")
        
        if updates:
            return f"Updated interaction with: {', '.join(updates)}."
        return f"Updated interaction #{target.id}."

    return "I can log a new interaction, search HCPs, summarize the latest note, or suggest follow-ups."


def _build_graph(session: Session):
    def classify_node(state: AssistantState) -> AssistantState:
        text = state.get("text", "")
        interaction_id = state.get("interaction_id")
        
        classification = _classify_request(text)
        intent = classification.get("intent", "generic")
        
        # If an interaction is already selected and this isn't a query intent,
        # treat it as an update instead of a new log
        if interaction_id is not None and intent in ("log", "generic"):
            intent = "update"
        
        return {
            **state,
            "intent": intent,
            "query": classification.get("query", ""),
            "request_text": text
        }

    def log_node(state: AssistantState) -> AssistantState:
        text = state.get("text", "")
        interaction_id = state.get("interaction_id")
        parsed = extract_entities(text)
        resolved_hcp_id = state.get("hcp_id")

        parsed_hcp_name = parsed.get("hcp_name")
        if not resolved_hcp_id and isinstance(parsed_hcp_name, str) and parsed_hcp_name.strip():
            hcp = get_or_create_hcp_by_name(session, parsed_hcp_name.strip())
            resolved_hcp_id = hcp.id

        # Check if we're continuing an existing interaction
        if interaction_id is not None:
            try:
                interaction = get_interaction_or_404(session, interaction_id)
                # Append the new text to the existing notes
                existing_notes = interaction.notes or ""
                interaction.notes = f"{existing_notes}\n\n{text}" if existing_notes else text
                session.add(interaction)
                session.commit()
                session.refresh(interaction)
            except Exception:
                # If interaction not found, create a new one
                interaction = create_interaction_from_text(
                    session=session,
                    text=text,
                    hcp_id=resolved_hcp_id,
                    parsed=parsed,
                )
        else:
            # Create a new interaction
            interaction = create_interaction_from_text(
                session=session,
                text=text,
                hcp_id=resolved_hcp_id,
                parsed=parsed,
            )

        return {
            **state,
            "intent": "log",
            "interaction": interaction,
            "extracted": parsed,
            "assistant_message": _build_message(
                "log",
                hcp_name=parsed.get("hcp_name") or (f"HCP #{interaction.hcp_id}" if interaction.hcp_id else None),
                interaction_type=interaction.interaction_type,
            ),
        }

    def summary_node(state: AssistantState) -> AssistantState:
        target = _resolve_target_interaction(session, state.get("interaction_id"), state.get("hcp_id"))
        if target is None:
            return {**state, "intent": "summary", "assistant_message": "I could not find an interaction to summarize."}

        return {
            **state,
            "intent": "summary",
            "interaction": target,
            "summary": build_interaction_summary(target),
            "assistant_message": _build_message("summary", target=target),
        }

    def followup_node(state: AssistantState) -> AssistantState:
        query = state.get("text", "")
        hcp_id = state.get("hcp_id")
        
        # Find interactions with followups matching the query date
        followup_interactions = find_interactions_by_followup_date(session, query, hcp_id, limit=10)
        
        if not followup_interactions:
            return {**state, "intent": "followup", "assistant_message": "I could not find any scheduled followups matching your query."}
        
        # Use the first matching interaction
        target = followup_interactions[0]
        
        # Build message showing the followup details
        followup_text = target.follow_up or ""
        return {
            **state,
            "intent": "followup",
            "interaction": target,
            "recommendations": [followup_text] if followup_text else [],
            "assistant_message": f"Found followup scheduled: {followup_text}" if followup_text else "Loaded followup interaction.",
        }

    def search_node(state: AssistantState) -> AssistantState:
        query = state.get("query") or state.get("text", "")
        results = search_hcps(session=session, query=query, limit=5)
        return {
            **state,
            "intent": "search",
            "search_results": results,
            "assistant_message": _build_message("search", search_results=results, query=query),
        }

    def update_node(state: AssistantState) -> AssistantState:
        target = _resolve_target_interaction(session, state.get("interaction_id"), state.get("hcp_id"))
        if target is None:
            return {**state, "intent": "update", "assistant_message": "I could not find an interaction to update."}

        parsed = extract_entities(state.get("text", ""))
        updates: dict[str, Any] = {}
        
        for key in (
            "interaction_type",
            "datetime",
            "sentiment",
            "outcomes",
            "follow_up",
        ):
            value = parsed.get(key)
            if value not in {None, ""}:
                updates[key] = value
        
        # Special handling for attendees - append instead of replace
        parsed_attendees = parsed.get("attendees")
        if parsed_attendees and parsed_attendees.strip():
            existing_attendees = (target.attendees or "").strip()
            if existing_attendees:
                # Check if this attendee is already in the list
                existing_list = [a.strip() for a in existing_attendees.split(",")]
                new_list = [a.strip() for a in parsed_attendees.split(",")]
                for new_attendee in new_list:
                    if not any(new_attendee.lower() in existing.lower() or existing.lower() in new_attendee.lower() for existing in existing_list):
                        existing_list.append(new_attendee)
                updates["attendees"] = ", ".join(existing_list)
            else:
                updates["attendees"] = parsed_attendees
        
        # Special handling for topics - append instead of replace
        parsed_topics = parsed.get("topics")
        if parsed_topics and parsed_topics.strip():
            existing_topics = (target.topics or "").strip()
            if existing_topics:
                # Check if this topic is already in the list
                existing_list = [t.strip() for t in existing_topics.split(",")]
                new_list = [t.strip() for t in parsed_topics.split(",")]
                for new_topic in new_list:
                    if new_topic.lower() not in [et.lower() for et in existing_list]:
                        existing_list.append(new_topic)
                updates["topics"] = ", ".join(existing_list)
            else:
                updates["topics"] = parsed_topics
        
        # Append to materials if found
        parsed_materials = parsed.get("materials_shared")
        if parsed_materials and parsed_materials.strip():
            existing_materials = (target.materials_shared or "").strip()
            if existing_materials and existing_materials.lower() != "yes":
                updates["materials_shared"] = f"{existing_materials}, {parsed_materials}"
            else:
                updates["materials_shared"] = parsed_materials
        
        # Append to samples if found
        parsed_samples = parsed.get("samples_distributed")
        if parsed_samples and parsed_samples.strip():
            existing_samples = (target.samples_distributed or "").strip()
            if existing_samples:
                if existing_samples.lower() not in parsed_samples.lower():
                    updates["samples_distributed"] = f"{existing_samples}, {parsed_samples}"
                else:
                    updates["samples_distributed"] = parsed_samples
            else:
                updates["samples_distributed"] = parsed_samples

        # Append to notes
        notes = state.get("text", "")
        if notes:
            existing_notes = target.notes or ""
            updates["notes"] = f"{existing_notes}\n\n{notes}" if existing_notes else notes

        updated = update_interaction(session, target.id, updates)
        return {
            **state,
            "intent": "update",
            "interaction": updated,
            "extracted": parsed,
            "assistant_message": _build_message("update", target=updated),
        }

    def generic_node(state: AssistantState) -> AssistantState:
        return {**state, "intent": "generic", "assistant_message": _build_message("generic")}

    builder = StateGraph(AssistantState)
    builder.add_node("classify", classify_node)
    builder.add_node("log", log_node)
    builder.add_node("summary", summary_node)
    builder.add_node("followup", followup_node)
    builder.add_node("search", search_node)
    builder.add_node("update", update_node)
    builder.add_node("generic", generic_node)

    builder.add_edge(START, "classify")
    builder.add_conditional_edges(
        "classify",
        lambda state: state.get("intent", "generic"),
        {
            "log": "log",
            "summary": "summary",
            "followup": "followup",
            "search": "search",
            "update": "update",
            "generic": "generic",
        },
    )
    for node in ("log", "summary", "followup", "search", "update", "generic"):
        builder.add_edge(node, END)

    return builder.compile()


def run_assistant_request(
    session: Session,
    text: str,
    hcp_id: int | None = None,
    interaction_id: int | None = None,
) -> dict[str, Any]:
    graph = _build_graph(session)
    state = graph.invoke({"text": text or "", "hcp_id": hcp_id, "interaction_id": interaction_id})

    response: dict[str, Any] = {
        "intent": state.get("intent", "generic"),
        "request_text": state.get("request_text") or text or "",
        "assistant_message": state.get("assistant_message") or _build_message("generic"),
    }

    for key in ("interaction", "summary", "recommendations", "search_results", "extracted"):
        value = state.get(key)
        if value:
            response[key] = value

    return response