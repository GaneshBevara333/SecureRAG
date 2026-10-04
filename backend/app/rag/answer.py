import time
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from langchain_core.messages import SystemMessage, HumanMessage
from app.retrieval.search import dense_search, SearchResult
from app.llm.prompts import SYSTEM_PROMPT, format_context, build_rag_prompt
from app.llm.providers import get_llm


def generate_rag_answer(
    db: Session,
    question: str,
    org_id: Optional[str] = None,
    top_k: Optional[int] = None,
) -> Dict[str, Any]:
    """Retrieve relevant chunks and generate grounded answer with citations."""
    start_time = time.perf_counter()

    chunks: List[SearchResult] = dense_search(db, query=question, org_id=org_id, top_k=top_k)

    if not chunks:
        latency_ms = (time.perf_counter() - start_time) * 1000.0
        return {
            "answer": "not found in your documents",
            "citations": [],
            "latency_ms": round(latency_ms, 2),
            "cache_hit": False,
            "provider": "none",
            "retrieved_chunk_ids": [],
            "scores": [],
        }

    context_str = format_context(chunks)
    prompt_str = build_rag_prompt(question, context_str)

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=prompt_str),
    ]

    llm = get_llm()
    response = llm.invoke(messages)
    answer_text = response.content if isinstance(response.content, str) else str(response.content)

    latency_ms = (time.perf_counter() - start_time) * 1000.0

    citations = [
        {
            "chunk_id": c.chunk_id,
            "document_id": c.document_id,
            "filename": c.filename,
            "page": c.page,
            "chunk_index": c.chunk_index,
            "score": round(c.score, 4),
        }
        for c in chunks
    ]

    provider_name = getattr(llm, "_llm_type", "groq")

    return {
        "answer": answer_text,
        "citations": citations,
        "latency_ms": round(latency_ms, 2),
        "cache_hit": False,
        "provider": provider_name,
        "retrieved_chunk_ids": [c.chunk_id for c in chunks],
        "scores": [c.score for c in chunks],
    }
