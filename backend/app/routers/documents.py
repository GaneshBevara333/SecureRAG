from typing import List, Optional
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, Header
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.db.models import Document, Chunk, Organization, User
from app.ingestion.pipeline import ingest_document

router = APIRouter(prefix="/documents", tags=["documents"])


def get_default_org_and_user(db: Session, x_org_id: Optional[str] = None, x_user_id: Optional[str] = None):
    """Ensure a default organization and user exist for Phase 1 ingestion."""
    if x_org_id and x_user_id:
        return x_org_id, x_user_id

    # Find or create a default demo org and user
    org = db.query(Organization).first()
    if not org:
        org = Organization(name="Default Org")
        db.add(org)
        db.flush()

    user = db.query(User).filter(User.org_id == org.id).first()
    if not user:
        user = User(
            org_id=org.id,
            email="admin@default.local",
            password_hash="mockhash",
            role="admin",
        )
        db.add(user)
        db.flush()

    db.commit()
    return org.id, user.id


@router.post("")
async def upload_document(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    visibility: str = Form("private"),
    team_id: Optional[str] = Form(None),
    x_org_id: Optional[str] = Header(None),
    x_user_id: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """Upload a PDF, Markdown, or Text document for ingestion."""
    filename = file.filename or "uploaded_file.txt"
    content = await file.read()

    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    org_id, user_id = get_default_org_and_user(db, x_org_id, x_user_id)

    try:
        doc = ingest_document(
            db=db,
            org_id=org_id,
            owner_id=user_id,
            filename=filename,
            file_bytes=content,
            title=title,
            visibility=visibility,
            team_id=team_id,
        )
        return {
            "id": doc.id,
            "title": doc.title,
            "filename": doc.filename,
            "visibility": doc.visibility,
            "status": doc.status,
            "version": doc.version,
            "chunk_count": len(doc.chunks),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")


@router.get("")
def list_documents(
    x_org_id: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """List documents."""
    query = db.query(Document)
    if x_org_id:
        query = query.filter(Document.org_id == x_org_id)
    docs = query.all()
    return [
        {
            "id": d.id,
            "title": d.title,
            "filename": d.filename,
            "visibility": d.visibility,
            "status": d.status,
            "version": d.version,
            "created_at": d.created_at.isoformat(),
        }
        for d in docs
    ]


@router.get("/{document_id}")
def get_document(
    document_id: str,
    db: Session = Depends(get_db),
):
    """Retrieve document details by ID."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    return {
        "id": doc.id,
        "title": doc.title,
        "filename": doc.filename,
        "visibility": doc.visibility,
        "status": doc.status,
        "version": doc.version,
        "created_at": doc.created_at.isoformat(),
        "chunks": [
            {
                "id": c.id,
                "chunk_index": c.chunk_index,
                "page": c.page,
                "text": c.text,
            }
            for c in doc.chunks
        ],
    }


@router.delete("/{document_id}")
def delete_document(
    document_id: str,
    db: Session = Depends(get_db),
):
    """Delete a document and all its chunks."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    db.delete(doc)
    db.commit()
    return {"message": "Document deleted successfully", "id": document_id}
