"""Task submission routes for the generic learner evaluation pipeline."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.auth import get_current_profile, get_current_user
from app.schemas.auth import AuthenticatedUser, UserProfile
from app.schemas.submissions import SubmissionCreate, SubmissionResult
from app.services.submission_service import submit_task_work, validate_task_work


router = APIRouter(prefix="/projects", tags=["submissions"])


def _require_learner(profile: UserProfile) -> None:
    if profile.role != "learner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Submitting work requires a learner account",
        )


@router.post(
    "/{project_id}/tasks/{task_id}/submit",
    response_model=SubmissionResult,
    status_code=status.HTTP_201_CREATED,
    summary="Submit learner work for the active task",
)
@router.post(
    "/{project_id}/tasks/{task_id}/submissions",
    response_model=SubmissionResult,
    status_code=status.HTTP_201_CREATED,
    summary="Submit learner work for the active task",
)
def submit_task(
    project_id: UUID,
    task_id: UUID,
    payload: SubmissionCreate,
    user: AuthenticatedUser = Depends(get_current_user),
    profile: UserProfile = Depends(get_current_profile),
) -> SubmissionResult:
    _require_learner(profile)
    return submit_task_work(
        learner_id=user.id,
        project_id=project_id,
        task_id=task_id,
        payload=payload,
    )


@router.post(
    "/{project_id}/tasks/{task_id}/check",
    response_model=SubmissionResult,
    status_code=status.HTTP_200_OK,
    summary="Validate learner work without creating a submission",
)
def check_task(
    project_id: UUID,
    task_id: UUID,
    payload: SubmissionCreate,
    user: AuthenticatedUser = Depends(get_current_user),
    profile: UserProfile = Depends(get_current_profile),
) -> SubmissionResult:
    _require_learner(profile)
    return validate_task_work(
        learner_id=user.id,
        project_id=project_id,
        task_id=task_id,
        payload=payload,
    )
