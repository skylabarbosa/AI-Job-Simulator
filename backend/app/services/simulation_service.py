"""Simulation service — creates or resumes a learner simulation.

Architecture note:
  STATIC DEFINITION TABLES: projects, project_blueprints, modules, tasks
  RUNTIME TABLES:            simulations, submissions, evaluations, user_skills

A simulation is a learner's work session for a project.  Each learner gets
their own simulation row; two learners working on the same project/task
always produce two distinct simulation records.

Gemini/LLM calls: ZERO — this module never calls any LLM.
"""

from uuid import UUID

from fastapi import HTTPException, status

from app.db.client import get_supabase_client
from app.schemas.simulations import SimulationContext


def _require_active_project_with_blueprint(client, project_id: UUID) -> dict:
    """Verify the project is published (active) and has an approved blueprint.

    Returns the project record on success; raises HTTPException otherwise.
    """
    project_resp = (
        client.table("projects")
        .select("id, name, status, published_release_id")
        .eq("id", str(project_id))
        .eq("status", "active")
        .maybe_single()
        .execute()
    )
    if not project_resp.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found or not yet published",
        )

    blueprint_resp = (
        client.table("project_blueprints")
        .select("id")
        .eq("project_id", str(project_id))
        .eq("status", "approved")
        .limit(1)
        .execute()
    )
    if not blueprint_resp.data:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Project does not have an approved blueprint",
        )

    return project_resp.data


def _require_task_in_project(client, task_id: UUID, project_id: UUID, project: dict) -> dict:
    """Verify the task belongs to the project and is active.

    Also verifies the task belongs to a valid (active) module in that project.
    Returns the task record on success; raises HTTPException otherwise.
    """
    task_resp = (
        client.table("tasks")
        .select("id, project_id, release_id, module_id, title, description, instructions, task_type, difficulty, expected_outcome, status")
        .eq("id", str(task_id))
        .eq("project_id", str(project_id))
        .eq("status", "active")
        .maybe_single()
        .execute()
    )
    if not task_resp.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found in this project",
        )

    task = task_resp.data
    published_release_id = project.get("published_release_id")
    if published_release_id and str(task.get("release_id")) != str(published_release_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task is not part of the published project release",
        )
    if not task.get("module_id"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Task is not assigned to a work area",
        )

    # Verify the module belongs to this project and is active.
    module_resp = (
        client.table("modules")
        .select("id, name, release_id")
        .eq("id", str(task["module_id"]))
        .eq("project_id", str(project_id))
        .eq("status", "active")
        .maybe_single()
        .execute()
    )
    if not module_resp.data:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Task work area is not active in this project",
        )
    if published_release_id and str(module_resp.data.get("release_id")) != str(published_release_id):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Task work area is not part of the published project release",
        )

    task["module_name"] = module_resp.data["name"]
    return task


def _build_context(
    *,
    simulation: dict,
    project: dict,
    task: dict,
    task_id: UUID,
    activity_state: str,
) -> SimulationContext:
    return SimulationContext(
        simulation_id=simulation["id"],
        project_id=simulation["project_id"],
        project_name=project["name"],
        task_id=task_id,
        task_title=task["title"],
        task_description=task.get("description"),
        task_instructions=task.get("instructions"),
        task_expected_outcome=task.get("expected_outcome"),
        task_type=task["task_type"],
        task_difficulty=task["difficulty"],
        module_id=task["module_id"],
        module_name=task["module_name"],
        status=simulation["status"],
        started_at=simulation["started_at"],
        activity_state=activity_state,
    )


def start_or_resume_simulation(
    *,
    learner_id: str,
    project_id: UUID,
    task_id: UUID,
) -> SimulationContext:
    """Start a new simulation or resume the existing active one for this learner+project.

    Security invariants (enforced here AND by database RLS):
      - learner_id always comes from the authentication context, never from the
        request body.
      - Only learners with role='learner' can reach this service (enforced by
        the router dependency before calling this function).
      - RLS on simulations table enforces learner_id = auth.uid() for insert/update.

    Idempotency:
      - If an 'active' simulation already exists for this learner+project, it is
        reused and current_task_id is updated to the requested task.
      - Only one insert per learner+project pair in 'active' status at a time.

    Gemini/LLM calls: ZERO.
    """
    client = get_supabase_client()

    # 1. Verify project is published and has an approved blueprint.
    project = _require_active_project_with_blueprint(client, project_id)

    # 2. Verify the task is active and belongs to this project's active module.
    task = _require_task_in_project(client, task_id, project_id, project)

    # 3. Find an existing active/resumable simulation for this learner+project.
    existing_resp = (
        client.table("simulations")
        .select("id, learner_id, project_id, status, started_at")
        .eq("learner_id", learner_id)
        .eq("project_id", str(project_id))
        .in_("status", ["active", "paused"])
        .order("started_at", desc=True)
        .limit(1)
        .execute()
    )

    if existing_resp.data:
        # Resume: update current_task_id to the newly requested task.
        sim = existing_resp.data[0]
        update_resp = (
            client.table("simulations")
            .update({"current_task_id": str(task_id), "status": "active"})
            .eq("id", sim["id"])
            .eq("learner_id", learner_id)
            .execute()
        )
        row = update_resp.data[0] if update_resp.data else sim
        return _build_context(
            simulation=row,
            project=project,
            task=task,
            task_id=task_id,
            activity_state="resumed",
        )

    # 4. No resumable simulation — create a new one.
    try:
        insert_resp = (
            client.table("simulations")
            .insert(
                {
                    "learner_id": learner_id,
                    "project_id": str(project_id),
                    "current_task_id": str(task_id),
                    "status": "active",
                }
            )
            .execute()
        )
    except Exception as error:
        # The partial unique index closes the race between the lookup and
        # insert. Recover the concurrent winner as an idempotent resume.
        existing_resp = (
            client.table("simulations")
            .select("id, learner_id, project_id, status, started_at")
            .eq("learner_id", learner_id)
            .eq("project_id", str(project_id))
            .in_("status", ["active", "paused"])
            .order("started_at", desc=True)
            .limit(1)
            .execute()
        )
        if not existing_resp.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Unable to create simulation session",
            ) from error
        sim = existing_resp.data[0]
        update_resp = (
            client.table("simulations")
            .update({"current_task_id": str(task_id), "status": "active"})
            .eq("id", sim["id"])
            .eq("learner_id", learner_id)
            .execute()
        )
        row = update_resp.data[0] if update_resp.data else sim
        return _build_context(
            simulation=row,
            project=project,
            task=task,
            task_id=task_id,
            activity_state="resumed",
        )
    if not insert_resp.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to create simulation session",
        )

    row = insert_resp.data[0]
    return _build_context(
        simulation=row,
        project=project,
        task=task,
        task_id=task_id,
        activity_state="started",
    )
