import math
from typing import List, Tuple, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.db.models import Chunk, Document
from app.retrieval.embed import default_embedding_service
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
    top_k: Optional[int] = None,
) -> List[SearchResult]:
    """Execute dense vector search against chunks in database."""
    settings = get_settings()
    k = top_k if top_k is not None else settings.TOP_K_FINAL
    query_vector = default_embedding_service.embed_query(query)

    is_postgres = db.bind is not None and db.bind.dialect.name == "postgresql"

    if is_postgres:
        # Use pgvector cosine distance operator <=>
        stmt = """
        SELECT c.id, c.document_id, c.text, c.chunk_index, c.page, d.filename,
               1 - (c.embedding <=> :qvec::vector) as similarity
        FROM chunks c
        JOIN documents d ON d.id = c.document_id
        WHERE (:org_id IS NULL OR c.org_id = :org_id)
        ORDER BY c.embedding <=> :qvec::vector
        LIMIT :k
        """
        # Format query_vector as string '[0.1, 0.2, ...]'
        qvec_str = "[" + ",".join(str(x) for x in query_vector) + "]"
        rows = db.execute(
            text(stmt),
            {"qvec": qvec_str, "org_id": org_id, "k": k}
        ).fetchall()

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
        # SQLite / In-memory fallback: compute cosine similarity in Python
        query_db = db.query(Chunk, Document.filename).join(Document, Chunk.document_id == Document.id)
        if org_id:
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
