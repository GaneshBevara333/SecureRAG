import io
import pytest


def register_user(client, org_name: str, email: str, password: str = "password123"):
    res = client.post(
        "/auth/register",
        json={"org_name": org_name, "email": email, "password": password},
    )
    assert res.status_code == 201
    return res.json()["access_token"], res.json()["user"]


def add_member(client, admin_token: str, email: str, password: str = "password123"):
    res = client.post(
        "/orgs/members",
        json={"email": email, "password": password, "role": "member"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 201
    # Login as the new member
    login_res = client.post(
        "/auth/login",
        json={"email": email, "password": password},
    )
    assert login_res.status_code == 200
    return login_res.json()["access_token"], login_res.json()["user"]


def create_team(client, admin_token: str, team_name: str):
    res = client.post(
        "/teams",
        json={"name": team_name},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 201
    return res.json()["id"]


def add_to_team(client, admin_token: str, team_id: str, user_id: str):
    res = client.post(
        f"/teams/{team_id}/members",
        json={"user_id": user_id},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code in (200, 201)


def upload_doc(client, token: str, filename: str, content: str, visibility: str = "private", team_id: str = None):
    data = {"title": filename, "visibility": visibility}
    if team_id:
        data["team_id"] = team_id
    res = client.post(
        "/documents",
        files={"file": (filename, io.BytesIO(content.encode("utf-8")), "text/plain")},
        data=data,
        headers={"Authorization": f"Bearer {token}"},
    )
    return res


def test_upload_team_validation(client):
    admin_token, admin = register_user(client, "Acme", "admin@acme.com")
    member_token, member = add_member(client, admin_token, "bob@acme.com")
    team_id = create_team(client, admin_token, "RedTeam")

    # 1. Upload visibility="team" without team_id -> 400
    res1 = upload_doc(client, member_token, "doc1.txt", "Some content", visibility="team")
    assert res1.status_code == 400
    assert "team_id is required" in res1.json()["detail"].lower()

    # 2. Upload with team_id user is NOT in -> 400
    res2 = upload_doc(client, member_token, "doc2.txt", "Some content", visibility="team", team_id=team_id)
    assert res2.status_code == 400
    assert "not a member" in res2.json()["detail"].lower()

    # 3. Add Bob to RedTeam, then upload succeeds
    add_to_team(client, admin_token, team_id, member["id"])
    
    # Re-login Bob to get fresh token with updated team_ids
    login_res = client.post("/auth/login", json={"email": "bob@acme.com", "password": "password123"})
    bob_updated_token = login_res.json()["access_token"]

    res3 = upload_doc(client, bob_updated_token, "doc3.txt", "Red team secret plan", visibility="team", team_id=team_id)
    assert res3.status_code == 200
    assert res3.json()["visibility"] == "team"


def test_document_listing_and_404_acl(client):
    admin_token, admin = register_user(client, "Cyberdyne", "admin@cyber.com")
    alice_token, alice = add_member(client, admin_token, "alice@cyber.com")
    bob_token, bob = add_member(client, admin_token, "bob@cyber.com")
    team_id = create_team(client, admin_token, "SkynetOps")
    add_to_team(client, admin_token, team_id, alice["id"])

    # Re-login Alice to get token with team_id
    alice_token = client.post("/auth/login", json={"email": "alice@cyber.com", "password": "password123"}).json()["access_token"]

    # 1. Alice uploads private doc
    alice_priv = upload_doc(client, alice_token, "alice_priv.txt", "Alice private notes", visibility="private").json()

    # 2. Alice uploads team doc
    alice_team = upload_doc(client, alice_token, "alice_team.txt", "Skynet operations protocol", visibility="team", team_id=team_id).json()

    # 3. Alice uploads org doc
    alice_org = upload_doc(client, alice_token, "alice_org.txt", "Company cafeteria rules", visibility="org").json()

    # Bob's listing: should see only org doc
    bob_list = client.get("/documents", headers={"Authorization": f"Bearer {bob_token}"}).json()
    bob_doc_ids = [d["id"] for d in bob_list]
    assert alice_org["id"] in bob_doc_ids
    assert alice_priv["id"] not in bob_doc_ids
    assert alice_team["id"] not in bob_doc_ids

    # Alice's listing: should see private, team, and org
    alice_list = client.get("/documents", headers={"Authorization": f"Bearer {alice_token}"}).json()
    alice_doc_ids = [d["id"] for d in alice_list]
    assert alice_priv["id"] in alice_doc_ids
    assert alice_team["id"] in alice_doc_ids
    assert alice_org["id"] in alice_doc_ids

    # Admin's listing: should see all in org
    admin_list = client.get("/documents", headers={"Authorization": f"Bearer {admin_token}"}).json()
    admin_doc_ids = [d["id"] for d in admin_list]
    assert alice_priv["id"] in admin_doc_ids
    assert alice_team["id"] in admin_doc_ids
    assert alice_org["id"] in admin_doc_ids

    # Direct GET/DELETE by Bob on inaccessible docs returns 404 (never 403)
    get_priv_resp = client.get(f"/documents/{alice_priv['id']}", headers={"Authorization": f"Bearer {bob_token}"})
    assert get_priv_resp.status_code == 404

    del_priv_resp = client.delete(f"/documents/{alice_priv['id']}", headers={"Authorization": f"Bearer {bob_token}"})
    assert del_priv_resp.status_code == 404

    get_team_resp = client.get(f"/documents/{alice_team['id']}", headers={"Authorization": f"Bearer {bob_token}"})
    assert get_team_resp.status_code == 404

    del_team_resp = client.delete(f"/documents/{alice_team['id']}", headers={"Authorization": f"Bearer {bob_token}"})
    assert del_team_resp.status_code == 404


def test_retrieval_acl_enforcement(client):
    admin_token, admin = register_user(client, "OmniCorp", "admin@omni.com")
    charlie_token, charlie = add_member(client, admin_token, "charlie@omni.com")
    david_token, david = add_member(client, admin_token, "david@omni.com")
    team_alpha = create_team(client, admin_token, "AlphaTeam")
    add_to_team(client, admin_token, team_alpha, charlie["id"])

    charlie_token = client.post("/auth/login", json={"email": "charlie@omni.com", "password": "password123"}).json()["access_token"]

    # Charlie uploads private doc with secret marker
    upload_doc(
        client,
        charlie_token,
        "charlie_confidential.txt",
        "UniqueSecretCode CHARLIE_PRIVATE_MARKER_9988 is stored in the vault.",
        visibility="private",
    )

    # Charlie uploads team doc with secret marker
    upload_doc(
        client,
        charlie_token,
        "team_alpha_secret.txt",
        "Alpha team classified project ALPHA_TEAM_MARKER_7744 launch date.",
        visibility="team",
        team_id=team_alpha,
    )

    # Charlie uploads org doc with secret marker
    upload_doc(
        client,
        charlie_token,
        "omni_public.txt",
        "OmniCorp public handbook OMNI_ORG_MARKER_1122 for all employees.",
        visibility="org",
    )

    # 1. David queries for Charlie's private marker -> Should NOT be retrieved
    q1 = client.post(
        "/query",
        json={"question": "What is CHARLIE_PRIVATE_MARKER_9988?"},
        headers={"Authorization": f"Bearer {david_token}"},
    )
    assert q1.status_code == 200
    assert q1.json()["answer"] == "not found in your documents"
    assert len(q1.json()["citations"]) == 0

    # 2. David queries for Alpha team marker -> Should NOT be retrieved
    q2 = client.post(
        "/query",
        json={"question": "What is ALPHA_TEAM_MARKER_7744?"},
        headers={"Authorization": f"Bearer {david_token}"},
    )
    assert q2.status_code == 200
    assert q2.json()["answer"] == "not found in your documents"
    assert len(q2.json()["citations"]) == 0

    # 3. David queries for Org public marker -> Accessible and retrieved
    q3 = client.post(
        "/query",
        json={"question": "What is OMNI_ORG_MARKER_1122?"},
        headers={"Authorization": f"Bearer {david_token}"},
    )
    assert q3.status_code == 200
    assert len(q3.json()["citations"]) > 0
    assert q3.json()["citations"][0]["filename"] == "omni_public.txt"

    # 4. Charlie queries for his own private marker -> Successfully retrieved
    q4 = client.post(
        "/query",
        json={"question": "What is CHARLIE_PRIVATE_MARKER_9988?"},
        headers={"Authorization": f"Bearer {charlie_token}"},
    )
    assert q4.status_code == 200
    assert len(q4.json()["citations"]) > 0
    assert any(c["filename"] == "charlie_confidential.txt" for c in q4.json()["citations"])

    # 5. Charlie queries for Alpha team marker -> Successfully retrieved
    q5 = client.post(
        "/query",
        json={"question": "What is ALPHA_TEAM_MARKER_7744?"},
        headers={"Authorization": f"Bearer {charlie_token}"},
    )
    assert q5.status_code == 200
    assert len(q5.json()["citations"]) > 0
    assert any(c["filename"] == "team_alpha_secret.txt" for c in q5.json()["citations"])


def test_cross_tenant_isolation(client):
    # Tenant 1: Initech
    t1_admin_token, _ = register_user(client, "Initech", "admin@initech.com")
    doc_t1 = upload_doc(
        client,
        t1_admin_token,
        "tps_report.txt",
        "Initech special secret INITECH_SECRET_KEY_5544.",
        visibility="org",
    ).json()

    # Tenant 2: PiedPiper
    t2_admin_token, _ = register_user(client, "PiedPiper", "admin@piedpiper.com")

    # 1. PiedPiper queries for Initech secret -> Must NOT find anything
    query_resp = client.post(
        "/query",
        json={"question": "What is INITECH_SECRET_KEY_5544?"},
        headers={"Authorization": f"Bearer {t2_admin_token}"},
    )
    assert query_resp.status_code == 200
    assert query_resp.json()["answer"] == "not found in your documents"
    assert len(query_resp.json()["citations"]) == 0

    # 2. PiedPiper tries direct GET on Initech document id -> 404
    get_resp = client.get(
        f"/documents/{doc_t1['id']}",
        headers={"Authorization": f"Bearer {t2_admin_token}"},
    )
    assert get_resp.status_code == 404

    # 3. PiedPiper tries direct DELETE on Initech document id -> 404
    del_resp = client.delete(
        f"/documents/{doc_t1['id']}",
        headers={"Authorization": f"Bearer {t2_admin_token}"},
    )
    assert del_resp.status_code == 404
