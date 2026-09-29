"""Generic learner submission pipeline."""

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status

from app.db.client import get_supabase_client
from app.schemas.submissions import SkillEvidence, SubmissionCreate, SubmissionResult
from app.services.evaluation_service import (
    EvaluationContext,
    EvaluationResult,
    dedupe_skill_evidence,
    evaluate_deterministically,
    evaluate_semantically,
)
from app.services.performance_service import refresh_simulation_progress
from app.services.sql_execution_service import execute_task_sql


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _require_active_project_with_blueprint(client, project_id: UUID) -> dict[str, Any]:
    project_resp = (
        client.table("projects")
        .select("id, name, status")
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


def _load_task(client, project_id: UUID, task_id: UUID) -> dict[str, Any]:
    task_resp = (
        client.table("tasks")
        .select("id, project_id, module_id, title, description, instructions, task_type, difficulty, expected_outcome, reference_solution, status")
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
    return task_resp.data


def _load_simulation(client, learner_id: str, project_id: UUID, task_id: UUID) -> dict[str, Any]:
    simulation_resp = (
        client.table("simulations")
        .select("id, learner_id, project_id, current_task_id, status")
        .eq("learner_id", learner_id)
        .eq("project_id", str(project_id))
        .in_("status", ["active", "paused"])
        .order("started_at", desc=True)
        .limit(1)
        .execute()
    )
    if not simulation_resp.data:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Start this task before submitting work",
        )

    simulation = simulation_resp.data[0]
    if str(simulation.get("current_task_id")) != str(task_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Submit work for the task currently active in your simulation",
        )
    return simulation


def _next_attempt(client, simulation_id: str, task_id: UUID) -> int:
    existing_resp = (
        client.table("submissions")
        .select("attempt_number")
        .eq("simulation_id", simulation_id)
        .eq("task_id", str(task_id))
        .order("attempt_number", desc=True)
        .limit(1)
        .execute()
    )
    if existing_resp.data:
        return int(existing_resp.data[0].get("attempt_number", 0)) + 1
    return 1


def _submission_content(payload: SubmissionCreate) -> dict[str, Any]:
    content = dict(payload.content or {})
    if payload.response is not None:
        content["response"] = payload.response.strip()
    content.pop("learner_id", None)
    return content


def _load_rubric(client, task_id: UUID) -> dict[str, Any] | None:
    rubric_resp = (
        client.table("rubrics")
        .select("id, criteria, scoring_guidance, max_score, status")
        .eq("task_id", str(task_id))
        .eq("status", "active")
        .order("version", desc=True)
        .limit(1)
        .execute()
    )
    return rubric_resp.data[0] if rubric_resp.data else None


def _load_relationships(client, task_id: UUID) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    competencies = (
        client.table("task_competencies")
        .select("competency_id")
        .eq("task_id", str(task_id))
        .execute()
        .data
        or []
    )
    concepts = (
        client.table("task_concepts")
        .select("concept_id")
        .eq("task_id", str(task_id))
        .execute()
        .data
        or []
    )
    return competencies, concepts


def _insert_evaluation(client, submission_id: str, result: EvaluationResult) -> str | None:
    if result.evaluation_type not in {"deterministic", "ai"}:
        return None
    payload = result.safe_payload()
    response = client.table("evaluations").insert(
        {
            "submission_id": submission_id,
            "evaluation_type": result.evaluation_type,
            "status": "completed" if result.status in {"passed", "failed"} else "pending",
            "score": 100 if result.status == "passed" else (0 if result.status == "failed" else None),
            "deterministic_result": payload if result.evaluation_type == "deterministic" else None,
            "ai_result": payload if result.evaluation_type == "ai" else None,
            "feedback": result.summary,
            "evaluated_at": _now() if result.status in {"passed", "failed"} else None,
        }
    ).execute()
    if response.data:
        return str(response.data[0].get("id"))
    return None


def _score_for_level(level: str) -> tuple[int, str]:
    if level == "demonstrated":
        return 80, "proficient"
    if level == "developing":
        return 45, "developing"
    return 10, "novice"


def _update_skill(client, learner_id: str, evidence: SkillEvidence) -> None:
    field = "concept_id" if evidence.concept_id else "competency_id"
    value = str(evidence.concept_id or evidence.competency_id)
    if not value:
        return
    score, level = _score_for_level(evidence.level)
    existing = (
        client.table("user_skills")
        .select("id, current_score")
        .eq("learner_id", learner_id)
        .eq(field, value)
        .limit(1)
        .execute()
        .data
    )
    existing_row = existing[0] if existing else None
    if existing_row:
        previous_score = float(existing_row.get("current_score") or 0)
        # `user_skills` is the compact demonstrated-mastery projection used by
        # adaptation. A weaker later attempt must not erase durable evidence;
        # the per-submission/evaluation records retain current performance.
        demonstrated_score = max(previous_score, score)
        client.table("user_skills").update(
            {
                "previous_score": previous_score,
                "current_score": demonstrated_score,
                "level": _highest_skill_level(existing_row.get("level"), level),
                "last_evaluated_at": _now(),
            }
        ).eq("id", existing_row["id"]).execute()
        return
    client.table("user_skills").insert(
        {
            "learner_id": learner_id,
            field: value,
            "current_score": score,
            "level": level,
            "last_evaluated_at": _now(),
        }
    ).execute()


def _highest_skill_level(existing: str | None, incoming: str) -> str:
    levels = {"novice": 0, "developing": 1, "proficient": 2, "advanced": 3}
    return existing if levels.get(str(existing), 0) >= levels.get(incoming, 0) else incoming


def _update_skill_evidence(client, learner_id: str, result: EvaluationResult) -> None:
    result.skill_evidence = dedupe_skill_evidence(result.skill_evidence)
    for evidence in result.skill_evidence:
        _update_skill(client, learner_id, evidence)


def _to_submission_result(submission_id: str, evaluation_id: str | None, result: EvaluationResult, execution: dict[str, Any] | None = None) -> SubmissionResult:
    return SubmissionResult(
        submission_id=UUID(str(submission_id)),
        evaluation_id=UUID(str(evaluation_id)) if evaluation_id else None,
        validation_status=result.status,  # type: ignore[arg-type]
        checks=result.learner_checks(),
        message=result.learner_message(),
        strengths=list(dict.fromkeys(result.strengths)),
        areas_for_improvement=list(dict.fromkeys(result.areas_for_improvement)),
        evidence=list(dict.fromkeys(result.evidence)),
        skill_evidence=dedupe_skill_evidence(result.skill_evidence),
        **(execution or {}),
    )


def validate_task_work(
    *,
    learner_id: str,
    project_id: UUID,
    task_id: UUID,
    payload: SubmissionCreate,
) -> SubmissionResult:
    client = get_supabase_client()

    _require_active_project_with_blueprint(client, project_id)
    task = _load_task(client, project_id, task_id)
    _load_simulation(client, learner_id, project_id, task_id)
    content = _submission_content(payload)

    rubric = _load_rubric(client, task_id)
    competencies, concepts = _load_relationships(client, task_id)
    context = EvaluationContext(
        task=task,
        rubric=rubric,
        competencies=competencies,
        concepts=concepts,
        content=content,
    )

    result = evaluate_deterministically(context)
    response = _to_submission_result(str(task_id), None, result)
    if str(task.get("task_type", "")).lower() != "sql":
        return response
    query = str(content.get("sql") or payload.response or "")
    execution = execute_task_sql(project_id=str(project_id), task=task, query=query)
    response.execution_status = execution["execution_status"]
    response.columns = execution["columns"]
    response.rows = execution["rows"]
    response.row_count = execution["row_count"]
    response.displayed_row_count = execution["displayed_row_count"]
    response.truncated = execution["truncated"]
    response.execution_time_ms = execution["execution_time_ms"]
    response.message = "Query ran successfully."
    return response


def submit_task_work(
    *,
    learner_id: str,
    project_id: UUID,
    task_id: UUID,
    payload: SubmissionCreate,
) -> SubmissionResult:
    client = get_supabase_client()

    _require_active_project_with_blueprint(client, project_id)
    task = _load_task(client, project_id, task_id)
    simulation = _load_simulation(client, learner_id, project_id, task_id)
    content = _submission_content(payload)
    next_attempt = _next_attempt(client, simulation["id"], task_id)

    insert_resp = (
        client.table("submissions")
        .insert(
            {
                "simulation_id": simulation["id"],
                "task_id": str(task_id),
                "learner_id": learner_id,
                "attempt_number": next_attempt,
                "content": content,
                "status": "submitted",
                "submitted_at": _now(),
            }
        )
        .execute()
    )
    if not insert_resp.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to save submission",
        )
    submission = insert_resp.data[0]

    rubric = _load_rubric(client, task_id)
    competencies, concepts = _load_relationships(client, task_id)
    context = EvaluationContext(
        task=task,
        rubric=rubric,
        competencies=competencies,
        concepts=concepts,
        content=content,
    )

    deterministic_result = evaluate_deterministically(context)
    result = deterministic_result
    evaluation_id = _insert_evaluation(client, submission["id"], deterministic_result)
    _update_skill_evidence(client, learner_id, deterministic_result)

    if deterministic_result.needs_semantic:
        result = evaluate_semantically(context)
        if not result.checks:
            result.checks = deterministic_result.checks
        if not result.evidence:
            result.evidence = deterministic_result.evidence
        evaluation_id = _insert_evaluation(client, submission["id"], result)
        _update_skill_evidence(client, learner_id, result)

    try:
        refresh_simulation_progress(learner_id=learner_id, project_id=project_id)
    except Exception:
        # Evaluation and evidence are durable even when progress refresh is unavailable.
        pass

    return _to_submission_result(submission["id"], evaluation_id, result)
