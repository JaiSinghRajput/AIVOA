from typing import Optional
import re

from sqlmodel import Session, select

from models import HCP


TITLE_WORDS = {"dr", "doctor", "mr", "mrs", "ms", "miss", "hcp"}
SEARCH_STOP_WORDS = {
    "interaction",
    "interactions",
    "search",
    "find",
    "show",
    "get",
    "for",
    "of",
    "with",
    "details",
    "detail",
}


def normalize_hcp_query(value: str | None) -> str:
    text = (value or "").lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    tokens = [token for token in text.split() if token not in TITLE_WORDS and token not in SEARCH_STOP_WORDS]
    return " ".join(tokens)


def hcp_match_score(name: str, query: str | None) -> int:
    normalized_name = normalize_hcp_query(name)
    normalized_query = normalize_hcp_query(query)
    if not normalized_query:
        return 1

    query_tokens = normalized_query.split()
    if not query_tokens:
        return 1

    if normalized_name == normalized_query:
        return 1000
    if normalized_query in normalized_name:
        return 800 + len(normalized_query)

    score = 0
    name_tokens = set(normalized_name.split())
    for token in query_tokens:
        if token in name_tokens:
            score += 120
        elif any(part.startswith(token) for part in name_tokens):
            score += 80
        elif token in normalized_name:
            score += 40
    return score


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
    hcps = session.exec(select(HCP)).all()
    if not query or not query.strip():
        return hcps[:limit]

    scored = [(hcp, hcp_match_score(hcp.name, query)) for hcp in hcps]
    matches = [(hcp, score) for hcp, score in scored if score > 0]
    matches.sort(key=lambda item: (-item[1], item[0].name.lower()))
    return [hcp for hcp, _ in matches[:limit]]


def create_hcp(session: Session, name: str, specialty: Optional[str], location: Optional[str]) -> HCP:
    hcp = HCP(name=name, specialty=specialty, location=location)
    session.add(hcp)
    session.commit()
    session.refresh(hcp)
    return hcp
