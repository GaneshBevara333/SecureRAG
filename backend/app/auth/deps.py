from dataclasses import dataclass
from typing import List, Optional
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, APIKeyHeader
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.db.models import User, TeamMember, ApiKey
from app.auth.jwt import decode_access_token
from app.auth.api_keys import hash_api_key

security = HTTPBearer(auto_error=False)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


@dataclass
class CurrentUser:
    user: User
    id: str
    org_id: str
    role: str
    email: str
    team_ids: List[str]


def _resolve_current_user_from_user(user: User, db: Session) -> CurrentUser:
    """Helper to populate CurrentUser and associated team IDs."""
    team_memberships = db.query(TeamMember.team_id).filter(TeamMember.user_id == user.id).all()
    team_ids = [tm[0] for tm in team_memberships]
    return CurrentUser(
        user=user,
        id=user.id,
        org_id=user.org_id,
        role=user.role,
        email=user.email,
        team_ids=team_ids,
    )


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db),
) -> CurrentUser:
    """Dependency that resolves current user, org, role, and team IDs from a JWT access token."""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    try:
        payload = decode_access_token(token)
        user_id: Optional[str] = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing subject",
                headers={"WWW-Authenticate": "Bearer"},
            )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except (jwt.InvalidTokenError, Exception):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return _resolve_current_user_from_user(user, db)


def get_current_user_or_api_key(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    api_key_val: Optional[str] = Depends(api_key_header),
    db: Session = Depends(get_db),
) -> CurrentUser:
    """
    Dependency that resolves the caller either via JWT Bearer token or API key
    (via X-API-Key header or Authorization: Bearer sec_...).
    """
    # 1. Check X-API-Key header
    raw_key = api_key_val

    # 2. If not in header, check if Bearer token is an API key (starts with 'sec_')
    if not raw_key and credentials and credentials.credentials.startswith("sec_"):
        raw_key = credentials.credentials

    # 3. If an API key was provided, authenticate via API key
    if raw_key:
        key_hash = hash_api_key(raw_key)
        api_key_record = db.query(ApiKey).filter(ApiKey.key_hash == key_hash).first()
        if not api_key_record:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key",
            )
        if api_key_record.revoked_at is not None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="API key has been revoked",
            )

        user = db.query(User).filter(User.id == api_key_record.user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User associated with API key not found",
            )
        return _resolve_current_user_from_user(user, db)

    # 4. Otherwise, fall back to standard JWT authentication
    return get_current_user(credentials=credentials, db=db)


def require_admin(
    current_user: CurrentUser = Depends(get_current_user),
) -> CurrentUser:
    """Dependency that ensures the authenticated user has an 'admin' role."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    return current_user
