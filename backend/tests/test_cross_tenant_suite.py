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


@pytest.fixture
def two_tenant_setup(client):
    """
    Set up two isolated organizations with admins, members, teams, and documents
    containing unique marker strings.
    """
    # Organization 1: Stark Industries
    stark_admin_token, stark_admin = register(client, "Stark Industries", "tony@stark.com")
    rhodey_token, rhodey = create_member(client, stark_admin_token, "rhodey@stark.com")
    peter_token, peter = create_member(client, stark_admin_token, "peter@stark.com")
    pepper_token, pepper = create_member(client, stark_admin_token, "pepper@stark.com")

    team_warmachine = make_team(client, stark_admin_token, "WarMachine")
    team_interns = make_team(client, stark_admin_token, "Interns")
    assign_team(client, stark_admin_token, team_warmachine, rhodey["id"])
    assign_team(client, stark_admin_token, team_interns, peter["id"])

    # Re-login to get updated JWT tokens containing team IDs
    rhodey_token = client.post("/auth/login", json={"email": "rhodey@stark.com", "password": "pass123"}).json()["access_token"]
    peter_token = client.post("/auth/login", json={"email": "peter@stark.com", "password": "pass123"}).json()["access_token"]

    stark_priv = upload_document(
        client, stark_admin_token, "stark_private.txt",
        "Top Secret Arc Reactor Blueprints MARKER_STARK_PRIVATE_9876 exclusively for Tony.",
        visibility="private",
    )
    stark_team_wm = upload_document(
        client, rhodey_token, "warmachine_specs.txt",
        "Armor telemetry specifications MARKER_STARK_TEAM_WARMACHINE_5432.",
        visibility="team", team_id=team_warmachine,
    )
    stark_team_int = upload_document(
        client, peter_token, "intern_project.txt",
        "Spider-suit web fluid formula MARKER_STARK_TEAM_INTERNS_3321.",
        visibility="team", team_id=team_interns,
    )
    stark_org = upload_document(
        client, stark_admin_token, "stark_handbook.txt",
        "Stark Industries Company Handbook MARKER_STARK_ORG_PUBLIC_1111 for all employees.",
        visibility="org",
    )

    # Organization 2: Wayne Enterprises
    wayne_admin_token, wayne_admin = register(client, "Wayne Enterprises", "bruce@wayne.com")
    lucius_token, lucius = create_member(client, wayne_admin_token, "lucius@wayne.com")
    dick_token, dick = create_member(client, wayne_admin_token, "dick@wayne.com")
    alfred_token, alfred = create_member(client, wayne_admin_token, "alfred@wayne.com")

    team_rnd = make_team(client, wayne_admin_token, "RnD")
    team_titans = make_team(client, wayne_admin_token, "Titans")
    assign_team(client, wayne_admin_token, team_rnd, lucius["id"])
    assign_team(client, wayne_admin_token, team_titans, dick["id"])

    # Re-login
    lucius_token = client.post("/auth/login", json={"email": "lucius@wayne.com", "password": "pass123"}).json()["access_token"]
    dick_token = client.post("/auth/login", json={"email": "dick@wayne.com", "password": "pass123"}).json()["access_token"]

    wayne_priv = upload_document(
        client, wayne_admin_token, "batcave_logs.txt",
        "Classified Batcave entry codes MARKER_WAYNE_PRIVATE_8877.",
        visibility="private",
    )
    wayne_team_rnd = upload_document(
        client, lucius_token, "tumbler_specs.txt",
        "Tumbler reinforced plating designs MARKER_WAYNE_TEAM_RND_6655.",
        visibility="team", team_id=team_rnd,
    )
    wayne_team_titans = upload_document(
        client, dick_token, "titans_mission.txt",
        "Titans tactical coordination MARKER_WAYNE_TEAM_TITANS_4433.",
        visibility="team", team_id=team_titans,
    )
    wayne_org = upload_document(
        client, wayne_admin_token, "wayne_bylaws.txt",
        "Wayne Enterprises corporate bylaws MARKER_WAYNE_ORG_PUBLIC_2222.",
        visibility="org",
    )

    return {
        "stark": {
            "admin_token": stark_admin_token,
            "rhodey_token": rhodey_token,
            "peter_token": peter_token,
            "pepper_token": pepper_token,
            "docs": {
                "private": stark_priv,
                "team_wm": stark_team_wm,
                "team_int": stark_team_int,
                "org": stark_org,
            },
            "markers": {
                "private": "MARKER_STARK_PRIVATE_9876",
                "team_wm": "MARKER_STARK_TEAM_WARMACHINE_5432",
                "team_int": "MARKER_STARK_TEAM_INTERNS_3321",
                "org": "MARKER_STARK_ORG_PUBLIC_1111",
            },
        },
        "wayne": {
            "admin_token": wayne_admin_token,
            "lucius_token": lucius_token,
            "dick_token": dick_token,
            "alfred_token": alfred_token,
            "docs": {
                "private": wayne_priv,
                "team_rnd": wayne_team_rnd,
                "team_titans": wayne_team_titans,
                "org": wayne_org,
            },
            "markers": {
                "private": "MARKER_WAYNE_PRIVATE_8877",
                "team_rnd": "MARKER_WAYNE_TEAM_RND_6655",
                "team_titans": "MARKER_WAYNE_TEAM_TITANS_4433",
                "org": "MARKER_WAYNE_ORG_PUBLIC_2222",
            },
        },
    }


