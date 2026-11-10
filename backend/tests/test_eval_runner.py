import pytest
from app.auth.rate_limit import rate_limiter
from app.evals.judge import judge_service
from app.db.models import EvalRun, EvalResult, EvalCase


def _setup_org_with_docs_and_cases(client):
    """Helper to set up an admin user, sample documents, and eval cases."""
    rate_limiter.reset()
    reg = client.post(
        "/auth/register",
        json={"org_name": "Eval Corp", "email": "eval_chief@corp.local", "password": "password123"},
    )
    assert reg.status_code == 201
    admin_token = reg.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # Invite member
    m_reg = client.post(
        "/orgs/members",
        headers=admin_headers,
        json={"email": "eval_worker@corp.local", "password": "password123", "role": "member"},
    )
    assert m_reg.status_code == 201
    m_login = client.post("/auth/login", json={"email": "eval_worker@corp.local", "password": "password123"})
    member_token = m_login.json()["access_token"]
    member_headers = {"Authorization": f"Bearer {member_token}"}

    # Upload 2 documents
    doc1_resp = client.post(
        "/documents",
        headers=admin_headers,
        files={"file": ("postgres_backup.txt", b"Database backups run automatically at midnight UTC daily to S3 bucket secure-backups.", "text/plain")},
        data={"title": "Postgres Backup Policy", "visibility": "org"},
    )
    assert doc1_resp.status_code in (200, 201)
    doc1_id = doc1_resp.json()["id"]

    doc2_resp = client.post(
        "/documents",
        headers=admin_headers,
        files={"file": ("oncall_guide.txt", b"The primary oncall engineer is paged through PagerDuty with an escalation timeout of 10 minutes.", "text/plain")},
        data={"title": "Oncall Guide", "visibility": "org"},
    )
    assert doc2_resp.status_code in (200, 201)
    doc2_id = doc2_resp.json()["id"]

    # Create 2 eval cases
    c1 = client.post(
        "/evals/cases",
        headers=admin_headers,
        json={
            "question": "When do database backups run?",
            "expected_doc_id": doc1_id,
            "expected_answer": "At midnight UTC daily.",
            "source": "manual",
        },
    )
    assert c1.status_code == 201

    c2 = client.post(
        "/evals/cases",
        headers=admin_headers,
        json={
            "question": "What is the oncall escalation timeout?",
            "expected_doc_id": doc2_id,
            "expected_answer": "10 minutes via PagerDuty.",
            "source": "manual",
        },
    )
    assert c2.status_code == 201

    return admin_headers, member_headers, [doc1_id, doc2_id]


def test_eval_runner_admin_only(client):
    """Member cannot trigger or view eval runs (returns 403)."""
    admin_headers, member_headers, _ = _setup_org_with_docs_and_cases(client)

    run_attempt = client.post(
        "/evals/run",
        headers=member_headers,
        json={"label": "unauthorized-run", "config": {"retrieval_mode": "dense"}},
    )
    assert run_attempt.status_code == 403

    list_attempt = client.get("/evals/runs", headers=member_headers)
    assert list_attempt.status_code == 403


def test_eval_runner_caching_zero_new_calls(client):
    """Re-running an unchanged eval must make zero new judge calls (judge cache works)."""
    admin_headers, _, _ = _setup_org_with_docs_and_cases(client)
    judge_service.reset_cache()

    # First run: judge service computes scores and populates cache
    initial_calls = judge_service.call_count
    run1 = client.post(
        "/evals/run",
        headers=admin_headers,
        json={"label": "run-initial", "config": {"retrieval_mode": "hybrid"}},
    )
    assert run1.status_code == 201
    calls_after_first = judge_service.call_count
    assert calls_after_first > initial_calls, "Judge should have been called on first run"

    # Second run with exact same cases & answers: must make zero new judge calls
    run2 = client.post(
        "/evals/run",
        headers=admin_headers,
        json={"label": "run-cached", "config": {"retrieval_mode": "hybrid"}},
    )
    assert run2.status_code == 201
    calls_after_second = judge_service.call_count
    assert calls_after_second == calls_after_first, "Re-running unchanged eval made new judge calls!"
    assert judge_service.cache_hits > 0


def test_eval_runner_three_retrieval_modes(client, db_session):
    """Run dense, hybrid, and hybrid+rerank and assert three distinct result rows are created."""
    admin_headers, _, _ = _setup_org_with_docs_and_cases(client)

    modes = ["dense", "hybrid", "hybrid+rerank"]
    created_runs = []

    for mode in modes:
        res = client.post(
            "/evals/run",
            headers=admin_headers,
            json={"label": f"eval-{mode}", "config": {"retrieval_mode": mode}},
        )
        assert res.status_code == 201, res.text
        data = res.json()
        assert data["label"] == f"eval-{mode}"
        assert data["config"]["retrieval_mode"] == mode
        assert 0.0 <= data["hit_at_k"] <= 1.0
        assert 0.0 <= data["mrr"] <= 1.0
        assert 0.0 <= data["faithfulness"] <= 1.0
        assert data["p50_ms"] >= 0.0
        assert data["p95_ms"] >= 0.0
        created_runs.append(data)

    assert len(created_runs) == 3

    # Verify listing of runs via GET /evals/runs
    list_res = client.get("/evals/runs", headers=admin_headers)
    assert list_res.status_code == 200
    runs = list_res.json()
    assert len(runs) >= 3

    # Verify run detail includes per-case results
    detail_res = client.get(f"/evals/runs/{created_runs[0]['id']}", headers=admin_headers)
    assert detail_res.status_code == 200
    detail = detail_res.json()
    assert "results" in detail
    assert len(detail["results"]) == 2
    for r in detail["results"]:
        assert r["faithfulness"] >= 0.0
        assert r["latency_ms"] >= 0.0


def test_judge_retry_on_429(monkeypatch):
    """Test that judge service retries on simulated 429 errors."""
    judge_service.reset_cache()

    attempts = {"count": 0}

    class FlakyChatModel:
        def invoke(self, messages):
            attempts["count"] += 1
            if attempts["count"] < 3:
                raise Exception("429 Too Many Requests: Rate limit exceeded")
            class Resp:
                content = "1.0"
            return Resp()

    from app.evals import judge
    monkeypatch.setattr(judge, "get_llm", lambda: FlakyChatModel())

    score = judge_service.evaluate_faithfulness(
        question="What is X?",
        answer="X is 42.",
        context="X is 42.",
        initial_backoff=0.01,
    )
    assert score == 1.0
    assert attempts["count"] == 3
