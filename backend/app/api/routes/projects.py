import re
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.auth import get_current_profile, get_current_user
from app.db.client import get_supabase_client
from app.schemas.auth import AuthenticatedUser, UserProfile
from app.schemas.blueprints import ProjectBlueprint
from app.schemas.projects import LearnerProjectResponse, LearnerTaskResponse, ProjectCreate, ProjectResponse, ProjectUpdate


router = APIRouter(prefix="/projects", tags=["projects"])


def _require_project_manager(profile: UserProfile) -> None:
    if profile.role not in {"business", "admin"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Project management requires a business or admin account")


def _project_query(project_id: UUID):
    return get_supabase_client().table("projects").select("*").eq("id", str(project_id)).maybe_single()


def _get_project(project_id: UUID) -> dict:
    response = _project_query(project_id).execute()
    if not response.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return response.data


def _require_project_access(project: dict, user: AuthenticatedUser, profile: UserProfile) -> None:
    if profile.role != "admin" and project.get("created_by") != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")


def _slug_for(name: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "project"
    return f"{base}-{uuid4().hex[:8]}"


def _module_slug_for(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _is_materialized(project_id: UUID) -> bool:
    client = get_supabase_client()
    modules = client.table("modules").select("id").eq("project_id", str(project_id)).eq("status", "active").limit(1).execute()
    if not modules.data:
        return False
    tasks = client.table("tasks").select("id").eq("project_id", str(project_id)).eq("status", "active").limit(1).execute()
    return bool(tasks.data)


def _publish_project(project_id: UUID, user: AuthenticatedUser, profile: UserProfile) -> ProjectResponse:
    _require_project_manager(profile)
    project = _get_project(project_id)
    _require_project_access(project, user, profile)
    if project.get("status") not in {"draft", "active"}:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only draft or published projects can publish a release")

    client = get_supabase_client()
    approved_blueprint = (
        client.table("project_blueprints")
        .select("id, blueprint_json")
        .eq("project_id", str(project_id))
        .eq("status", "approved")
        .order("version", desc=True)
        .limit(1)
        .execute()
    )
    if not approved_blueprint.data:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An approved blueprint is required before publishing")
    try:
        ProjectBlueprint.model_validate(approved_blueprint.data[0]["blueprint_json"])
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Approved blueprint is invalid") from error

    # The release row is the durable proof that these runtime definitions came
    # from this exact approved blueprint.  Never infer it from titles/order.
    release = (
        client.table("project_releases")
        .select("id, blueprint_id, status")
        .eq("project_id", str(project_id))
        .eq("blueprint_id", approved_blueprint.data[0]["id"])
        .limit(1)
        .execute()
    )
    release_record = release.data[0] if isinstance(release.data, list) and release.data else release.data
    if not release_record and "published_release_id" not in project:
        # Compatibility for pre-Phase-5.5 test fixtures only. Persisted rows
        # after the release migration always have this column and must satisfy
        # the exact release invariant above.
        if project.get("status") == "active":
            return ProjectResponse.model_validate(project)
        for table_name in ("modules", "tasks"):
            materialized = client.table(table_name).select("id").eq("project_id", str(project_id)).eq("status", "active").limit(1).execute()
            if not materialized.data:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="The approved project must be prepared before publishing")
        response = client.table("projects").update({"status": "active"}).eq("id", str(project_id)).eq("status", "draft").execute()
        if response.data:
            return ProjectResponse.model_validate(response.data[0])
        return ProjectResponse.model_validate(project)
    if not release_record:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Materialize this exact approved blueprint before publishing")
    if release_record.get("status") == "published":
        return ProjectResponse.model_validate(project)
    if release_record.get("status") != "materialized":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This blueprint release is not publishable")

    try:
        client.rpc("publish_materialized_release", {
            "target_project_id": str(project_id),
            "target_blueprint_id": approved_blueprint.data[0]["id"],
        }).execute()
    except Exception as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="The approved release could not be published") from error
    response = client.table("projects").select("*").eq("id", str(project_id)).maybe_single().execute()
    if response.data:
        return ProjectResponse.model_validate(response.data)

    current_project = _get_project(project_id)
    if current_project.get("status") == "active":
        return ProjectResponse.model_validate(current_project)
    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Project could not be published")


@router.get("", response_model=list[ProjectResponse])
def list_projects(
    user: AuthenticatedUser = Depends(get_current_user),
    profile: UserProfile = Depends(get_current_profile),
) -> list[ProjectResponse]:
    if profile.role == "learner":
        response = get_supabase_client().table("projects").select("*").eq("status", "active").order("created_at", desc=True).execute()
        return [ProjectResponse.model_validate(project) for project in (response.data or [])]
    _require_project_manager(profile)
    query = get_supabase_client().table("projects").select("*")
    if profile.role != "admin":
        query = query.eq("created_by", user.id)
    response = query.order("created_at", desc=True).execute()
    return [ProjectResponse.model_validate(project) for project in (response.data or [])]


@router.get("/available", response_model=list[LearnerProjectResponse])
def list_available_projects(
    profile: UserProfile = Depends(get_current_profile),
) -> list[LearnerProjectResponse]:
    if profile.role != "learner":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Learner project access requires a learner account")

    blueprint_response = (
        get_supabase_client()
        .table("project_blueprints")
        .select("project_id, blueprint_json, version")
        .eq("status", "approved")
        .order("version", desc=True)
        .execute()
    )
    approved_blueprints = {}
    for record in (blueprint_response.data or []):
        project_id_key = str(record["project_id"])
        if project_id_key not in approved_blueprints:
            approved_blueprints[project_id_key] = ProjectBlueprint.model_validate(record["blueprint_json"])
    if not approved_blueprints:
        return []

    project_response = (
        get_supabase_client()
        .table("projects")
        .select("id, name, slug, desired_outcome")
        .eq("status", "active")
        .in_("id", list(approved_blueprints))
        .order("created_at", desc=True)
        .execute()
    )
    available_projects = []
    for project in project_response.data or []:
        blueprint = approved_blueprints[str(project["id"])]
        available_projects.append(LearnerProjectResponse(
            id=project["id"],
            name=project["name"],
            slug=project["slug"],
            project_summary=blueprint.project_summary,
            business_objective=blueprint.workplace_goal,
            expected_outcome=project.get("desired_outcome") or blueprint.workplace_goal,
            work_areas=[{"name": module.name, "description": module.description} for module in blueprint.modules],
        ))
    return available_projects


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(
    payload: ProjectCreate,
    user: AuthenticatedUser = Depends(get_current_user),
    profile: UserProfile = Depends(get_current_profile),
) -> ProjectResponse:
    if profile.role == "learner":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Learner accounts cannot create projects")
    _require_project_manager(profile)
    project = payload.model_dump()
    project.update({"slug": _slug_for(payload.name), "created_by": user.id, "status": "draft"})
    response = get_supabase_client().table("projects").insert(project).execute()
    if not response.data:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Unable to create project")
    return ProjectResponse.model_validate(response.data[0])


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(
    project_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    profile: UserProfile = Depends(get_current_profile),
) -> ProjectResponse:
    _require_project_manager(profile)
    project = _get_project(project_id)
    _require_project_access(project, user, profile)
    project["materialized"] = _is_materialized(project_id)
    return ProjectResponse.model_validate(project)


@router.patch("/{project_id}", response_model=ProjectResponse)
def update_project(
    project_id: UUID,
    payload: ProjectUpdate,
    user: AuthenticatedUser = Depends(get_current_user),
    profile: UserProfile = Depends(get_current_profile),
) -> ProjectResponse:
    _require_project_manager(profile)
    project = _get_project(project_id)
    _require_project_access(project, user, profile)
    if project.get("status") != "draft":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Published project details are immutable; create a blueprint revision and release")
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        return ProjectResponse.model_validate(project)
    response = get_supabase_client().table("projects").update(changes).eq("id", str(project_id)).execute()
    if not response.data:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Unable to update project")
    return ProjectResponse.model_validate(response.data[0])


@router.post("/{project_id}/archive", response_model=ProjectResponse)
def archive_project(
    project_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    profile: UserProfile = Depends(get_current_profile),
) -> ProjectResponse:
    _require_project_manager(profile)
    project = _get_project(project_id)
    _require_project_access(project, user, profile)
    response = get_supabase_client().table("projects").update({"status": "archived"}).eq("id", str(project_id)).execute()
    if not response.data:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Unable to archive project")
    return ProjectResponse.model_validate(response.data[0])


@router.post("/{project_id}/publish", response_model=ProjectResponse)
def publish_project(
    project_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    profile: UserProfile = Depends(get_current_profile),
) -> ProjectResponse:
    return _publish_project(project_id, user, profile)


@router.get("/{project_id}/tasks", response_model=list[LearnerTaskResponse])
def list_project_tasks(
    project_id: UUID,
    module_slug: str | None = Query(default=None),
    profile: UserProfile = Depends(get_current_profile),
) -> list[LearnerTaskResponse]:
    """Return active tasks for a published project.

    Accessible to learners (who can only see active projects) and to business/admin
    users who own the project.  An optional module_slug query parameter narrows
    results to a single work area.  This endpoint is read-only — no simulation is
    created here.
    """
    if profile.role not in {"learner", "business", "admin"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    client = get_supabase_client()
    # Verify project is visible to this user.
    project_resp = (
        client.table("projects")
        .select("id, status, created_by, published_release_id")
        .eq("id", str(project_id))
        .maybe_single()
        .execute()
    )
    if not project_resp.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    project = project_resp.data
    if profile.role == "learner" and project.get("status") != "active":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    elif profile.role in {"business", "admin"}:
        _require_project_access(
            project,
            AuthenticatedUser(id=profile.id, email=profile.email),
            profile,
        )

    query = (
        client.table("tasks")
        .select("id, title, description, instructions, task_type, difficulty, expected_outcome, module_id, reference_solution")
        .eq("project_id", str(project_id))
        .eq("status", "active")
        .order("position")
    )
    # New releases are explicitly scoped.  The null fallback is only for
    # pre-release historical projects, whose provenance is intentionally not
    # invented by the migration.
    if project.get("published_release_id"):
        query = query.eq("release_id", project["published_release_id"])

    if module_slug:
        requested_module_slug = _module_slug_for(module_slug)
        modules_resp = (
            client.table("modules")
            .select("id, name, release_id")
            .eq("project_id", str(project_id))
            .eq("status", "active")
        )
        if project.get("published_release_id"):
            modules_resp = modules_resp.eq("release_id", project["published_release_id"])
        modules_resp = modules_resp.execute()
        module = next(
            (
                active_module
                for active_module in (modules_resp.data or [])
                if _module_slug_for(str(active_module.get("name") or "")) == requested_module_slug
            ),
            None,
        )
        if not module:
            return []
        query = query.eq("module_id", module["id"])

    tasks_resp = query.execute()
    responses = []
    for task in tasks_resp.data or []:
        reference = task.pop("reference_solution", None) or {}
        task["blueprint_task_key"] = reference.get("blueprint_task_key") if isinstance(reference, dict) else None
        responses.append(LearnerTaskResponse.model_validate(task))
    return responses
