import hashlib
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from app.db.models import Organization, ResponseCache


def normalize_question(question: str) -> str:
    """Normalize question by converting to lowercase and collapsing consecutive whitespace."""
    return " ".join(question.strip().lower().split())


def compute_cache_key(user_id: str, question: str, corpus_version: int) -> str:
    """
    Compute sha256(user_id + normalized question + corpus_version).
    The key MUST include user_id so cached answers never cross permission boundaries.
    """
    norm_q = normalize_question(question)
    raw = f"{user_id}:{norm_q}:{corpus_version}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def get_corpus_version(db: Session, org_id: str) -> int:
    """Get the current corpus version for an organization (defaults to 1)."""
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if org and getattr(org, "corpus_version", None) is not None:
        return org.corpus_version
    return 1


def bump_corpus_version(db: Session, org_id: str) -> int:
    """
    Increment corpus_version for an organization upon document upload or deletion.
    This safely invalidates all cached responses whose keys depended on the previous version.
    """
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if org:
        current = getattr(org, "corpus_version", 1) or 1
        org.corpus_version = current + 1
        db.commit()
        db.refresh(org)
        return org.corpus_version
    return 1


def get_cached_response(
    db: Session,
    user_id: str,
    org_id: str,
    question: str,
) -> Optional[Dict[str, Any]]:
    """Look up cached response for user_id + question + current corpus_version."""
    corpus_version = get_corpus_version(db, org_id)
    cache_key = compute_cache_key(user_id=user_id, question=question, corpus_version=corpus_version)
    
    cached = db.query(ResponseCache).filter(ResponseCache.key == cache_key).first()
    if cached:
        return {
            "answer": cached.answer,
            "citations": cached.citations or [],
            "cache_hit": True,
            "cache_key": cache_key,
            "corpus_version": cached.corpus_version,
        }
    return None


def set_cached_response(
    db: Session,
    user_id: str,
    org_id: str,
    question: str,
    answer: str,
    citations: List[Dict[str, Any]],
) -> str:
    """Save an answer and citations in response_cache for the user's current corpus_version."""
    corpus_version = get_corpus_version(db, org_id)
    cache_key = compute_cache_key(user_id=user_id, question=question, corpus_version=corpus_version)
    
    existing = db.query(ResponseCache).filter(ResponseCache.key == cache_key).first()
    if existing:
        existing.answer = answer
        existing.citations = citations
        existing.corpus_version = corpus_version
    else:
        new_entry = ResponseCache(
            key=cache_key,
            user_id=user_id,
            answer=answer,
            citations=citations,
            corpus_version=corpus_version,
        )
        db.add(new_entry)
    db.commit()
    return cache_key
