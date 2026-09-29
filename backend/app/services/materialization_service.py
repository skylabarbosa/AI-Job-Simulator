import logging
from uuid import UUID

from fastapi import HTTPException, status

from app.api.routes.projects import _get_project, _require_project_access
from app.core.auth import AuthenticatedUser
from app.db.client import get_supabase_client
from app.schemas.auth import UserProfile
from app.schemas.blueprints import ProjectBlueprint
from app.schemas.materialization import MaterializationResult


logger = logging.getLogger(__name__)


def materialize_project(project_id: UUID, user: AuthenticatedUser, profile: UserProfile) -> MaterializationResult:
    if profile.role not in {"business", "admin"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only business or admin users can materialize projects")
    project = _get_project(project_id)
    _require_project_access(project, user, profile)
    if project.get("status", "draft") not in {"draft", "active"}:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Archived projects cannot materialize a release")
    client = get_supabase_client()
    blueprint = (
        client.table("project_blueprints")
        .select("id, version, status, blueprint_json")
        .eq("project_id", str(project_id))
        .eq("status", "approved")
        .order("version", desc=True)
        .limit(1)
        .execute()
    )
    if not blueprint.data:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An approved blueprint is required")
    blueprint_json = blueprint.data[0]["blueprint_json"]
    try:
        ProjectBlueprint.model_validate(blueprint_json)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Approved blueprint is invalid") from error
    if any(not task.get("task_key") for task in blueprint_json.get("tasks", [])):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Create a blueprint revision to persist missing task identities before materialization",
        )
    try:
        result = client.rpc("materialize_approved_blueprint", {"target_project_id": str(project_id), "target_blueprint_id": blueprint.data[0]["id"]}).execute()
    except Exception as error:
        logger.exception("Approved blueprint materialization failed for project %s", project_id)
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Approved blueprint could not be materialized") from error
    if not result.data:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Materialization returned no result")
    return MaterializationResult.model_validate(result.data)
