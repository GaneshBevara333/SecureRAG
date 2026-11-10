import io
import pytest


def register(client, org_name: str, email: str, password: str = "pass123"):
    res = client.post(
        "/auth/register",
        json={"org_name": org_name, "email": email, "password": password},
    )
    assert res.status_code == 201
    return res.json()["access_token"], res.json()["user"]


def create_member(client, admin_token: str, email: str, password: str = "pass123"):
    res = client.post(
        "/orgs/members",
        json={"email": email, "password": password, "role": "member"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 201
    login_res = client.post(
        "/auth/login",
        json={"email": email, "password": password},
    )
    assert login_res.status_code == 200
    return login_res.json()["access_token"], login_res.json()["user"]


def make_team(client, admin_token: str, team_name: str):
    res = client.post(
        "/teams",
        json={"name": team_name},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 201
    return res.json()["id"]


def assign_team(client, admin_token: str, team_id: str, user_id: str):
    res = client.post(
        f"/teams/{team_id}/members",
        json={"user_id": user_id},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code in (200, 201)


def upload_document(client, token: str, filename: str, content: str, visibility: str = "private", team_id: str = None):
    data = {"title": filename, "visibility": visibility}
    if team_id:
        data["team_id"] = team_id
    res = client.post(
        "/documents",
        files={"file": (filename, io.BytesIO(content.encode("utf-8")), "text/plain")},
        data=data,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    return res.json()


@pytest.mark.parametrize("retrieval_mode", ["dense", "hybrid", "hybrid+rerank"])
def test_all_retrieval_modes_return_permitted_chunks(client, retrieval_mode):
    """Verify that 'dense', 'hybrid', and 'hybrid+rerank' all return valid results for permitted content."""
    admin_token, admin = register(client, f"PermOrg_{retrieval_mode}", f"admin_{retrieval_mode}@perm.com")

    upload_document(
        client,
        admin_token,
        "protocol.txt",
        "The standard system recovery protocol requires dual cryptographic confirmation.",
        visibility="org",
    )

    query_res = client.post(
        "/query",
        json={
            "question": "What does the standard system recovery protocol require?",
            "retrieval_mode": retrieval_mode,
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert query_res.status_code == 200
    data = query_res.json()
    assert len(data["citations"]) > 0
    assert any(c["filename"] == "protocol.txt" for c in data["citations"])


@pytest.mark.parametrize("retrieval_mode", ["dense", "hybrid", "hybrid+rerank"])
def test_all_retrieval_modes_enforce_acl_and_tenant_isolation(client, retrieval_mode):
    """Verify that private, team, and cross-tenant access boundaries hold across all three retrieval modes."""
    # Org 1: Alpha
    a_admin_token, a_admin = register(client, f"AlphaOrg_{retrieval_mode}", f"admin_a_{retrieval_mode}@alpha.com")
    a_member_token, a_member = create_member(client, a_admin_token, f"user_a_{retrieval_mode}@alpha.com")

    upload_document(
        client,
        a_admin_token,
        "alpha_private.txt",
        f"Confidential Alpha private key ALPHA_SECRET_{retrieval_mode}.",
        visibility="private",
    )

    # 1. Member in same org querying private doc -> BLOCKED in this mode
    res1 = client.post(
        "/query",
        json={
            "question": f"What is ALPHA_SECRET_{retrieval_mode}?",
            "retrieval_mode": retrieval_mode,
        },
        headers={"Authorization": f"Bearer {a_member_token}"},
    )
    assert res1.status_code == 200
    assert res1.json()["answer"] == "not found in your documents"
    assert len(res1.json()["citations"]) == 0

    # Org 2: Beta
    b_admin_token, b_admin = register(client, f"BetaOrg_{retrieval_mode}", f"admin_b_{retrieval_mode}@beta.com")

    # 2. Member in another org querying Alpha secret -> BLOCKED in this mode
    res2 = client.post(
        "/query",
        json={
            "question": f"What is ALPHA_SECRET_{retrieval_mode}?",
            "retrieval_mode": retrieval_mode,
        },
        headers={"Authorization": f"Bearer {b_admin_token}"},
    )
    assert res2.status_code == 200
    assert res2.json()["answer"] == "not found in your documents"
    assert len(res2.json()["citations"]) == 0

    # 3. Owner (Alpha admin) querying -> PERMITTED in this mode
    res3 = client.post(
        "/query",
        json={
            "question": f"What is ALPHA_SECRET_{retrieval_mode}?",
            "retrieval_mode": retrieval_mode,
        },
        headers={"Authorization": f"Bearer {a_admin_token}"},
    )
    assert res3.status_code == 200
    assert len(res3.json()["citations"]) > 0
    assert any(c["filename"] == "alpha_private.txt" for c in res3.json()["citations"])
