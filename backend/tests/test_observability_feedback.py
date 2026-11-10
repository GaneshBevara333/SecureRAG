import pytest
from app.auth.rate_limit import rate_limiter
from app.db.models import QueryLog, Feedback, EvalCase


def _register(client, email: str, org_name: str = "Test Org", role: str = "admin"):
    res = client.post(
        "/auth/register",
        json={"org_name": org_name, "email": email, "password": "securepassword123"},
    )
    assert res.status_code == 201, res.text
    return res.json()["access_token"], res.json()["user"]


def _add_member(client, admin_token: str, email: str, role: str = "member"):
    res = client.post(
        "/orgs/members",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"email": email, "password": "password123", "role": role},
    )
    assert res.status_code == 201, res.text
    login_res = client.post("/auth/login", json={"email": email, "password": "password123"})
    assert login_res.status_code == 200
    return login_res.json()["access_token"], res.json()


def test_query_logging_completeness(client, db_session):
    """Verify that every /query is logged with question, answer, chunks, scores, latency, tokens, provider, cache_hit, mode."""
    rate_limiter.reset()
    token, user = _register(client, "logger_check@corp.local")
    headers = {"Authorization": f"Bearer {token}"}

    # Upload test document
    upload_res = client.post(
        "/documents",
        headers=headers,
        files={"file": ("infra.txt", b"Server cluster redundancy operates across 3 primary availability zones.", "text/plain")},
        data={"title": "Infrastructure Guide", "visibility": "org"},
    )
    assert upload_res.status_code in (200, 201)

    # Execute query
    q_res = client.post(
        "/query",
        headers=headers,
        json={"question": "What is the cluster redundancy?", "mode": "standard"},
    )
    assert q_res.status_code == 200
    data = q_res.json()
    assert "query_log_id" in data
    log_id = data["query_log_id"]

    # Verify query log in database
    log = db_session.query(QueryLog).filter(QueryLog.id == log_id).first()
    assert log is not None
    assert log.org_id == user["org_id"]
    assert log.user_id == user["id"]
    assert log.question == "What is the cluster redundancy?"
    assert log.answer == data["answer"]
    assert isinstance(log.retrieved_chunk_ids, list)
    assert isinstance(log.scores, list)
    assert log.latency_ms >= 0.0
    assert log.prompt_tokens > 0
    assert log.completion_tokens > 0
    assert log.provider != ""
    assert log.cache_hit is False
    assert log.mode == "standard"


def test_users_cannot_read_others_logs(client):
    """Users can only view their own query logs; other users' logs return 404."""
    rate_limiter.reset()
    admin_token, user_a = _register(client, "user_a_logs@corp.local")
    user_b_token, user_b = _add_member(client, admin_token, "user_b_logs@corp.local")

    headers_a = {"Authorization": f"Bearer {admin_token}"}
    headers_b = {"Authorization": f"Bearer {user_b_token}"}

    # User A runs a query
    res_a = client.post(
        "/query",
        headers=headers_a,
        json={"question": "User A confidential question?", "mode": "standard"},
    )
    log_id_a = res_a.json()["query_log_id"]

    # User A can read own log
    get_a = client.get(f"/query/logs/{log_id_a}", headers=headers_a)
    assert get_a.status_code == 200
    assert get_a.json()["id"] == log_id_a

    # User B cannot read User A's log (returns 404 to avoid leaking existence)
    get_b = client.get(f"/query/logs/{log_id_a}", headers=headers_b)
    assert get_b.status_code == 404

    # User B list of logs does not contain User A's log
    list_b = client.get("/query/logs", headers=headers_b)
    assert list_b.status_code == 200
    assert all(item["id"] != log_id_a for item in list_b.json())


def test_feedback_own_logs_only_and_rating_validation(client):
    """POST /feedback only succeeds on user's own logs (404 on others) and validates rating (+1/-1)."""
    rate_limiter.reset()
    admin_token, user_a = _register(client, "fb_user_a@corp.local")
    user_b_token, user_b = _add_member(client, admin_token, "fb_user_b@corp.local")

    headers_a = {"Authorization": f"Bearer {admin_token}"}
    headers_b = {"Authorization": f"Bearer {user_b_token}"}

    # User A runs a query
    res_a = client.post(
        "/query",
        headers=headers_a,
        json={"question": "How to deploy?", "mode": "standard"},
    )
    log_id_a = res_a.json()["query_log_id"]

    # User B cannot rate User A's query log -> 404
    fb_fail = client.post(
        "/feedback",
        headers=headers_b,
        json={"query_log_id": log_id_a, "rating": 1, "comment": "Good job"},
    )
    assert fb_fail.status_code == 404

    # Invalid rating rejected (must be +1 or -1)
    invalid_fb = client.post(
        "/feedback",
        headers=headers_a,
        json={"query_log_id": log_id_a, "rating": 5, "comment": "Invalid"},
    )
    assert invalid_fb.status_code == 400

    # User A can rate own query log with thumbs down (-1) and optional comment
    fb_success = client.post(
        "/feedback",
        headers=headers_a,
        json={"query_log_id": log_id_a, "rating": -1, "comment": "Missing detail on CI/CD"},
    )
    assert fb_success.status_code == 201
    fb_data = fb_success.json()
    assert fb_data["rating"] == -1
    assert fb_data["comment"] == "Missing detail on CI/CD"
    assert fb_data["query_log_id"] == log_id_a
    fb_id = fb_data["id"]

    # User B cannot read User A's feedback -> 404
    read_fb_b = client.get(f"/feedback/{fb_id}", headers=headers_b)
    assert read_fb_b.status_code == 404

    # User A can read own feedback
    read_fb_a = client.get(f"/feedback/{fb_id}", headers=headers_a)
    assert read_fb_a.status_code == 200
    assert read_fb_a.json()["id"] == fb_id


