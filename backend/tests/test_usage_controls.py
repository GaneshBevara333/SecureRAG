import pytest
from app.db.models import QueryLog, Organization, User
from app.auth.rate_limit import rate_limiter


def _register_user(client, email: str, org_name: str = "Test Org", role: str = "member"):
    res = client.post(
        "/auth/register",
        json={"org_name": org_name, "email": email, "password": "securepassword123"},
    )
    assert res.status_code == 201, res.text
    token = res.json()["access_token"]
    user_id = res.json()["user"]["id"]
    org_id = res.json()["user"]["org_id"]
    return token, user_id, org_id


def test_api_key_creation_and_usage(client, db_session):
    """Test API key creation (shown once), listing, usage for /query, and revocation."""
    rate_limiter.reset()
    token, user_id, org_id = _register_user(client, "apikey_tester@example.com")
    auth_header = {"Authorization": f"Bearer {token}"}

    # 1. Create an API key
    res = client.post("/api-keys", headers=auth_header)
    assert res.status_code == 201
    key_data = res.json()
    assert "id" in key_data
    assert "prefix" in key_data
    assert "api_key" in key_data
    raw_api_key = key_data["api_key"]
    key_id = key_data["id"]
    assert raw_api_key.startswith("sec_")

    # 2. List API keys (raw key must NOT be present in listing)
    list_res = client.get("/api-keys", headers=auth_header)
    assert list_res.status_code == 200
    keys = list_res.json()
    assert len(keys) == 1
    assert keys[0]["id"] == key_id
    assert keys[0]["prefix"] == key_data["prefix"]
    assert keys[0]["revoked_at"] is None
    assert "api_key" not in keys[0]

    # 3. Query using X-API-Key header
    q_res = client.post(
        "/query",
        headers={"X-API-Key": raw_api_key},
        json={"question": "What is the security procedure?", "mode": "standard"},
    )
    assert q_res.status_code == 200
    assert "answer" in q_res.json()
    assert "citations" in q_res.json()

    # 4. Query using Authorization: Bearer <api_key>
    bearer_q_res = client.post(
        "/query",
        headers={"Authorization": f"Bearer {raw_api_key}"},
        json={"question": "What is the policy?", "mode": "standard"},
    )
    assert bearer_q_res.status_code == 200

    # 5. Revoke the API key
    del_res = client.delete(f"/api-keys/{key_id}", headers=auth_header)
    assert del_res.status_code == 200
    assert del_res.json()["status"] == "revoked"

    # 6. Revoked API key must be rejected on /query with 401
    revoked_res = client.post(
        "/query",
        headers={"X-API-Key": raw_api_key},
        json={"question": "What is the policy now?", "mode": "standard"},
    )
    assert revoked_res.status_code == 401
    assert "revoked" in revoked_res.json()["detail"].lower()

    # 7. Non-existent API key rejected with 401
    fake_res = client.post(
        "/query",
        headers={"X-API-Key": "sec_nonexistentkey123456789"},
        json={"question": "Any document?", "mode": "standard"},
    )
    assert fake_res.status_code == 401
    assert "invalid" in fake_res.json()["detail"].lower()


def test_api_key_cross_user_isolation(client):
    """A user cannot delete another user's API key."""
    rate_limiter.reset()
    token1, _, _ = _register_user(client, "user1_keys@example.com", org_name="Org 1")
    token2, _, _ = _register_user(client, "user2_keys@example.com", org_name="Org 2")

    # User 1 creates key
    k_res = client.post("/api-keys", headers={"Authorization": f"Bearer {token1}"})
    key_id = k_res.json()["id"]

    # User 2 attempts to delete User 1's key -> 404
    del_res = client.delete(f"/api-keys/{key_id}", headers={"Authorization": f"Bearer {token2}"})
    assert del_res.status_code == 404


