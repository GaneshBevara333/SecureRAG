import math
from typing import List, Tuple, Optional, Dict
from collections import defaultdict
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.db.models import Chunk, Document
from app.retrieval.embed import default_embedding_service
from app.retrieval.acl import build_acl_sql, build_chunk_acl_condition
from app.config import get_settings


def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    """Compute cosine similarity between two float vectors."""
    dot = sum(a * b for a, b in zip(v1, v2))
    norm_a = math.sqrt(sum(a * a for a in v1))
    norm_b = math.sqrt(sum(b * b for b in v2))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


class SearchResult:
    def __init__(
        self,
        chunk_id: str,
        document_id: str,
        text: str,
        score: float,
        chunk_index: int,
        page: Optional[int] = None,
        filename: Optional[str] = None,
    ):
        self.chunk_id = chunk_id
        self.document_id = document_id
        self.text = text
        self.score = score
        self.chunk_index = chunk_index
        self.page = page
        self.filename = filename

    def to_dict(self):
        return {
            "chunk_id": self.chunk_id,
            "document_id": self.document_id,
            "text": self.text,
            "score": self.score,
            "chunk_index": self.chunk_index,
            "page": self.page,
            "filename": self.filename,
        }


def dense_search(
    db: Session,
    query: str,
    org_id: Optional[str] = None,
    user_id: Optional[str] = None,
    is_admin: bool = False,
    team_ids: Optional[List[str]] = None,
    top_k: Optional[int] = None,
) -> List[SearchResult]:
    """
    Execute dense vector search against chunks in database.
    ACL filters are applied directly INSIDE the SQL query (never post-filtered).
    """
    settings = get_settings()
    k = top_k if top_k is not None else settings.TOP_K_CANDIDATES
    query_vector = default_embedding_service.embed_query(query)
    effective_team_ids = team_ids or []

    is_postgres = db.bind is not None and db.bind.dialect.name == "postgresql"

    if is_postgres:
        qvec_str = "[" + ",".join(str(x) for x in query_vector) + "]"
        params = {"qvec": qvec_str, "k": k}

        if org_id and user_id:
            acl_where, acl_params = build_acl_sql(
                user_id=user_id,
                org_id=org_id,
                is_admin=is_admin,
                team_ids=effective_team_ids,
            )
            params.update(acl_params)
        elif org_id:
            acl_where = "c.org_id = :org_id"
            params["org_id"] = org_id
        else:
            acl_where = "1=1"

        stmt = f"""
        SELECT c.id, c.document_id, c.text, c.chunk_index, c.page, d.filename,
               1 - (c.embedding <=> CAST(:qvec AS vector)) as similarity
        FROM chunks c
        JOIN documents d ON d.id = c.document_id
        WHERE {acl_where}
        ORDER BY c.embedding <=> CAST(:qvec AS vector)
        LIMIT :k
        """
        rows = db.execute(text(stmt), params).fetchall()

        results = []
        for r in rows:
            results.append(
                SearchResult(
                    chunk_id=r[0],
                    document_id=r[1],
                    text=r[2],
                    chunk_index=r[3],
                    page=r[4],
                    filename=r[5],
                    score=float(r[6]) if r[6] is not None else 0.0,
                )
            )
        return results

    else:
        # SQLite / In-memory fallback: apply ACL filter inside the ORM query
        query_db = db.query(Chunk, Document.filename).join(Document, Chunk.document_id == Document.id)

        if org_id and user_id:
            query_db = query_db.filter(
                build_chunk_acl_condition(
                    user_id=user_id,
                    org_id=org_id,
                    is_admin=is_admin,
                    team_ids=effective_team_ids,
                )
            )
        elif org_id:
            query_db = query_db.filter(Chunk.org_id == org_id)

        rows = query_db.all()
        scored_results: List[Tuple[SearchResult, float]] = []

        for chunk, filename in rows:
            emb = chunk.embedding
            if emb is not None:
                sim = cosine_similarity(query_vector, emb)
                res = SearchResult(
                    chunk_id=chunk.id,
                    document_id=chunk.document_id,
                    text=chunk.text,
                    chunk_index=chunk.chunk_index,
                    page=chunk.page,
                    filename=filename,
                    score=sim,
                )
                scored_results.append((res, sim))

        # Sort descending by similarity
        scored_results.sort(key=lambda x: x[1], reverse=True)
        return [item[0] for item in scored_results[:k]]


