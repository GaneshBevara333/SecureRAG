import time
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from app.db.models import EvalCase, EvalRun, EvalResult
from app.rag.answer import generate_rag_answer
from app.retrieval.search import retrieve_chunks
from app.llm.prompts import format_context
from app.evals.metrics import compute_rank, compute_hit_at_k, compute_mrr, compute_latency_percentiles
from app.evals.judge import judge_service


def run_evaluation(
    db: Session,
    org_id: str,
    label: str,
    config: Optional[Dict[str, Any]] = None,
) -> EvalRun:
    """
    Run evaluation suite for all eval cases in the specified org.
    Computes hit@k, MRR, latency (p50/p95), and faithfulness via LLM-as-judge.
    """
    if config is None:
        config = {}

    retrieval_mode = config.get("retrieval_mode", "hybrid+rerank")
    top_k = config.get("top_k", None)

    # 1. Fetch eval cases for this organization
    cases = (
        db.query(EvalCase)
        .filter(EvalCase.org_id == org_id)
        .order_by(EvalCase.created_at.asc())
        .all()
    )
    if not cases:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No eval cases found for this organization. Add cases first.",
        )

    # 2. Initialize EvalRun record
    eval_run = EvalRun(
        org_id=org_id,
        label=label,
        config=config,
    )
    db.add(eval_run)
    db.flush()

    results: List[EvalResult] = []
    latencies: List[float] = []

    # 3. Execute evaluation per case
    for case in cases:
        rag_res = generate_rag_answer(
            db=db,
            question=case.question,
            org_id=org_id,
            is_admin=True,
            retrieval_mode=retrieval_mode,
            top_k=top_k,
        )

        citation_doc_ids = [c["document_id"] for c in rag_res.get("citations", [])]
        rank = compute_rank(case.expected_doc_id, citation_doc_ids)
        hit = (rank is not None) if case.expected_doc_id else (len(citation_doc_ids) > 0)

        # Context for judge
        retrieved_contexts = [f"[{c['filename']}]: {c.get('chunk_index', 0)}" for c in rag_res.get("citations", [])]
        context_str = "\n".join(retrieved_contexts) if retrieved_contexts else "No context retrieved."

        # Evaluate faithfulness using cached judge service
        faithfulness_score = judge_service.evaluate_faithfulness(
            question=case.question,
            answer=rag_res["answer"],
            context=context_str,
        )

        latency = float(rag_res.get("latency_ms", 0.0))
        latencies.append(latency)

        eval_result = EvalResult(
            run_id=eval_run.id,
            case_id=case.id,
            hit=hit,
            rank=rank,
            faithfulness=faithfulness_score,
            latency_ms=latency,
            answer=rag_res["answer"],
        )
        db.add(eval_result)
        results.append(eval_result)

    # 4. Compute aggregate metrics
    eval_run.hit_at_k = compute_hit_at_k([r.hit for r in results])
    eval_run.mrr = compute_mrr([r.rank for r in results])
    eval_run.faithfulness = (
        sum(r.faithfulness for r in results) / len(results) if results else 0.0
    )
    p50, p95 = compute_latency_percentiles(latencies)
    eval_run.p50_ms = p50
    eval_run.p95_ms = p95

    db.commit()
    db.refresh(eval_run)

    return eval_run
