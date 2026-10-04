import os
import hashlib
import math
from typing import List, Optional
from app.config import get_settings

_model_instance = None


def get_embedding_model():
    """Lazy load local sentence-transformers embedding model."""
    global _model_instance
    if _model_instance is None:
        from sentence_transformers import SentenceTransformer
        settings = get_settings()
        _model_instance = SentenceTransformer(settings.EMBED_MODEL)
    return _model_instance


def _pseudo_embedding(text: str, dim: int = 384) -> List[float]:
    """Generate a deterministic normalized pseudo-embedding for testing or fallback."""
    vec = []
    # Seed pseudo-random with text hash
    h = hashlib.sha256(text.encode("utf-8")).digest()
    for i in range(dim):
        byte_val = h[i % len(h)]
        val = (byte_val / 128.0) - 1.0 + math.sin(i + (byte_val % 7))
        vec.append(val)
    # Normalize to unit vector
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / norm for x in vec]


class EmbeddingService:
    def __init__(self, use_mock: Optional[bool] = None):
        if use_mock is not None:
            self.use_mock = use_mock
        else:
            self.use_mock = os.getenv("USE_MOCK_EMBEDDINGS", "0").lower() in ("1", "true", "yes")

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        if self.use_mock:
            return [_pseudo_embedding(t) for t in texts]

        try:
            model = get_embedding_model()
            embeddings = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
            return [e.tolist() for e in embeddings]
        except Exception:
            # Fallback to pseudo embedding if model loading fails
            return [_pseudo_embedding(t) for t in texts]

    def embed_query(self, text: str) -> List[float]:
        return self.embed_texts([text])[0]

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return self.embed_texts(texts)


default_embedding_service = EmbeddingService()
