from typing import List, Optional
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.db.models import Document, Team
from app.ingestion.pipeline import ingest_document
from app.auth.deps import get_current_user, CurrentUser

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("")
async def upload_document(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    visibility: str = Form("private"),
    team_id: Optional[str] = Form(None),
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Upload a document; securely associated with the authenticated user and organization."""
    if visibility not in ("private", "team", "org"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Visibility must be 'private', 'team', or 'org'",
        )

    if team_id:
        team = db.query(Team).filter(
            Team.id == team_id,
            Team.org_id == current_user.org_id,
        ).first()
        if not team:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Team does not exist in your organization",
            )

    filename = file.filename or "uploaded_file.txt"
    content = await file.read()

    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )

    try:
        doc = ingest_document(
            db=db,
            org_id=current_user.org_id,
            owner_id=current_user.id,
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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ingestion failed: {str(e)}",
        )


@router.get("")
def list_documents(
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List documents belonging to the authenticated user's organization."""
    docs = db.query(Document).filter(Document.org_id == current_user.org_id).all()
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
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve document details by ID. Returns 404 for inaccessible documents."""
    doc = db.query(Document).filter(
        Document.id == document_id,
        Document.org_id == current_user.org_id,
    ).first()

    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

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
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a document. Only owner or admin may delete; returns 404 if inaccessible."""
    doc = db.query(Document).filter(
        Document.id == document_id,
        Document.org_id == current_user.org_id,
    ).first()

    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    # Only owner or admin may delete
    if doc.owner_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    db.delete(doc)
    db.commit()
    return {"message": "Document deleted successfully", "id": document_id}
