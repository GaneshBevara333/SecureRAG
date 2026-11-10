from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.db.models import EvalCase, EvalRun, EvalResult, QueryLog, Feedback
from app.auth.deps import require_admin, CurrentUser
from app.evals.runner import run_evaluation

router = APIRouter(prefix="/evals", tags=["evals"])


class EvalCaseCreate(BaseModel):
    question: Optional[str] = None
    expected_doc_id: Optional[str] = None
    expected_answer: Optional[str] = None
    query_log_id: Optional[str] = None
    source: str = "manual"


class PromoteFeedbackRequest(BaseModel):
    query_log_id: str
    expected_doc_id: Optional[str] = None
    expected_answer: Optional[str] = None


class EvalCaseResponse(BaseModel):
    id: str
    org_id: str
    question: str
    expected_doc_id: Optional[str] = None
    expected_answer: Optional[str] = None
    source: str
    created_at: datetime


class EvalRunRequest(BaseModel):
    label: str
    config: Dict[str, Any] = Field(default_factory=dict)


class EvalResultResponse(BaseModel):
    id: str
    case_id: str
    hit: bool
    rank: Optional[int] = None
    faithfulness: float
    latency_ms: float
    answer: Optional[str] = None


class EvalRunResponse(BaseModel):
    id: str
    org_id: str
    label: str
    config: Dict[str, Any] = {}
    hit_at_k: float
    mrr: float
    faithfulness: float
    p50_ms: float
    p95_ms: float
    created_at: datetime
    results: Optional[List[EvalResultResponse]] = None


@router.post("/cases", response_model=EvalCaseResponse, status_code=status.HTTP_201_CREATED)
def create_eval_case(
    payload: EvalCaseCreate,
    current_user: CurrentUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Create an eval case (admin-only).
    Can create directly or promote from a thumbs-down query log if query_log_id is provided.
    """
    if payload.query_log_id:
        return _promote_query_log(
            db=db,
            org_id=current_user.org_id,
            query_log_id=payload.query_log_id,
            expected_doc_id=payload.expected_doc_id,
            expected_answer=payload.expected_answer,
            override_question=payload.question,
        )

    if not payload.question:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Question is required when creating an eval case directly",
        )

    case = EvalCase(
        org_id=current_user.org_id,
        question=payload.question,
        expected_doc_id=payload.expected_doc_id,
        expected_answer=payload.expected_answer,
        source=payload.source or "manual",
    )
    db.add(case)
    db.commit()
    db.refresh(case)

    return EvalCaseResponse(
        id=case.id,
        org_id=case.org_id,
        question=case.question,
        expected_doc_id=case.expected_doc_id,
        expected_answer=case.expected_answer,
        source=case.source,
        created_at=case.created_at,
    )


@router.post("/promote-feedback", response_model=EvalCaseResponse, status_code=status.HTTP_201_CREATED)
def promote_feedback_to_case(
    payload: PromoteFeedbackRequest,
    current_user: CurrentUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Admin-only endpoint to promote a thumbs-down (-1) query log into an eval case."""
    return _promote_query_log(
        db=db,
        org_id=current_user.org_id,
        query_log_id=payload.query_log_id,
        expected_doc_id=payload.expected_doc_id,
        expected_answer=payload.expected_answer,
    )


def _promote_query_log(
    db: Session,
    org_id: str,
    query_log_id: str,
    expected_doc_id: Optional[str] = None,
    expected_answer: Optional[str] = None,
    override_question: Optional[str] = None,
) -> EvalCaseResponse:
    # 1. Look up query log within the admin's org
    query_log = (
        db.query(QueryLog)
        .filter(QueryLog.id == query_log_id, QueryLog.org_id == org_id)
        .first()
    )
    if not query_log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Query log not found in your organization",
        )

    # 2. Verify that there is negative feedback (rating == -1) on this query log
    fb = db.query(Feedback).filter(Feedback.query_log_id == query_log.id).first()
    if not fb or fb.rating != -1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only thumbs-down (-1) queries can be promoted to eval cases",
        )

    # 3. Create the eval case with source='feedback'
    question_text = override_question or query_log.question
    case = EvalCase(
        org_id=org_id,
        question=question_text,
        expected_doc_id=expected_doc_id,
        expected_answer=expected_answer,
        source="feedback",
    )
    db.add(case)
    db.commit()
    db.refresh(case)

    return EvalCaseResponse(
        id=case.id,
        org_id=case.org_id,
        question=case.question,
        expected_doc_id=case.expected_doc_id,
        expected_answer=case.expected_answer,
        source=case.source,
        created_at=case.created_at,
    )


