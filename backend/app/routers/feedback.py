from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.db.models import Feedback, QueryLog
from app.auth.deps import get_current_user_or_api_key, CurrentUser

router = APIRouter(prefix="/feedback", tags=["feedback"])


class FeedbackCreate(BaseModel):
    query_log_id: str
    rating: int = Field(..., description="+1 for thumbs-up, -1 for thumbs-down")
    comment: Optional[str] = None


class FeedbackResponse(BaseModel):
    id: str
    query_log_id: str
    rating: int
    comment: Optional[str] = None
    created_at: datetime


@router.post("", response_model=FeedbackResponse, status_code=status.HTTP_201_CREATED)
def submit_feedback(
    payload: FeedbackCreate,
    current_user: CurrentUser = Depends(get_current_user_or_api_key),
    db: Session = Depends(get_db),
):
    """
    Submit feedback (+1 / -1, optional comment) on a query log.
    Enforces that users can only submit feedback on their own query logs (returns 404 otherwise).
    """
    if payload.rating not in (1, -1):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Rating must be +1 or -1",
        )

    # 1. Lookup query log belonging strictly to the current user and org
    query_log = (
        db.query(QueryLog)
        .filter(
            QueryLog.id == payload.query_log_id,
            QueryLog.user_id == current_user.id,
            QueryLog.org_id == current_user.org_id,
        )
        .first()
    )
    if not query_log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Query log not found",
        )

    # 2. Check if feedback already exists for this query log (update if so)
    existing_fb = db.query(Feedback).filter(Feedback.query_log_id == query_log.id).first()
    if existing_fb:
        existing_fb.rating = payload.rating
        existing_fb.comment = payload.comment
        db.commit()
        db.refresh(existing_fb)
        feedback_record = existing_fb
    else:
        feedback_record = Feedback(
            query_log_id=query_log.id,
            rating=payload.rating,
            comment=payload.comment,
        )
        db.add(feedback_record)
        db.commit()
        db.refresh(feedback_record)

    return FeedbackResponse(
        id=feedback_record.id,
        query_log_id=feedback_record.query_log_id,
        rating=feedback_record.rating,
        comment=feedback_record.comment,
        created_at=feedback_record.created_at,
    )


@router.get("", response_model=List[FeedbackResponse])
def list_feedback(
    current_user: CurrentUser = Depends(get_current_user_or_api_key),
    db: Session = Depends(get_db),
):
    """List feedback submitted on the current user's query logs."""
    feedbacks = (
        db.query(Feedback)
        .join(QueryLog, Feedback.query_log_id == QueryLog.id)
        .filter(QueryLog.user_id == current_user.id, QueryLog.org_id == current_user.org_id)
        .order_by(Feedback.created_at.desc())
        .all()
    )
    return [
        FeedbackResponse(
            id=fb.id,
            query_log_id=fb.query_log_id,
            rating=fb.rating,
            comment=fb.comment,
            created_at=fb.created_at,
        )
        for fb in feedbacks
    ]


@router.get("/{feedback_id}", response_model=FeedbackResponse)
def get_feedback(
    feedback_id: str,
    current_user: CurrentUser = Depends(get_current_user_or_api_key),
    db: Session = Depends(get_db),
):
    """Get feedback by ID; returns 404 if it belongs to another user's query log or does not exist."""
    fb = (
        db.query(Feedback)
        .join(QueryLog, Feedback.query_log_id == QueryLog.id)
        .filter(
            Feedback.id == feedback_id,
            QueryLog.user_id == current_user.id,
            QueryLog.org_id == current_user.org_id,
        )
        .first()
    )
    if not fb:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Feedback not found",
        )
    return FeedbackResponse(
        id=fb.id,
        query_log_id=fb.query_log_id,
        rating=fb.rating,
        comment=fb.comment,
        created_at=fb.created_at,
    )