def test_rate_limiting_per_user_returns_429(client, monkeypatch):
    """Exceeding the per-user rate limit returns 429 with Retry-After header."""
    rate_limiter.reset()
    # Set small limit of 3 requests per minute for testing
    rate_limiter._custom_rpm = 3

    token_a, user_id_a, _ = _register_user(client, "rate_a@example.com")
    token_b, user_id_b, _ = _register_user(client, "rate_b@example.com")

    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # First 3 requests for User A succeed
    for i in range(3):
        res = client.post(
            "/query",
            headers=headers_a,
            json={"question": f"Test question {i}?", "mode": "standard"},
        )
        assert res.status_code == 200, f"Request {i} failed: {res.text}"

    # 4th request for User A must return 429 Too Many Requests
    blocked_res = client.post(
        "/query",
        headers=headers_a,
        json={"question": "Blocked question?", "mode": "standard"},
    )
    assert blocked_res.status_code == 429
    assert "Retry-After" in blocked_res.headers
    retry_after = int(blocked_res.headers["Retry-After"])
    assert retry_after >= 1
    assert "detail" in blocked_res.json()

    # User B should NOT be rate limited (rate limiting is strictly per-user)
    res_b = client.post(
        "/query",
        headers=headers_b,
        json={"question": "User B question?", "mode": "standard"},
    )
    assert res_b.status_code == 200

    # Reset rate limiter
    rate_limiter.reset()
    rate_limiter._custom_rpm = None


def test_query_logs_and_token_counts(client, db_session):
    """Every query logs prompt/completion tokens and metadata in query_logs."""
    rate_limiter.reset()
    token, user_id, org_id = _register_user(client, "logger_tester@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    # Upload a document first so chunks exist
    upload_res = client.post(
        "/documents",
        headers=headers,
        files={"file": ("guide.txt", b"Incident response protocol: contact devops immediately.", "text/plain")},
        data={"title": "Incident Protocol", "visibility": "org"},
    )
    assert upload_res.status_code in (200, 201)

    # Perform query
    q_res = client.post(
        "/query",
        headers=headers,
        json={"question": "What is the incident protocol?", "mode": "standard"},
    )
    assert q_res.status_code == 200

    # Verify query log in database
    logs = db_session.query(QueryLog).filter(QueryLog.user_id == user_id).all()
    assert len(logs) == 1
    log = logs[0]
    assert log.org_id == org_id
    assert log.user_id == user_id
    assert log.question == "What is the incident protocol?"
    assert log.answer != ""
    assert log.prompt_tokens > 0
    assert log.completion_tokens > 0
    assert log.latency_ms >= 0.0
    assert log.mode == "standard"
    assert len(log.retrieved_chunk_ids) > 0


def test_admin_usage_endpoint(client, db_session):
    """Admin usage endpoint returns token counts, latency stats, and per-user breakdown."""
    rate_limiter.reset()
    # Register admin
    admin_token, admin_id, org_id = _register_user(client, "org_admin@example.com")
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # Admin invites member
    member_res = client.post(
        "/orgs/members",
        headers=admin_headers,
        json={"email": "org_member@example.com", "password": "password123", "role": "member"},
    )
    assert member_res.status_code == 201

    # Login as member
    m_login = client.post(
        "/auth/login",
        json={"email": "org_member@example.com", "password": "password123"},
    )
    member_token = m_login.json()["access_token"]
    member_headers = {"Authorization": f"Bearer {member_token}"}

    # Run query as admin
    client.post(
        "/query",
        headers=admin_headers,
        json={"question": "Admin test query?", "mode": "standard"},
    )

    # Run query as member
    client.post(
        "/query",
        headers=member_headers,
        json={"question": "Member test query?", "mode": "standard"},
    )

    # Admin requests usage stats
    usage_res = client.get("/admin/usage", headers=admin_headers)
    assert usage_res.status_code == 200
    data = usage_res.json()
    assert data["total_queries"] >= 2
    assert data["total_prompt_tokens"] > 0
    assert data["total_completion_tokens"] > 0
    assert data["total_tokens"] == data["total_prompt_tokens"] + data["total_completion_tokens"]
    assert data["avg_latency_ms"] >= 0.0
    assert "per_user_usage" in data
    assert len(data["per_user_usage"]) >= 2

    # Member requests usage stats -> 403 Forbidden
    forbidden_res = client.get("/admin/usage", headers=member_headers)
    assert forbidden_res.status_code == 403
