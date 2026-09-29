"""Simulation routes.

POST /api/projects/{project_id}/tasks/{task_id}/start
  — Authenticated learner starts or resumes a simulation for a project task.
  — Learner identity is taken exclusively from the authentication context.
  — Never accepts learner_id from the request body.

Gemini/LLM calls: ZERO.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.auth import get_current_profile, get_current_user
from app.schemas.auth import AuthenticatedUser, UserProfile
from app.schemas.simulations import SimulationContext
from app.services.simulation_service import start_or_resume_simulation


router = APIRouter(prefix="/projects", tags=["simulations"])


def _require_learner(profile: UserProfile) -> None:
    if profile.role != "learner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Starting a simulation requires a learner account",
        )


@router.post(
    "/{project_id}/tasks/{task_id}/start",
    response_model=SimulationContext,
    status_code=status.HTTP_200_OK,
    summary="Start or resume a simulation for a task",
    description=(
        "Creates a new simulation for this learner+project, or resumes an existing "
        "active/paused one, and records the current task. "
        "Learner identity is derived from the authentication token — never from the request body."
    ),
)
def start_task(
    project_id: UUID,
    task_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    profile: UserProfile = Depends(get_current_profile),
) -> SimulationContext:
    _require_learner(profile)
    return start_or_resume_simulation(
        learner_id=user.id,
        project_id=project_id,
        task_id=task_id,
    )
