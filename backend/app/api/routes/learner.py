from fastapi import APIRouter, Depends, HTTPException, status

from app.core.auth import get_current_profile, get_current_user
from app.schemas.auth import AuthenticatedUser, UserProfile
from app.schemas.performance import LearnerProgressResponse, LearnerSkillsResponse
from app.services.performance_service import get_learner_progress, get_learner_skills

router = APIRouter(prefix="/learner", tags=["learner"])


def _require_learner(profile: UserProfile) -> None:
    if profile.role != "learner":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Learner access is required")


@router.get("/progress", response_model=LearnerProgressResponse)
def learner_progress(
    user: AuthenticatedUser = Depends(get_current_user),
    profile: UserProfile = Depends(get_current_profile),
) -> LearnerProgressResponse:
    _require_learner(profile)
    return get_learner_progress(learner_id=user.id)


@router.get("/skills", response_model=LearnerSkillsResponse)
def learner_skills(
    user: AuthenticatedUser = Depends(get_current_user),
    profile: UserProfile = Depends(get_current_profile),
) -> LearnerSkillsResponse:
    _require_learner(profile)
    return get_learner_skills(learner_id=user.id)
