from datetime import datetime, timezone
from typing import List, Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.db.models import ApiKey
from app.auth.deps import get_current_user, CurrentUser
from app.auth.api_keys import generate_api_key_pair

router = APIRouter(prefix="/api-keys", tags=["api-keys"])


class ApiKeyCreateResponse(BaseModel):
    id: str
    prefix: str
    api_key: str  # Raw secret key, shown only once
    created_at: datetime


class ApiKeyItem(BaseModel):
    id: str
    prefix: str
    created_at: datetime
    revoked_at: Optional[datetime] = None


@router.post("", response_model=ApiKeyCreateResponse, status_code=status.HTTP_201_CREATED)
def create_api_key(
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new API key for the current user. The raw key is returned once."""
    raw_key, key_hash, prefix = generate_api_key_pair()

    key_record = ApiKey(
        user_id=current_user.id,
        key_hash=key_hash,
        prefix=prefix,
        created_at=datetime.now(timezone.utc),
    )
    db.add(key_record)
    db.commit()
    db.refresh(key_record)

    return ApiKeyCreateResponse(
        id=key_record.id,
        prefix=key_record.prefix,
        api_key=raw_key,
        created_at=key_record.created_at,
    )


@router.get("", response_model=List[ApiKeyItem])
def list_api_keys(
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all API keys belonging to the current user."""
    keys = (
        db.query(ApiKey)
        .filter(ApiKey.user_id == current_user.id)
        .order_by(ApiKey.created_at.desc())
        .all()
    )
    return [
        ApiKeyItem(
            id=k.id,
            prefix=k.prefix,
            created_at=k.created_at,
            revoked_at=k.revoked_at,
        )
        for k in keys
    ]


@router.delete("/{key_id}")
def revoke_api_key(
    key_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Revoke an API key. Once revoked, requests using it will be rejected with 401."""
    key_record = (
        db.query(ApiKey)
        .filter(ApiKey.id == key_id, ApiKey.user_id == current_user.id)
        .first()
    )
    if not key_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found",
        )

    if key_record.revoked_at is None:
        key_record.revoked_at = datetime.now(timezone.utc)
        db.commit()

    return {"status": "revoked", "id": key_id}
