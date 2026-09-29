from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.core.auth import get_current_profile, get_current_user
from app.schemas.auth import AuthenticatedUser, UserProfile
from app.schemas.blueprints import (
    BlueprintApproval,
    BlueprintOverview,
    BlueprintRecord,
    BlueprintReviseRequest,
    BlueprintUpdateRequest,
)
from app.schemas.materialization import MaterializationResult
from app.services.blueprint_service import (
    approve_blueprint,
    generate_blueprint,
    get_approved_overview,
    get_latest_blueprint,
    revise_blueprint,
    update_blueprint_draft,
)
from app.services.materialization_service import materialize_project


router = APIRouter(prefix="/projects/{project_id}/blueprint", tags=["blueprints"])


@router.post("/generate", response_model=BlueprintRecord)
def generate_project_blueprint(
    project_id: UUID,
    regenerate: bool = Query(default=False),
    user: AuthenticatedUser = Depends(get_current_user),
    profile: UserProfile = Depends(get_current_profile),
) -> BlueprintRecord:
    return generate_blueprint(project_id, user, profile, regenerate=regenerate)


@router.get("", response_model=BlueprintRecord)
def get_project_blueprint(
    project_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    profile: UserProfile = Depends(get_current_profile),
) -> BlueprintRecord:
    return get_latest_blueprint(project_id, user, profile)


@router.get("/overview", response_model=BlueprintOverview)
def get_project_blueprint_overview(
    project_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    profile: UserProfile = Depends(get_current_profile),
) -> BlueprintOverview:
    return get_approved_overview(project_id, user, profile)


@router.post("/revise", response_model=BlueprintRecord)
def revise_project_blueprint(
    project_id: UUID,
    payload: BlueprintReviseRequest | None = None,
    user: AuthenticatedUser = Depends(get_current_user),
    profile: UserProfile = Depends(get_current_profile),
) -> BlueprintRecord:
    return revise_blueprint(project_id, user, profile, payload=payload)


@router.patch("/{blueprint_id}", response_model=BlueprintRecord)
def update_project_blueprint(
    project_id: UUID,
    blueprint_id: UUID,
    payload: BlueprintUpdateRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    profile: UserProfile = Depends(get_current_profile),
) -> BlueprintRecord:
    return update_blueprint_draft(project_id, blueprint_id, payload, user, profile)


@router.post("/approve", response_model=BlueprintRecord)
def approve_project_blueprint(
    project_id: UUID,
    payload: BlueprintApproval,
    user: AuthenticatedUser = Depends(get_current_user),
    profile: UserProfile = Depends(get_current_profile),
) -> BlueprintRecord:
    return approve_blueprint(project_id, payload.blueprint_id, user, profile)


@router.post("/materialize", response_model=MaterializationResult)
def materialize_project_blueprint(
    project_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    profile: UserProfile = Depends(get_current_profile),
) -> MaterializationResult:
    return materialize_project(project_id, user, profile)
