from dataclasses import dataclass
from typing import List, Optional
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.db.models import User, TeamMember
from app.auth.jwt import decode_access_token

security = HTTPBearer(auto_error=False)


@dataclass
class CurrentUser:
    user: User
    id: str
    org_id: str
    role: str
    email: str
    team_ids: List[str]


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db),
) -> CurrentUser:
    """Dependency that resolves current user, org, role, and team IDs on every request."""
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

    # Resolve team IDs for the user
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
