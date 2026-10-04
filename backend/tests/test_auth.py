from datetime import timedelta
import pytest
from app.auth.jwt import create_access_token


def test_register_creates_org_and_admin(client):
    res = client.post(
        "/auth/register",
        json={"org_name": "Acme Corp", "email": "admin@acme.com", "password": "securepassword123"},
    )
    assert res.status_code == 201
    data = res.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == "admin@acme.com"
    assert data["user"]["role"] == "admin"
    assert data["user"]["org_id"] is not None


def test_register_duplicate_email_rejected(client):
    client.post(
        "/auth/register",
        json={"org_name": "Acme Corp", "email": "admin@acme.com", "password": "password123"},
    )
    res = client.post(
        "/auth/register",
        json={"org_name": "Another Corp", "email": "admin@acme.com", "password": "password123"},
    )
    assert res.status_code == 400
    assert "already registered" in res.json()["detail"].lower()


def test_login_success(client):
    client.post(
        "/auth/register",
        json={"org_name": "Acme Corp", "email": "admin@acme.com", "password": "securepassword123"},
    )
    login_res = client.post(
        "/auth/login",
        json={"email": "admin@acme.com", "password": "securepassword123"},
    )
    assert login_res.status_code == 200
    data = login_res.json()
    assert "access_token" in data
    assert data["user"]["role"] == "admin"


def test_wrong_password_rejected(client):
    client.post(
        "/auth/register",
        json={"org_name": "Acme Corp", "email": "admin@acme.com", "password": "correctpassword"},
    )
    login_res = client.post(
        "/auth/login",
        json={"email": "admin@acme.com", "password": "wrongpassword"},
    )
    assert login_res.status_code == 401
    assert "invalid email or password" in login_res.json()["detail"].lower()


def test_expired_token_rejected(client):
    # Register user
    reg_res = client.post(
        "/auth/register",
        json={"org_name": "Acme Corp", "email": "admin@acme.com", "password": "password123"},
    )
    user_id = reg_res.json()["user"]["id"]
    org_id = reg_res.json()["user"]["org_id"]

    # Create an expired token (negative delta)
    expired_token = create_access_token(
        {"sub": user_id, "org_id": org_id, "role": "admin"},
        expires_delta=timedelta(seconds=-10),
    )

    # Attempt to access protected endpoint
    res = client.get("/auth/me", headers={"Authorization": f"Bearer {expired_token}"})
    assert res.status_code == 401
    assert "expired" in res.json()["detail"].lower()


def test_unauthenticated_requests_rejected(client):
    # Calling /documents without token
    res1 = client.get("/documents")
    assert res1.status_code == 401

    # Calling /query without token
    res2 = client.post("/query", json={"question": "Hello?"})
    assert res2.status_code == 401


def test_member_cannot_call_admin_endpoints(client):
    # 1. Register admin and organization
    admin_res = client.post(
        "/auth/register",
        json={"org_name": "Sec Corp", "email": "admin@sec.com", "password": "adminpassword"},
    )
    admin_token = admin_res.json()["access_token"]

    # 2. Admin adds a regular member
    add_member_res = client.post(
        "/orgs/members",
        json={"email": "member@sec.com", "password": "memberpassword", "role": "member"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert add_member_res.status_code == 201

    # 3. Member logs in
    member_login = client.post(
        "/auth/login",
        json={"email": "member@sec.com", "password": "memberpassword"},
    )
    assert member_login.status_code == 200
    member_token = member_login.json()["access_token"]

    # 4. Member attempts to create a team (admin only) -> Expect 403 Forbidden
    team_res = client.post(
        "/teams",
        json={"name": "Engineering"},
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert team_res.status_code == 403
    assert "admin privileges required" in team_res.json()["detail"].lower()

    # 5. Member attempts to add another member (admin only) -> Expect 403 Forbidden
    invite_res = client.post(
        "/orgs/members",
        json={"email": "hacker@sec.com", "password": "password", "role": "member"},
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert invite_res.status_code == 403


def test_admin_manages_teams_and_members(client):
    # 1. Register admin
    admin_res = client.post(
        "/auth/register",
        json={"org_name": "DevOrg", "email": "admin@dev.org", "password": "adminpassword123"},
    )
    admin_token = admin_res.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # 2. Add member
    add_res = client.post(
        "/orgs/members",
        json={"email": "bob@dev.org", "password": "bobpassword", "role": "member"},
        headers=admin_headers,
    )
    assert add_res.status_code == 201
    bob_id = add_res.json()["id"]

    # 3. Create team
    team_res = client.post(
        "/teams",
        json={"name": "Backend Engineers"},
        headers=admin_headers,
    )
    assert team_res.status_code == 201
    team_id = team_res.json()["id"]

    # 4. Add member to team
    join_res = client.post(
        f"/teams/{team_id}/members",
        json={"user_id": bob_id},
        headers=admin_headers,
    )
    assert join_res.status_code == 201

    # 5. Verify Bob's /auth/me reflects team membership
    bob_login = client.post(
        "/auth/login",
        json={"email": "bob@dev.org", "password": "bobpassword"},
    )
    bob_token = bob_login.json()["access_token"]
    me_res = client.get("/auth/me", headers={"Authorization": f"Bearer {bob_token}"})
    assert me_res.status_code == 200
    me_data = me_res.json()
    assert me_data["email"] == "bob@dev.org"
    assert team_id in me_data["team_ids"]
