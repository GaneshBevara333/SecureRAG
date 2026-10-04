from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.rag.answer import generate_rag_answer

router = APIRouter(prefix="/query", tags=["query"])


class QueryRequest(BaseModel):
    question: str = Field(..., description="The user question to answer")
    mode: str = Field("standard", description="'standard' or 'agentic'")


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


@router.post("", response_model=QueryResponse)
def run_query(
    payload: QueryRequest,
    x_org_id: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """Answer question over documents with source citations."""
    result = generate_rag_answer(
        db=db,
        question=payload.question,
        org_id=x_org_id,
    )
    return QueryResponse(
        answer=result["answer"],
        citations=[CitationItem(**c) for c in result["citations"]],
        latency_ms=result["latency_ms"],
        cache_hit=result["cache_hit"],
    )
