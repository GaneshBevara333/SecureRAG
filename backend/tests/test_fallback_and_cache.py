import pytest
from langchain_core.messages import AIMessage
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.outputs import ChatResult, ChatGeneration
from app.auth.rate_limit import rate_limiter
from app.db.models import QueryLog, Organization, ResponseCache
from app.llm import providers
from app.llm.cache import compute_cache_key, get_corpus_version, bump_corpus_version


def _register(client, email: str, org_name: str = "Cache Corp"):
    rate_limiter.reset()
    res = client.post(
        "/auth/register",
        json={"org_name": org_name, "email": email, "password": "password123"},
    )
    assert res.status_code == 201
    token = res.json()["access_token"]
    user_id = res.json()["user"]["id"]
    org_id = res.json()["user"]["org_id"]
    return token, user_id, org_id


def test_provider_fallback_on_429(client, monkeypatch, db_session):
    """Simulated Groq 429 error falls back to Gemini with LangChain with_fallbacks and logs provider."""
    token, user_id, org_id = _register(client, "fallback_user@corp.local")
    headers = {"Authorization": f"Bearer {token}"}

    # Upload document
    client.post(
        "/documents",
        headers=headers,
        files={"file": ("guide.txt", b"Deployment procedure: commit to main and trigger GitHub Actions.", "text/plain")},
        data={"title": "Deployment", "visibility": "org"},
    )

    # Create mock Groq that raises 429
    class FailingGroqModel(BaseChatModel):
        def _generate(self, messages, stop=None, **kwargs):
            raise Exception("429 Too Many Requests: Groq rate limit exceeded")

        @property
        def _llm_type(self):
            return "groq"

    # Create mock Gemini fallback model that succeeds
    class WorkingGeminiModel(BaseChatModel):
        def _generate(self, messages, stop=None, **kwargs):
            msg = AIMessage(
                content="Deployment is handled via GitHub Actions on main branch.",
                response_metadata={"model_name": "gemini-1.5-flash", "provider": "gemini"},
                usage_metadata={"input_tokens": 15, "output_tokens": 10, "total_tokens": 25},
            )
            return ChatResult(generations=[ChatGeneration(message=msg)])

        @property
        def _llm_type(self):
            return "gemini"

    groq_primary = FailingGroqModel()
    gemini_fallback = WorkingGeminiModel()

    # Monkeypatch get_llm to return primary.with_fallbacks([fallback])
    monkeypatch.setattr(
        providers,
        "get_llm",
        lambda *args, **kwargs: groq_primary.with_fallbacks([gemini_fallback]),
    )

    # Perform query
    res = client.post(
        "/query",
        headers=headers,
        json={"question": "How is deployment performed?", "mode": "standard"},
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert "Deployment is handled via GitHub Actions" in data["answer"]
    assert len(data["citations"]) > 0

    # Verify query_logs recorded provider as 'gemini'
    log_id = data["query_log_id"]
    log = db_session.query(QueryLog).filter(QueryLog.id == log_id).first()
    assert log is not None
    assert log.provider == "gemini"


def test_response_cache_user_isolation(client):
    """User B never receives User A's cached answer; keys depend on user_id."""
    token_a, user_a_id, org_id = _register(client, "user_a_cache@corp.local", org_name="Isolation Org")
    token_b, user_b_id, _ = _register(client, "user_b_cache@corp.local", org_name="Isolation Org")

    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # Upload document visible to org
    client.post(
        "/documents",
        headers=headers_a,
        files={"file": ("memo.txt", b"Company annual holiday will be on December 24.", "text/plain")},
        data={"title": "Holiday Memo", "visibility": "org"},
    )

    question = "When is the company annual holiday?"

    # User A runs query -> cache_hit=False
    res_a1 = client.post(
        "/query",
        headers=headers_a,
        json={"question": question, "mode": "standard"},
    )
    assert res_a1.status_code == 200
    assert res_a1.json()["cache_hit"] is False

    # User A runs query again -> cache_hit=True
    res_a2 = client.post(
        "/query",
        headers=headers_a,
        json={"question": question, "mode": "standard"},
    )
    assert res_a2.status_code == 200
    assert res_a2.json()["cache_hit"] is True

    # User B runs the exact same query -> cache_hit MUST BE False (isolated per user_id)
    res_b1 = client.post(
        "/query",
        headers=headers_b,
        json={"question": question, "mode": "standard"},
    )
    assert res_b1.status_code == 200
    assert res_b1.json()["cache_hit"] is False

    # User B runs query again -> cache_hit=True (for User B's own cache)
    res_b2 = client.post(
        "/query",
        headers=headers_b,
        json={"question": question, "mode": "standard"},
    )
    assert res_b2.status_code == 200
    assert res_b2.json()["cache_hit"] is True


def test_cache_invalidation_on_upload_and_delete(client, db_session):
    """Cache invalidates when corpus_version bumps upon document upload and deletion."""
    token, user_id, org_id = _register(client, "invalidation_user@corp.local", org_name="Invalidation Org")
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Initial document upload
    doc_res = client.post(
        "/documents",
        headers=headers,
        files={"file": ("v1.txt", b"Version 1 specification of the architecture.", "text/plain")},
        data={"title": "V1 Spec", "visibility": "org"},
    )
    assert doc_res.status_code in (200, 201)
    doc_id = doc_res.json()["id"]

    q = "What is the architecture specification?"

    # Query 1 -> cache_hit=False
    q1 = client.post("/query", headers=headers, json={"question": q, "mode": "standard"})
    assert q1.status_code == 200
    assert q1.json()["cache_hit"] is False

    # Query 2 -> cache_hit=True
    q2 = client.post("/query", headers=headers, json={"question": q, "mode": "standard"})
    assert q2.status_code == 200
    assert q2.json()["cache_hit"] is True

    # 2. Upload a new document -> bumps corpus_version and invalidates cache
    upload_res2 = client.post(
        "/documents",
        headers=headers,
        files={"file": ("v2.txt", b"Version 2 adds microservices routing.", "text/plain")},
        data={"title": "V2 Spec", "visibility": "org"},
    )
    assert upload_res2.status_code in (200, 201)
    doc2_id = upload_res2.json()["id"]

    # Query 3 -> MUST BE cache_hit=False (invalidated by upload)
    q3 = client.post("/query", headers=headers, json={"question": q, "mode": "standard"})
    assert q3.status_code == 200
    assert q3.json()["cache_hit"] is False

    # Query 4 -> cache_hit=True
    q4 = client.post("/query", headers=headers, json={"question": q, "mode": "standard"})
    assert q4.status_code == 200
    assert q4.json()["cache_hit"] is True

    # 3. Delete document -> bumps corpus_version and invalidates cache
    del_res = client.delete(f"/documents/{doc2_id}", headers=headers)
    assert del_res.status_code == 200

    # Query 5 -> MUST BE cache_hit=False (invalidated by delete)
    q5 = client.post("/query", headers=headers, json={"question": q, "mode": "standard"})
    assert q5.status_code == 200
    assert q5.json()["cache_hit"] is False
