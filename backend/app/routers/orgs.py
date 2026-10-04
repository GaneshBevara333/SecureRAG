from typing import List, Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.db.models import User
from app.auth.jwt import hash_password
from app.auth.deps import get_current_user, require_admin, CurrentUser

router = APIRouter(prefix="/orgs", tags=["organizations"])


class AddMemberRequest(BaseModel):
    email: str = Field(..., min_length=3, description="Member email address")
    password: str = Field(..., min_length=6, description="Temporary password")
    role: str = Field("member", description="'admin' or 'member'")


class MemberResponse(BaseModel):
    id: str
    org_id: str
    email: str
    role: str


@router.post("/members", response_model=MemberResponse, status_code=status.HTTP_201_CREATED)
def add_member(
    payload: AddMemberRequest,
    current_admin: CurrentUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Admin invites/adds a new member to the organization."""
    if payload.role not in ("admin", "member"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Role must be either 'admin' or 'member'",
        )

    existing_user = db.query(User).filter(User.email == payload.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email already exists",
        )

    user = User(
        org_id=current_admin.org_id,
        email=payload.email,
        password_hash=hash_password(payload.password),
        role=payload.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return MemberResponse(
        id=user.id,
        org_id=user.org_id,
        email=user.email,
        role=user.role,
    )


@router.get("/members", response_model=List[MemberResponse])
def list_members(
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all members belonging to the current user's organization."""
    members = db.query(User).filter(User.org_id == current_user.org_id).all()
    return [
        MemberResponse(
            id=m.id,
            org_id=m.org_id,
            email=m.email,
            role=m.role,
        )
        for m in members
    ]
