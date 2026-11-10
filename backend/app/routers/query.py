from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.db.models import QueryLog
from app.rag.answer import generate_rag_answer
from app.auth.deps import get_current_user_or_api_key, CurrentUser
from app.auth.rate_limit import rate_limiter
from app.llm.cache import get_cached_response, set_cached_response

router = APIRouter(prefix="/query", tags=["query"])


class QueryRequest(BaseModel):
    question: str = Field(..., description="The user question to answer")
    mode: str = Field("standard", description="'standard' or 'agentic'")
    retrieval_mode: str = Field("hybrid+rerank", description="'dense', 'hybrid', or 'hybrid+rerank'")


class CitationItem(BaseModel):
    chunk_id: str
    document_id: str
    filename: Optional[str] = None
    page: Optional[int] = None
    chunk_index: int
    score: float


class QueryResponse(BaseModel):
    answer: str
    citations: List[CitationItem]
    latency_ms: float
    cache_hit: bool = False
    query_log_id: Optional[str] = None


class QueryLogItem(BaseModel):
    id: str
    org_id: str
    user_id: str
    question: str
    answer: str
    retrieved_chunk_ids: List[str] = []
    scores: List[float] = []
    latency_ms: float
    prompt_tokens: int
    completion_tokens: int
    provider: str
    cache_hit: bool
    mode: str
    created_at: datetime


@router.post("", response_model=QueryResponse)
def run_query(
    payload: QueryRequest,
    current_user: CurrentUser = Depends(get_current_user_or_api_key),
    db: Session = Depends(get_db),
):
    """
    Answer question over documents with retrieval-time access control,
    per-user rate limiting, API-key/JWT auth, and query logging with token counts.
    """
    # 1. Enforce per-user token bucket rate limiting (raises 429 with Retry-After)
    rate_limiter.check(current_user.id)

    # 2. Check response cache keyed by sha256(user_id + normalized question + corpus_version)
    cached = get_cached_response(
        db=db,
        user_id=current_user.id,
        org_id=current_user.org_id,
        question=payload.question,
    )

    if cached:
        answer = cached["answer"]
        citations = cached["citations"]
        latency_ms = 1.0
        cache_hit = True
        provider = "cache"
        prompt_tokens = 0
        completion_tokens = 0
        retrieved_chunk_ids = [c["chunk_id"] for c in citations if isinstance(c, dict) and "chunk_id" in c]
        scores = [c["score"] for c in citations if isinstance(c, dict) and "score" in c]
    else:
        # 3. Execute RAG answer generation with ACL filter inside retrieval
        result = generate_rag_answer(
            db=db,
            question=payload.question,
            org_id=current_user.org_id,
            user_id=current_user.id,
            is_admin=(current_user.role == "admin"),
            team_ids=current_user.team_ids,
            retrieval_mode=payload.retrieval_mode,
        )
        answer = result["answer"]
        citations = result["citations"]
        latency_ms = result["latency_ms"]
        cache_hit = False
        provider = result.get("provider", "groq")
        prompt_tokens = result.get("prompt_tokens", 0)
        completion_tokens = result.get("completion_tokens", 0)
        retrieved_chunk_ids = result.get("retrieved_chunk_ids", [])
        scores = result.get("scores", [])

        # Store response in cache for the user's current corpus_version
        set_cached_response(
            db=db,
            user_id=current_user.id,
            org_id=current_user.org_id,
            question=payload.question,
            answer=answer,
            citations=citations,
        )

    # 4. Log prompt/completion tokens and query metadata in query_logs table
    query_log = QueryLog(
        org_id=current_user.org_id,
        user_id=current_user.id,
        question=payload.question,
        answer=answer,
        retrieved_chunk_ids=retrieved_chunk_ids,
        scores=scores,
        latency_ms=latency_ms,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        provider=provider,
        cache_hit=cache_hit,
        mode=payload.mode,
    )
    db.add(query_log)
    db.commit()
    db.refresh(query_log)

    return QueryResponse(
        answer=answer,
        citations=[CitationItem(**c) for c in citations],
        latency_ms=latency_ms,
        cache_hit=cache_hit,
        query_log_id=query_log.id,
    )


@router.get("/logs", response_model=List[QueryLogItem])
def list_user_query_logs(
    current_user: CurrentUser = Depends(get_current_user_or_api_key),
    db: Session = Depends(get_db),
):
    """List query logs for the authenticated user only (users cannot read others' logs)."""
    logs = (
        db.query(QueryLog)
        .filter(QueryLog.user_id == current_user.id, QueryLog.org_id == current_user.org_id)
        .order_by(QueryLog.created_at.desc())
        .all()
    )
    return logs


@router.get("/logs/{log_id}", response_model=QueryLogItem)
def get_user_query_log(
    log_id: str,
    current_user: CurrentUser = Depends(get_current_user_or_api_key),
    db: Session = Depends(get_db),
):
    """Retrieve a single query log by ID; returns 404 if log belongs to another user or doesn't exist."""
    log = (
        db.query(QueryLog)
        .filter(QueryLog.id == log_id, QueryLog.user_id == current_user.id, QueryLog.org_id == current_user.org_id)
        .first()
    )
    if not log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Query log not found",
        )
    return log