def test_cross_org_retrieval_strictly_blocked(client, two_tenant_setup):
    stark = two_tenant_setup["stark"]
    wayne = two_tenant_setup["wayne"]

    # Every Stark user queries for Wayne's markers -> must NEVER retrieve them
    stark_tokens = [stark["admin_token"], stark["rhodey_token"], stark["peter_token"], stark["pepper_token"]]
    for token in stark_tokens:
        for marker_key, marker_val in wayne["markers"].items():
            res = client.post(
                "/query",
                json={"question": f"What is {marker_val}?"},
                headers={"Authorization": f"Bearer {token}"},
            )
            assert res.status_code == 200
            data = res.json()
            assert data["answer"] == "not found in your documents"
            assert len(data["citations"]) == 0
            # Confirm forbidden marker is never in answer or citations
            assert marker_val not in data["answer"]
            for c in data["citations"]:
                assert marker_val not in str(c)

    # Every Wayne user queries for Stark's markers -> must NEVER retrieve them
    wayne_tokens = [wayne["admin_token"], wayne["lucius_token"], wayne["dick_token"], wayne["alfred_token"]]
    for token in wayne_tokens:
        for marker_key, marker_val in stark["markers"].items():
            res = client.post(
                "/query",
                json={"question": f"What is {marker_val}?"},
                headers={"Authorization": f"Bearer {token}"},
            )
            assert res.status_code == 200
            data = res.json()
            assert data["answer"] == "not found in your documents"
            assert len(data["citations"]) == 0
            assert marker_val not in data["answer"]
            for c in data["citations"]:
                assert marker_val not in str(c)