def test_admin_eval_case_promotion(client, db_session):
    """Admin can promote thumbs-down logs into eval_cases; members receive 403; non-thumbs-down rejected with 400."""
    rate_limiter.reset()
    admin_token, admin = _register(client, "eval_admin@corp.local")
    member_token, member = _add_member(client, admin_token, "eval_member@corp.local")

    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    member_headers = {"Authorization": f"Bearer {member_token}"}

    # Admin runs query 1 and gives thumbs down (-1)
    res_1 = client.post(
        "/query",
        headers=admin_headers,
        json={"question": "Where is the secret key stored?", "mode": "standard"},
    )
    log_id_1 = res_1.json()["query_log_id"]
    client.post(
        "/feedback",
        headers=admin_headers,
        json={"query_log_id": log_id_1, "rating": -1, "comment": "Hallucinated key location"},
    )

    # Admin runs query 2 and gives thumbs up (+1)
    res_2 = client.post(
        "/query",
        headers=admin_headers,
        json={"question": "What is the office address?", "mode": "standard"},
    )
    log_id_2 = res_2.json()["query_log_id"]
    client.post(
        "/feedback",
        headers=admin_headers,
        json={"query_log_id": log_id_2, "rating": 1},
    )

    # 1. Non-admin member cannot promote -> 403 Forbidden
    member_promote = client.post(
        "/evals/promote-feedback",
        headers=member_headers,
        json={"query_log_id": log_id_1},
    )
    assert member_promote.status_code == 403

    # 2. Cannot promote query with thumbs up (+1) -> 400 Bad Request
    thumbs_up_promote = client.post(
        "/evals/promote-feedback",
        headers=admin_headers,
        json={"query_log_id": log_id_2},
    )
    assert thumbs_up_promote.status_code == 400
    assert "thumbs-down" in thumbs_up_promote.json()["detail"].lower()

    # 3. Admin successfully promotes thumbs-down query log into eval_case
    promote_res = client.post(
        "/evals/promote-feedback",
        headers=admin_headers,
        json={
            "query_log_id": log_id_1,
            "expected_doc_id": "doc_sec_keys_001",
            "expected_answer": "Secret keys are stored in AWS KMS.",
        },
    )
    assert promote_res.status_code == 201
    case_data = promote_res.json()
    assert case_data["question"] == "Where is the secret key stored?"
    assert case_data["expected_doc_id"] == "doc_sec_keys_001"
    assert case_data["expected_answer"] == "Secret keys are stored in AWS KMS."
    assert case_data["source"] == "feedback"
    assert case_data["org_id"] == admin["org_id"]

    # 4. Admin lists eval cases
    cases_res = client.get("/evals/cases", headers=admin_headers)
    assert cases_res.status_code == 200
    cases = cases_res.json()
    assert len(cases) >= 1
    assert any(c["id"] == case_data["id"] for c in cases)

    # 5. Member cannot list eval cases -> 403 Forbidden
    member_cases_res = client.get("/evals/cases", headers=member_headers)
    assert member_cases_res.status_code == 403


def test_cross_org_promotion_blocked(client):
    """Admin of Org A cannot promote a query log belonging to Org B."""
    rate_limiter.reset()
    admin_a_token, admin_a = _register(client, "admin_org_a@example.com", org_name="Org A")
    admin_b_token, admin_b = _register(client, "admin_org_b@example.com", org_name="Org B")

    # Org B runs query and rates thumbs down
    res_b = client.post(
        "/query",
        headers={"Authorization": f"Bearer {admin_b_token}"},
        json={"question": "Org B question?", "mode": "standard"},
    )
    log_id_b = res_b.json()["query_log_id"]
    client.post(
        "/feedback",
        headers={"Authorization": f"Bearer {admin_b_token}"},
        json={"query_log_id": log_id_b, "rating": -1},
    )

    # Admin A tries to promote Org B's query log -> 404
    cross_res = client.post(
        "/evals/promote-feedback",
        headers={"Authorization": f"Bearer {admin_a_token}"},
        json={"query_log_id": log_id_b},
    )
    assert cross_res.status_code == 404
