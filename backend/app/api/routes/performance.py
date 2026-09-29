from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.auth import get_current_profile, get_current_user
from app.schemas.auth import AuthenticatedUser, UserProfile
from app.schemas.performance import EvaluationResponse, ProjectPerformanceResponse
from app.services.performance_service import get_project_performance, get_task_evaluation


router = APIRouter(prefix="/projects", tags=["performance"])


def _require_learner(profile: UserProfile) -> None:
    if profile.role != "learner":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Learner performance access is required")


@router.get("/{project_id}/performance", response_model=ProjectPerformanceResponse)
def project_performance(
    project_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    profile: UserProfile = Depends(get_current_profile),
) -> ProjectPerformanceResponse:
    _require_learner(profile)
    return get_project_performance(learner_id=user.id, project_id=project_id)


@router.get("/{project_id}/tasks/{task_id}/evaluation", response_model=EvaluationResponse)
def task_evaluation(
    project_id: UUID,
    task_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    profile: UserProfile = Depends(get_current_profile),
) -> EvaluationResponse:
    _require_learner(profile)
    result = get_task_evaluation(learner_id=user.id, project_id=project_id, task_id=task_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evaluation not found")
    return result