@router.get("/cases", response_model=List[EvalCaseResponse])
def list_eval_cases(
    current_user: CurrentUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """List all eval cases belonging to the admin's organization."""
    cases = (
        db.query(EvalCase)
        .filter(EvalCase.org_id == current_user.org_id)
        .order_by(EvalCase.created_at.desc())
        .all()
    )
    return [
        EvalCaseResponse(
            id=c.id,
            org_id=c.org_id,
            question=c.question,
            expected_doc_id=c.expected_doc_id,
            expected_answer=c.expected_answer,
            source=c.source,
            created_at=c.created_at,
        )
        for c in cases
    ]


@router.post("/run", response_model=EvalRunResponse, status_code=status.HTTP_201_CREATED)
def execute_eval_run(
    payload: EvalRunRequest,
    current_user: CurrentUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Admin-only endpoint to execute an evaluation run over all org eval cases."""
    run = run_evaluation(
        db=db,
        org_id=current_user.org_id,
        label=payload.label,
        config=payload.config,
    )
    return EvalRunResponse(
        id=run.id,
        org_id=run.org_id,
        label=run.label,
        config=run.config or {},
        hit_at_k=run.hit_at_k,
        mrr=run.mrr,
        faithfulness=run.faithfulness,
        p50_ms=run.p50_ms,
        p95_ms=run.p95_ms,
        created_at=run.created_at,
    )


@router.get("/runs", response_model=List[EvalRunResponse])
def list_eval_runs(
    current_user: CurrentUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Admin-only endpoint to list all past evaluation runs for the organization."""
    runs = (
        db.query(EvalRun)
        .filter(EvalRun.org_id == current_user.org_id)
        .order_by(EvalRun.created_at.desc())
        .all()
    )
    return [
        EvalRunResponse(
            id=r.id,
            org_id=r.org_id,
            label=r.label,
            config=r.config or {},
            hit_at_k=r.hit_at_k,
            mrr=r.mrr,
            faithfulness=r.faithfulness,
            p50_ms=r.p50_ms,
            p95_ms=r.p95_ms,
            created_at=r.created_at,
        )
        for r in runs
    ]


@router.get("/runs/{run_id}", response_model=EvalRunResponse)
def get_eval_run_detail(
    run_id: str,
    current_user: CurrentUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Admin-only endpoint to retrieve detailed results for a specific evaluation run."""
    run = (
        db.query(EvalRun)
        .filter(EvalRun.id == run_id, EvalRun.org_id == current_user.org_id)
        .first()
    )
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Eval run not found",
        )

    results = (
        db.query(EvalResult)
        .filter(EvalResult.run_id == run.id)
        .all()
    )

    return EvalRunResponse(
        id=run.id,
        org_id=run.org_id,
        label=run.label,
        config=run.config or {},
        hit_at_k=run.hit_at_k,
        mrr=run.mrr,
        faithfulness=run.faithfulness,
        p50_ms=run.p50_ms,
        p95_ms=run.p95_ms,
        created_at=run.created_at,
        results=[
            EvalResultResponse(
                id=res.id,
                case_id=res.case_id,
                hit=res.hit,
                rank=res.rank,
                faithfulness=res.faithfulness,
                latency_ms=res.latency_ms,
                answer=res.answer,
            )
            for res in results
        ],
    )
