from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.db.models import Organization, User
from app.auth.jwt import hash_password, verify_password, create_access_token
from app.auth.deps import get_current_user, CurrentUser

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    org_name: str = Field(..., min_length=1, description="Organization name")
    email: str = Field(..., min_length=3, description="Admin email address")
    password: str = Field(..., min_length=6, description="Admin password")


class LoginRequest(BaseModel):
    email: str = Field(..., min_length=3, description="User email address")
    password: str = Field(..., min_length=1, description="User password")


class UserResponse(BaseModel):
    id: str
    org_id: str
    email: str
    role: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class CurrentUserResponse(BaseModel):
    id: str
    org_id: str
    email: str
    role: str
    team_ids: list[str]


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    """Register a new organization and its first admin user."""
    # Check if email is already taken
    existing_user = db.query(User).filter(User.email == payload.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email is already registered",
        )

    # 1. Create Organization
    org = Organization(name=payload.org_name)
    db.add(org)
    db.flush()

    # 2. Create first User as Admin
    user = User(
        org_id=org.id,
        email=payload.email,
        password_hash=hash_password(payload.password),
        role="admin",
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # 3. Generate JWT access token
    access_token = create_access_token({
        "sub": user.id,
        "org_id": org.id,
        "role": user.role,
        "email": user.email,
    })

    return AuthResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse(
            id=user.id,
            org_id=user.org_id,
            email=user.email,
            role=user.role,
        ),
    )


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    """Authenticate user with email and password, returning a JWT."""
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token({
        "sub": user.id,
        "org_id": user.org_id,
        "role": user.role,
        "email": user.email,
    })

    return AuthResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse(
            id=user.id,
            org_id=user.org_id,
            email=user.email,
            role=user.role,
        ),
    )


@router.get("/me", response_model=CurrentUserResponse)
def get_me(current_user: CurrentUser = Depends(get_current_user)):
    """Return currently authenticated user profile and team memberships."""
    return CurrentUserResponse(
        id=current_user.id,
        org_id=current_user.org_id,
        email=current_user.email,
        role=current_user.role,
        team_ids=current_user.team_ids,
    )
