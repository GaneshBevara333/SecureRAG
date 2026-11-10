from typing import List, Optional
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.db.models import Document, Team
from app.ingestion.pipeline import ingest_document
from app.auth.deps import get_current_user, CurrentUser
from app.retrieval.acl import build_acl_condition
from app.llm.cache import bump_corpus_version

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
    """
    Upload a document with visibility and team permissions.
    If team_id is provided, user must be a member of that team.
    """
    if visibility not in ("private", "team", "org"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Visibility must be 'private', 'team', or 'org'",
        )

    if visibility == "team" and not team_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="team_id is required when visibility is 'team'",
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

        if team_id not in current_user.team_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User is not a member of the specified team",
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
        bump_corpus_version(db, current_user.org_id)
        return {
            "id": doc.id,
            "title": doc.title,
            "filename": doc.filename,
            "visibility": doc.visibility,
            "team_id": doc.team_id,
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
    """List only documents that the user is permitted to view under ACL rules."""
    acl_filter = build_acl_condition(
        user_id=current_user.id,
        org_id=current_user.org_id,
        is_admin=(current_user.role == "admin"),
        team_ids=current_user.team_ids,
    )
    docs = db.query(Document).filter(acl_filter).all()
    return [
        {
            "id": d.id,
            "title": d.title,
            "filename": d.filename,
            "visibility": d.visibility,
            "team_id": d.team_id,
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
    """Retrieve document details. Returns 404 (never 403) for inaccessible documents."""
    acl_filter = build_acl_condition(
        user_id=current_user.id,
        org_id=current_user.org_id,
        is_admin=(current_user.role == "admin"),
        team_ids=current_user.team_ids,
    )
    doc = db.query(Document).filter(
        Document.id == document_id,
        acl_filter,
    ).first()

    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    return {
        "id": doc.id,
        "title": doc.title,
        "filename": doc.filename,
        "visibility": doc.visibility,
        "team_id": doc.team_id,
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
    """Delete a document. Returns 404 for inaccessible documents."""
    acl_filter = build_acl_condition(
        user_id=current_user.id,
        org_id=current_user.org_id,
        is_admin=(current_user.role == "admin"),
        team_ids=current_user.team_ids,
    )
    doc = db.query(Document).filter(
        Document.id == document_id,
        acl_filter,
    ).first()

    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    # Only owner or admin may delete
    if doc.owner_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    db.delete(doc)
    db.commit()
    bump_corpus_version(db, current_user.org_id)
    return {"message": "Document deleted successfully", "id": document_id}
