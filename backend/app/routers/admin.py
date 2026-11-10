import statistics
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.db.models import QueryLog, User
from app.auth.deps import require_admin, CurrentUser

router = APIRouter(prefix="/admin", tags=["admin"])


class PerUserUsage(BaseModel):
    user_id: str
    email: str
    query_count: int
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class AdminUsageResponse(BaseModel):
    total_queries: int
    total_prompt_tokens: int
    total_completion_tokens: int
    total_tokens: int
    avg_latency_ms: float
    p50_latency_ms: float
    p95_latency_ms: float
    cache_hit_rate: float
    per_user_usage: List[PerUserUsage]


@router.get("/usage", response_model=AdminUsageResponse)
def get_org_usage(
    current_user: CurrentUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Return aggregated token counts, latency metrics, cache hit rate, and per-user usage for the org."""
    logs = (
        db.query(QueryLog)
        .filter(QueryLog.org_id == current_user.org_id)
        .all()
    )

    total_queries = len(logs)
    total_prompt_tokens = sum(l.prompt_tokens or 0 for l in logs)
    total_completion_tokens = sum(l.completion_tokens or 0 for l in logs)
    total_tokens = total_prompt_tokens + total_completion_tokens

    latencies = [l.latency_ms for l in logs if l.latency_ms is not None]
    if latencies:
        avg_latency = round(statistics.mean(latencies), 2)
        sorted_lat = sorted(latencies)
        # Quantiles / percentiles
        p50_idx = int(0.50 * (len(sorted_lat) - 1))
        p95_idx = int(0.95 * (len(sorted_lat) - 1))
        p50_latency = round(sorted_lat[p50_idx], 2)
        p95_latency = round(sorted_lat[p95_idx], 2)
    else:
        avg_latency = 0.0
        p50_latency = 0.0
        p95_latency = 0.0

    cache_hits = sum(1 for l in logs if l.cache_hit)
    cache_hit_rate = round(cache_hits / total_queries, 4) if total_queries > 0 else 0.0

    # User breakdown
    users_in_org = db.query(User).filter(User.org_id == current_user.org_id).all()
    user_map = {u.id: u.email for u in users_in_org}

    user_stats: Dict[str, Dict[str, Any]] = {}
    for uid, email in user_map.items():
        user_stats[uid] = {
            "user_id": uid,
            "email": email,
            "query_count": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }

    for l in logs:
        if l.user_id in user_stats:
            user_stats[l.user_id]["query_count"] += 1
            user_stats[l.user_id]["prompt_tokens"] += (l.prompt_tokens or 0)
            user_stats[l.user_id]["completion_tokens"] += (l.completion_tokens or 0)
            user_stats[l.user_id]["total_tokens"] += (l.prompt_tokens or 0) + (l.completion_tokens or 0)

    per_user_list = [PerUserUsage(**stats) for stats in user_stats.values()]

    return AdminUsageResponse(
        total_queries=total_queries,
        total_prompt_tokens=total_prompt_tokens,
        total_completion_tokens=total_completion_tokens,
        total_tokens=total_tokens,
        avg_latency_ms=avg_latency,
        p50_latency_ms=p50_latency,
        p95_latency_ms=p95_latency,
        cache_hit_rate=cache_hit_rate,
        per_user_usage=per_user_list,
    )
