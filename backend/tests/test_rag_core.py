import io
from app.db.models import Organization, User, Document, Chunk
from app.ingestion.pipeline import ingest_document
from app.rag.answer import generate_rag_answer


def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_rag_answer_not_found_when_empty(db_session):
    result = generate_rag_answer(db_session, question="What is the secret recipe?")
    assert result["answer"] == "not found in your documents"
    assert result["citations"] == []


def test_rag_answer_with_citations(db_session):
    org = Organization(name="Research Corp")
    db_session.add(org)
    db_session.flush()

    user = User(org_id=org.id, email="researcher@corp.local", password_hash="hash")
    db_session.add(user)
    db_session.commit()

    text_content = b"The primary project deadline is November 15. The designated release coordinator is Alice."
    doc = ingest_document(
        db=db_session,
        org_id=org.id,
        owner_id=user.id,
        filename="project_plan.txt",
        file_bytes=text_content,
        title="Project Plan",
    )

    result = generate_rag_answer(db_session, question="When is the project deadline?", org_id=org.id)
    assert len(result["citations"]) > 0
    citation = result["citations"][0]
    assert citation["document_id"] == doc.id
    assert citation["filename"] == "project_plan.txt"
    assert citation["chunk_index"] == 0
    assert result["latency_ms"] >= 0.0


def test_document_api_flow(client):
    # 0. Register user to get JWT token
    reg_resp = client.post(
        "/auth/register",
        json={"org_name": "Acme Inc", "email": "admin@acme.local", "password": "password123"},
    )
    assert reg_resp.status_code == 201
    token = reg_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Upload document
    file_bytes = b"Security policies require all employees to use multi-factor authentication."
    response = client.post(
        "/documents",
        files={"file": ("security_policy.txt", io.BytesIO(file_bytes), "text/plain")},
        data={"title": "Security Policy", "visibility": "org"},
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()
    doc_id = data["id"]
    assert data["title"] == "Security Policy"
    assert data["chunk_count"] >= 1

    # 2. List documents
    list_resp = client.get("/documents", headers=headers)
    assert list_resp.status_code == 200
    docs = list_resp.json()
    assert any(d["id"] == doc_id for d in docs)

    # 3. Get document details
    get_resp = client.get(f"/documents/{doc_id}", headers=headers)
    assert get_resp.status_code == 200
    doc_detail = get_resp.json()
    assert len(doc_detail["chunks"]) >= 1

    # 4. Query endpoint
    query_resp = client.post(
        "/query",
        json={"question": "What authentication is required?", "mode": "standard"},
        headers=headers,
    )
    assert query_resp.status_code == 200
    q_data = query_resp.json()
    assert "answer" in q_data
    assert len(q_data["citations"]) >= 1
    assert q_data["citations"][0]["document_id"] == doc_id

    # 5. Delete document
    del_resp = client.delete(f"/documents/{doc_id}", headers=headers)
    assert del_resp.status_code == 200

    # 6. Verify 404 after deletion
    get_after_del = client.get(f"/documents/{doc_id}", headers=headers)
    assert get_after_del.status_code == 404
