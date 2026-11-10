import os
from typing import List, Optional, Tuple
from app.config import get_settings
from app.retrieval.search import SearchResult

_reranker_instance = None


def get_reranker_model():
    """Lazy-load the local cross-encoder model."""
    global _reranker_instance
    if _reranker_instance is None:
        from sentence_transformers import CrossEncoder
        settings = get_settings()
        _reranker_instance = CrossEncoder(settings.RERANK_MODEL)
    return _reranker_instance


def _mock_rerank_scores(query: str, texts: List[str]) -> List[float]:
    """Deterministic score generator for testing when mock embeddings are enabled."""
    q_words = set(query.lower().split())
    scores = []
    for text in texts:
        t_words = set(text.lower().split())
        overlap = len(q_words & t_words)
        scores.append(float(overlap) + 0.1)
    return scores


class RerankerService:
    def __init__(self, use_mock: Optional[bool] = None):
        self._custom_mock = use_mock

    @property
    def use_mock(self) -> bool:
        if self._custom_mock is not None:
            return self._custom_mock
        return os.getenv("USE_MOCK_EMBEDDINGS", "0").lower() in ("1", "true", "yes")

    @use_mock.setter
    def use_mock(self, val: bool) -> None:
        self._custom_mock = val

    def rerank(
        self,
        query: str,
        candidates: List[SearchResult],
        top_k: Optional[int] = None,
    ) -> List[SearchResult]:
        """Rerank candidates using local cross-encoder and return top_k candidates."""
        if not candidates:
            return []

        settings = get_settings()
        k = top_k if top_k is not None else settings.TOP_K_FINAL

        pairs = [[query, c.text] for c in candidates]

        if self.use_mock:
            scores = _mock_rerank_scores(query, [c.text for c in candidates])
        else:
            try:
                model = get_reranker_model()
                scores = model.predict(pairs)
                if hasattr(scores, "tolist"):
                    scores = scores.tolist()
            except Exception:
                scores = _mock_rerank_scores(query, [c.text for c in candidates])

        # Pair candidates with scores and sort descending
        scored_candidates = []
        for c, score in zip(candidates, scores):
            c.score = float(score)
            scored_candidates.append(c)

        scored_candidates.sort(key=lambda x: x.score, reverse=True)
        return scored_candidates[:k]


default_reranker_service = RerankerService()