def test_team_and_private_access_within_org(client, two_tenant_setup):
    stark = two_tenant_setup["stark"]

    # 1. Non-team member (Peter on Interns) queries for WarMachine marker -> BLOCKED
    res_wm_blocked = client.post(
        "/query",
        json={"question": f"What is {stark['markers']['team_wm']}?"},
        headers={"Authorization": f"Bearer {stark['peter_token']}"},
    )
    assert res_wm_blocked.json()["answer"] == "not found in your documents"
    assert len(res_wm_blocked.json()["citations"]) == 0
    assert stark["markers"]["team_wm"] not in res_wm_blocked.json()["answer"]

    # 2. Member without any team (Pepper) queries for Interns marker -> BLOCKED
    res_int_blocked = client.post(
        "/query",
        json={"question": f"What is {stark['markers']['team_int']}?"},
        headers={"Authorization": f"Bearer {stark['pepper_token']}"},
    )
    assert res_int_blocked.json()["answer"] == "not found in your documents"
    assert len(res_int_blocked.json()["citations"]) == 0

    # 3. Regular member (Rhodey) queries for Tony's private doc -> BLOCKED
    res_priv_blocked = client.post(
        "/query",
        json={"question": f"What is {stark['markers']['private']}?"},
        headers={"Authorization": f"Bearer {stark['rhodey_token']}"},
    )
    assert res_priv_blocked.json()["answer"] == "not found in your documents"
    assert len(res_priv_blocked.json()["citations"]) == 0

    # 4. Legitimate access: Rhodey queries WarMachine doc -> SUCCESS
    res_wm_ok = client.post(
        "/query",
        json={"question": f"What is {stark['markers']['team_wm']}?"},
        headers={"Authorization": f"Bearer {stark['rhodey_token']}"},
    )
    assert len(res_wm_ok.json()["citations"]) > 0
    assert any(c["filename"] == "warmachine_specs.txt" for c in res_wm_ok.json()["citations"])

    # 5. Legitimate access: Tony (owner/admin) queries his private doc -> SUCCESS
    res_priv_ok = client.post(
        "/query",
        json={"question": f"What is {stark['markers']['private']}?"},
        headers={"Authorization": f"Bearer {stark['admin_token']}"},
    )
    assert len(res_priv_ok.json()["citations"]) > 0
    assert any(c["filename"] == "stark_private.txt" for c in res_priv_ok.json()["citations"])

    # 6. Legitimate access: Pepper (any org member) queries org public doc -> SUCCESS
    res_org_ok = client.post(
        "/query",
        json={"question": f"What is {stark['markers']['org']}?"},
        headers={"Authorization": f"Bearer {stark['pepper_token']}"},
    )
    assert len(res_org_ok.json()["citations"]) > 0
    assert any(c["filename"] == "stark_handbook.txt" for c in res_org_ok.json()["citations"])


def test_direct_get_and_delete_404_inaccessible(client, two_tenant_setup):
    stark = two_tenant_setup["stark"]
    wayne = two_tenant_setup["wayne"]

    # 1. Wayne user tries GET/DELETE on Stark documents -> 404 for ALL
    for doc_key, doc in stark["docs"].items():
        doc_id = doc["id"]
        get_res = client.get(f"/documents/{doc_id}", headers={"Authorization": f"Bearer {wayne['admin_token']}"})
        assert get_res.status_code == 404

        del_res = client.delete(f"/documents/{doc_id}", headers={"Authorization": f"Bearer {wayne['admin_token']}"})
        assert del_res.status_code == 404

    # 2. Stark member (Peter) tries GET/DELETE on Rhodey's team doc -> 404
    wm_doc_id = stark["docs"]["team_wm"]["id"]
    get_wm = client.get(f"/documents/{wm_doc_id}", headers={"Authorization": f"Bearer {stark['peter_token']}"})
    assert get_wm.status_code == 404

    del_wm = client.delete(f"/documents/{wm_doc_id}", headers={"Authorization": f"Bearer {stark['peter_token']}"})
    assert del_wm.status_code == 404

    # 3. Stark member (Rhodey) tries GET/DELETE on Tony's private doc -> 404
    priv_doc_id = stark["docs"]["private"]["id"]
    get_priv = client.get(f"/documents/{priv_doc_id}", headers={"Authorization": f"Bearer {stark['rhodey_token']}"})
    assert get_priv.status_code == 404

    del_priv = client.delete(f"/documents/{priv_doc_id}", headers={"Authorization": f"Bearer {stark['rhodey_token']}"})
    assert del_priv.status_code == 404