def sparse_search(
    db: Session,
    query: str,
    org_id: Optional[str] = None,
    user_id: Optional[str] = None,
    is_admin: bool = False,
    team_ids: Optional[List[str]] = None,
    top_k: Optional[int] = None,
) -> List[SearchResult]:
    """
    Execute sparse full-text search against chunks in database.
    ACL filters are applied directly INSIDE the SQL query (never post-filtered).
    """
    settings = get_settings()
    k = top_k if top_k is not None else settings.TOP_K_CANDIDATES
    effective_team_ids = team_ids or []

    is_postgres = db.bind is not None and db.bind.dialect.name == "postgresql"

    if is_postgres:
        params = {"q": query, "k": k}

        if org_id and user_id:
            acl_where, acl_params = build_acl_sql(
                user_id=user_id,
                org_id=org_id,
                is_admin=is_admin,
                team_ids=effective_team_ids,
            )
            params.update(acl_params)
        elif org_id:
            acl_where = "c.org_id = :org_id"
            params["org_id"] = org_id
        else:
            acl_where = "1=1"

        stmt = f"""
        SELECT c.id, c.document_id, c.text, c.chunk_index, c.page, d.filename,
               ts_rank_cd(c.tsv, plainto_tsquery('english', :q)) as rank
        FROM chunks c
        JOIN documents d ON d.id = c.document_id
        WHERE {acl_where} AND c.tsv @@ plainto_tsquery('english', :q)
        ORDER BY ts_rank_cd(c.tsv, plainto_tsquery('english', :q)) DESC
        LIMIT :k
        """
        rows = db.execute(text(stmt), params).fetchall()

        results = []
        for r in rows:
            results.append(
                SearchResult(
                    chunk_id=r[0],
                    document_id=r[1],
                    text=r[2],
                    chunk_index=r[3],
                    page=r[4],
                    filename=r[5],
                    score=float(r[6]) if r[6] is not None else 0.0,
                )
            )
        return results

    else:
        # SQLite / In-memory fallback: text token overlap scoring
        query_db = db.query(Chunk, Document.filename).join(Document, Chunk.document_id == Document.id)

        if org_id and user_id:
            query_db = query_db.filter(
                build_chunk_acl_condition(
                    user_id=user_id,
                    org_id=org_id,
                    is_admin=is_admin,
                    team_ids=effective_team_ids,
                )
            )
        elif org_id:
            query_db = query_db.filter(Chunk.org_id == org_id)

        rows = query_db.all()
        q_tokens = set(query.lower().split())

        scored_results: List[Tuple[SearchResult, float]] = []
        for chunk, filename in rows:
            text_lower = chunk.text.lower()
            text_tokens = set(text_lower.split())
            overlap = len(q_tokens & text_tokens)
            if overlap > 0 or any(token in text_lower for token in q_tokens if len(token) > 3):
                score = float(overlap) + (0.5 if query.lower() in text_lower else 0.0)
                res = SearchResult(
                    chunk_id=chunk.id,
                    document_id=chunk.document_id,
                    text=chunk.text,
                    chunk_index=chunk.chunk_index,
                    page=chunk.page,
                    filename=filename,
                    score=score,
                )
                scored_results.append((res, score))

        scored_results.sort(key=lambda x: x[1], reverse=True)
        return [item[0] for item in scored_results[:k]]


