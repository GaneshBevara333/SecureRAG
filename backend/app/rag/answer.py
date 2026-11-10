import time
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from langchain_core.messages import SystemMessage, HumanMessage
from app.retrieval.search import retrieve_chunks, SearchResult
from app.llm.prompts import SYSTEM_PROMPT, format_context, build_rag_prompt
from app.llm import providers


def generate_rag_answer(
    db: Session,
    question: str,
    org_id: Optional[str] = None,
    user_id: Optional[str] = None,
    is_admin: bool = False,
    team_ids: Optional[List[str]] = None,
    retrieval_mode: str = "hybrid+rerank",
    top_k: Optional[int] = None,
) -> Dict[str, Any]:
    """Retrieve relevant chunks with ACL enforcement and generate grounded answer with citations."""
    start_time = time.perf_counter()

    chunks: List[SearchResult] = retrieve_chunks(
        db=db,
        query=question,
        org_id=org_id,
        user_id=user_id,
        is_admin=is_admin,
        team_ids=team_ids,
        retrieval_mode=retrieval_mode,
        top_k=top_k,
    )

    if not chunks:
        latency_ms = (time.perf_counter() - start_time) * 1000.0
        prompt_tokens = max(1, (len(SYSTEM_PROMPT) + len(question)) // 4)
        completion_tokens = max(1, len("not found in your documents") // 4)
        return {
            "answer": "not found in your documents",
            "citations": [],
            "latency_ms": round(latency_ms, 2),
            "cache_hit": False,
            "provider": "none",
            "retrieved_chunk_ids": [],
            "scores": [],
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
        }

    context_str = format_context(chunks)
    prompt_str = build_rag_prompt(question, context_str)

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=prompt_str),
    ]

    llm = providers.get_llm()
    response = llm.invoke(messages)
    answer_text = response.content if isinstance(response.content, str) else str(response.content)
    latency_ms = (time.perf_counter() - start_time) * 1000.0

    prompt_tokens = 0
    completion_tokens = 0

    if hasattr(response, "usage_metadata") and response.usage_metadata:
        prompt_tokens = response.usage_metadata.get("input_tokens", 0)
        completion_tokens = response.usage_metadata.get("output_tokens", 0)

    if not prompt_tokens and hasattr(response, "response_metadata") and response.response_metadata:
        token_usage = response.response_metadata.get("token_usage", {})
        if token_usage:
            prompt_tokens = token_usage.get("prompt_tokens", 0)
            completion_tokens = token_usage.get("completion_tokens", 0)

    if prompt_tokens == 0:
        prompt_tokens = max(1, (len(SYSTEM_PROMPT) + len(prompt_str)) // 4)
    if completion_tokens == 0:
        completion_tokens = max(1, len(answer_text) // 4)

    if answer_text.strip().lower() == "not found in your documents":
        citations = []
    else:
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

    provider_name = providers.determine_provider(response, llm)

    return {
        "answer": answer_text,
        "citations": citations,
        "latency_ms": round(latency_ms, 2),
        "cache_hit": False,
        "provider": provider_name,
        "retrieved_chunk_ids": [c.chunk_id for c in chunks],
        "scores": [c.score for c in chunks],
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
    }
