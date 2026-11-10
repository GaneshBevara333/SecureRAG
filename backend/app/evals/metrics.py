import statistics
from typing import List, Optional, Tuple


def compute_rank(expected_doc_id: Optional[str], retrieved_doc_ids: List[str]) -> Optional[int]:
    """
    Return 1-based rank of the first occurrence of expected_doc_id in retrieved_doc_ids.
    Returns None if not found or if expected_doc_id is not specified.
    """
    if not expected_doc_id:
        return 1 if retrieved_doc_ids else None
    try:
        idx = retrieved_doc_ids.index(expected_doc_id)
        return idx + 1
    except ValueError:
        return None


def compute_hit_at_k(hits: List[bool]) -> float:
    """Return fraction of hits across cases."""
    if not hits:
        return 0.0
    return sum(1.0 if h else 0.0 for h in hits) / len(hits)


def compute_mrr(ranks: List[Optional[int]]) -> float:
    """Return Mean Reciprocal Rank (MRR) across cases."""
    if not ranks:
        return 0.0
    rr_scores = [1.0 / r if (r is not None and r > 0) else 0.0 for r in ranks]
    return sum(rr_scores) / len(rr_scores)


def compute_latency_percentiles(latencies: List[float]) -> Tuple[float, float]:
    """Return (p50_ms, p95_ms) percentiles for a list of latencies."""
    if not latencies:
        return 0.0, 0.0
    sorted_lats = sorted(latencies)
    n = len(sorted_lats)
    p50_idx = int(0.50 * (n - 1))
    p95_idx = int(0.95 * (n - 1))
    return round(sorted_lats[p50_idx], 2), round(sorted_lats[p95_idx], 2)