def reciprocal_rank_fusion(
    dense_results: List[SearchResult],
    sparse_results: List[SearchResult],
    k: int = 60,
) -> List[SearchResult]:
    """
    Fuse dense and sparse retrieval results using Reciprocal Rank Fusion (RRF).
    score(d) = sum_{m in {dense, sparse}} 1 / (k + rank_m(d))
    """
    scores: Dict[str, float] = defaultdict(float)
    chunk_map: Dict[str, SearchResult] = {}

    for rank, res in enumerate(dense_results, start=1):
        scores[res.chunk_id] += 1.0 / (k + rank)
        chunk_map[res.chunk_id] = res

    for rank, res in enumerate(sparse_results, start=1):
        scores[res.chunk_id] += 1.0 / (k + rank)
        if res.chunk_id not in chunk_map:
            chunk_map[res.chunk_id] = res

    # Sort chunks by fused RRF score descending
    sorted_chunk_ids = sorted(scores.keys(), key=lambda cid: scores[cid], reverse=True)

    fused_results = []
    for cid in sorted_chunk_ids:
        item = chunk_map[cid]
        item.score = scores[cid]
        fused_results.append(item)

    return fused_results


def hybrid_search(
    db: Session,
    query: str,
    org_id: Optional[str] = None,
    user_id: Optional[str] = None,
    is_admin: bool = False,
    team_ids: Optional[List[str]] = None,
    top_k: Optional[int] = None,
) -> List[SearchResult]:
    """Execute dense and sparse search and fuse results with RRF (k=60)."""
    settings = get_settings()
    candidate_k = settings.TOP_K_CANDIDATES

    dense_candidates = dense_search(
        db=db,
        query=query,
        org_id=org_id,
        user_id=user_id,
        is_admin=is_admin,
        team_ids=team_ids,
        top_k=candidate_k,
    )
    sparse_candidates = sparse_search(
        db=db,
        query=query,
        org_id=org_id,
        user_id=user_id,
        is_admin=is_admin,
        team_ids=team_ids,
        top_k=candidate_k,
    )

    fused = reciprocal_rank_fusion(dense_candidates, sparse_candidates, k=60)
    k_final = top_k if top_k is not None else settings.TOP_K_FINAL
    return fused[:k_final]


def retrieve_chunks(
    db: Session,
    query: str,
    org_id: Optional[str] = None,
    user_id: Optional[str] = None,
    is_admin: bool = False,
    team_ids: Optional[List[str]] = None,
    retrieval_mode: str = "hybrid+rerank",
    top_k: Optional[int] = None,
) -> List[SearchResult]:
    """
    Configurable multi-mode retrieval pipeline:
    - 'dense': pgvector cosine distance search
    - 'hybrid': dense + sparse (tsvector) fused via RRF (k=60)
    - 'hybrid+rerank': hybrid search reranked with local cross-encoder
    """
    settings = get_settings()
    k_final = top_k if top_k is not None else settings.TOP_K_FINAL
    norm_mode = retrieval_mode.lower().strip()

    if norm_mode == "dense":
        return dense_search(
            db=db,
            query=query,
            org_id=org_id,
            user_id=user_id,
            is_admin=is_admin,
            team_ids=team_ids,
            top_k=k_final,
        )

    elif norm_mode == "hybrid":
        return hybrid_search(
            db=db,
            query=query,
            org_id=org_id,
            user_id=user_id,
            is_admin=is_admin,
            team_ids=team_ids,
            top_k=k_final,
        )

    elif norm_mode in ("hybrid+rerank", "hybrid_rerank"):
        from app.retrieval.rerank import default_reranker_service

        # Step 1: Hybrid candidate generation (TOP_K_CANDIDATES)
        candidates = hybrid_search(
            db=db,
            query=query,
            org_id=org_id,
            user_id=user_id,
            is_admin=is_admin,
            team_ids=team_ids,
            top_k=settings.TOP_K_CANDIDATES,
        )
        # If hybrid returned candidates, rerank them
        if not candidates:
            # Also try dense fallback if sparse was empty
            candidates = dense_search(
                db=db,
                query=query,
                org_id=org_id,
                user_id=user_id,
                is_admin=is_admin,
                team_ids=team_ids,
                top_k=settings.TOP_K_CANDIDATES,
            )

        # Step 2: Cross-encoder reranking
        return default_reranker_service.rerank(
            query=query,
            candidates=candidates,
            top_k=k_final,
        )

    else:
        # Default fallback to hybrid+rerank
        return retrieve_chunks(
            db=db,
            query=query,
            org_id=org_id,
            user_id=user_id,
            is_admin=is_admin,
            team_ids=team_ids,
            retrieval_mode="hybrid+rerank",
            top_k=k_final,
        )
