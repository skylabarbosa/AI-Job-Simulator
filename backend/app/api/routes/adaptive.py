"""Read-only adaptive presentation decisions for required project tasks."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.auth import get_current_profile, get_current_user
from app.schemas.adaptive import AdaptivePresentationDecision
from app.schemas.auth import AuthenticatedUser, UserProfile
from app.services.adaptive_service import get_adaptive_decision


router = APIRouter(prefix="/projects", tags=["adaptive"])


@router.get(
    "/{project_id}/tasks/{task_id}/adaptive-decision",
    response_model=AdaptivePresentationDecision,
    summary="Get presentation guidance for a required task",
)
def adaptive_decision(
    project_id: UUID,
    task_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    profile: UserProfile = Depends(get_current_profile),
) -> AdaptivePresentationDecision:
    if profile.role != "learner":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Adaptive decisions require a learner account")
    return get_adaptive_decision(learner_id=user.id, project_id=project_id, task_id=task_id)