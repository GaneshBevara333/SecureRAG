from typing import List, Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.db.models import Team, TeamMember, User
from app.auth.deps import get_current_user, require_admin, CurrentUser

router = APIRouter(prefix="/teams", tags=["teams"])


class CreateTeamRequest(BaseModel):
    name: str = Field(..., min_length=1, description="Team name")


class TeamResponse(BaseModel):
    id: str
    org_id: str
    name: str


class AddTeamMemberRequest(BaseModel):
    user_id: str = Field(..., description="ID of the user to add to the team")


class TeamMemberDetail(BaseModel):
    user_id: str
    email: str
    role: str


@router.post("", response_model=TeamResponse, status_code=status.HTTP_201_CREATED)
def create_team(
    payload: CreateTeamRequest,
    current_admin: CurrentUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Admin creates a new team within the organization."""
    team = Team(
        org_id=current_admin.org_id,
        name=payload.name,
    )
    db.add(team)
    db.commit()
    db.refresh(team)

    return TeamResponse(
        id=team.id,
        org_id=team.org_id,
        name=team.name,
    )


@router.get("", response_model=List[TeamResponse])
def list_teams(
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all teams within the current user's organization."""
    teams = db.query(Team).filter(Team.org_id == current_user.org_id).all()
    return [
        TeamResponse(
            id=t.id,
            org_id=t.org_id,
            name=t.name,
        )
        for t in teams
    ]


@router.post("/{team_id}/members", status_code=status.HTTP_201_CREATED)
def add_team_member(
    team_id: str,
    payload: AddTeamMemberRequest,
    current_admin: CurrentUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Admin adds a user to a team."""
    team = db.query(Team).filter(
        Team.id == team_id,
        Team.org_id == current_admin.org_id,
    ).first()
    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found in your organization",
        )

    user = db.query(User).filter(
        User.id == payload.user_id,
        User.org_id == current_admin.org_id,
    ).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found in your organization",
        )

    # Check if already a member
    existing = db.query(TeamMember).filter(
        TeamMember.team_id == team_id,
        TeamMember.user_id == payload.user_id,
    ).first()
    if existing:
        return {"message": "User is already a member of this team"}

    membership = TeamMember(
        team_id=team_id,
        user_id=payload.user_id,
    )
    db.add(membership)
    db.commit()

    return {"message": "User added to team successfully", "team_id": team_id, "user_id": payload.user_id}


@router.get("/{team_id}/members", response_model=List[TeamMemberDetail])
def list_team_members(
    team_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all members of a team in the organization."""
    team = db.query(Team).filter(
        Team.id == team_id,
        Team.org_id == current_user.org_id,
    ).first()
    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found in your organization",
        )

    memberships = (
        db.query(User)
        .join(TeamMember, TeamMember.user_id == User.id)
        .filter(TeamMember.team_id == team_id)
        .all()
    )

    return [
        TeamMemberDetail(
            user_id=u.id,
            email=u.email,
            role=u.role,
        )
        for u in memberships
    ]
