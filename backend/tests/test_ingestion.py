from app.db.models import Organization, User, Document, Chunk
from app.ingestion.loaders import load_file_content
from app.ingestion.pipeline import ingest_document


def test_loaders_txt_and_md():
    txt_content = b"This is a test plain text document."
    pages = load_file_content("test.txt", txt_content)
    assert len(pages) == 1
    assert "plain text" in pages[0].text
    assert pages[0].page_number == 1

    md_content = b"# Header\n\nSome markdown details here."
    md_pages = load_file_content("test.md", md_content)
    assert len(md_pages) == 1
    assert "# Header" in md_pages[0].text


def test_ingest_document_pipeline(db_session):
    org = Organization(name="Test Org")
    db_session.add(org)
    db_session.flush()

    user = User(org_id=org.id, email="test@example.com", password_hash="dummy")
    db_session.add(user)
    db_session.commit()

    content = b"Introduction to SecureRAG.\n\nSecureRAG provides access-controlled RAG for enterprises."
    doc = ingest_document(
        db=db_session,
        org_id=org.id,
        owner_id=user.id,
        filename="intro.txt",
        file_bytes=content,
        title="Intro Doc",
        visibility="org",
    )

    assert doc.id is not None
    assert doc.title == "Intro Doc"
    assert doc.status == "processed"
    assert doc.version == 1

    # Check chunks in DB
    chunks = db_session.query(Chunk).filter(Chunk.document_id == doc.id).all()
    assert len(chunks) >= 1
    assert chunks[0].org_id == org.id
    assert chunks[0].embedding is not None
    assert len(chunks[0].embedding) == 384
