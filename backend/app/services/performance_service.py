"""Learner-safe performance aggregation over the existing runtime tables."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import HTTPException, status

from app.db.client import get_supabase_client
from app.schemas.performance import (
    EvaluationResponse,
    LearnerProgressResponse,
    LearnerProgressTotals,
    LearnerProjectProgress,
    LearnerRecentActivity,
    LearnerSkillSummary,
    LearnerSkillTotals,
    LearnerSkillsResponse,
    ProjectPerformanceResponse,
    SkillProgress,
    TaskProgress,
)


def _require_published_project(client: Any, project_id: UUID) -> dict:
    project = (
        client.table("projects")
        .select("id, status, published_release_id")
        .eq("id", str(project_id))
        .maybe_single()
        .execute()
    )
    if not project.data or project.data.get("status") != "active":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project.data


def _all_submissions(client: Any, learner_id: str, project_id: UUID) -> dict[str, list[dict]]:
    """Return every submitted submission for the learner in this project, grouped by task_id."""
    simulations = (
        client.table("simulations")
        .select("id")
        .eq("learner_id", learner_id)
        .eq("project_id", str(project_id))
        .execute()
        .data
        or []
    )
    simulation_ids = {str(row["id"]) for row in simulations}
    if not simulation_ids:
        return {}
    submissions = (
        client.table("submissions")
        .select("id, task_id, simulation_id, attempt_number, status, submitted_at")
        .eq("learner_id", learner_id)
        .execute()
        .data
        or []
    )
    by_task: dict[str, list[dict]] = {}
    for submission in submissions:
        if str(submission.get("simulation_id")) not in simulation_ids or submission.get("status") != "submitted":
            continue
        task_id = str(submission["task_id"])
        by_task.setdefault(task_id, []).append(submission)
    # Sort each task's submissions by attempt_number so the latest is last.
    for task_id in by_task:
        by_task[task_id].sort(key=lambda s: int(s.get("attempt_number", 0)))
    return by_task


def _evaluation_map(client: Any, submission_ids: list[str]) -> dict[str, list[dict]]:
    if not submission_ids:
        return {}
    evaluations = (
        client.table("evaluations")
        .select("*")
        .in_("submission_id", submission_ids)
        .execute()
        .data
        or []
    )
    result: dict[str, list[dict]] = {}
    for evaluation in evaluations:
        result.setdefault(str(evaluation["submission_id"]), []).append(evaluation)
    return result


def _payload(evaluation: dict) -> dict:
    return evaluation.get("ai_result") or evaluation.get("deterministic_result") or {}


def _passed(evaluations: list[dict]) -> dict | None:
    completed = [item for item in evaluations if item.get("status") == "completed"]
    for evaluation in reversed(completed):
        if _payload(evaluation).get("status") == "passed":
            return evaluation
    return None


def _any_passed(task_submissions: list[dict], eval_map: dict[str, list[dict]]) -> dict | None:
    """Check ALL submissions for the task and return the first passing evaluation found."""
    for submission in task_submissions:
        evaluations = eval_map.get(str(submission["id"]), [])
        result = _passed(evaluations)
        if result is not None:
            return result
    return None


def get_project_performance(
    *, learner_id: str, project_id: UUID, include_skill_details: bool = True
) -> ProjectPerformanceResponse:
    client = get_supabase_client()
    project = _require_published_project(client, project_id)
    task_query = (
        client.table("tasks")
        .select("id, title")
        .eq("project_id", str(project_id))
        .eq("status", "active")
    )
    if project.get("published_release_id"):
        task_query = task_query.eq("release_id", project["published_release_id"])
    tasks = task_query.order("position").execute().data or []
    all_subs = _all_submissions(client, learner_id, project_id)
    # Collect all submission IDs to load evaluations in one query.
    all_submission_ids = [str(s["id"]) for subs in all_subs.values() for s in subs]
    eval_map = _evaluation_map(client, all_submission_ids)
    task_progress = []
    completed_task_ids: set[str] = set()
    for task in tasks:
        task_id = str(task["id"])
        task_submissions = all_subs.get(task_id, [])
        latest_submission = task_submissions[-1] if task_submissions else None
        # Check ALL submissions for a passing evaluation (once passed, stays passed).
        passed = _any_passed(task_submissions, eval_map)
        if passed:
            completed_task_ids.add(task_id)
        # Display metrics come from the latest submission.
        latest_evals = eval_map.get(str(latest_submission["id"]), []) if latest_submission else []
        latest_evaluation = latest_evals[-1] if latest_evals else None
        task_progress.append(TaskProgress(
            task_id=task["id"],
            title=task["title"],
            completed=passed is not None,
            attempts=int(latest_submission.get("attempt_number", 0)) if latest_submission else 0,
            latest_evaluation_status=latest_evaluation.get("status") if latest_evaluation else None,
            latest_score=float(latest_evaluation["score"]) if latest_evaluation and latest_evaluation.get("score") is not None else None,
        ))

    competencies: list[SkillProgress] = []
    concepts: list[SkillProgress] = []
    if include_skill_details:
        skills = (
            client.table("user_skills")
            .select("*")
            .eq("learner_id", learner_id)
            .execute()
            .data
            or []
        )
        task_ids = [str(task["id"]) for task in tasks]
        task_competencies = (
            client.table("task_competencies").select("competency_id").in_("task_id", task_ids).execute().data or []
        ) if task_ids else []
        task_concepts = (
            client.table("task_concepts").select("concept_id").in_("task_id", task_ids).execute().data or []
        ) if task_ids else []
        competency_ids = {str(row["competency_id"]) for row in task_competencies}
        concept_ids = {str(row["concept_id"]) for row in task_concepts}
        competency_names = {str(row["id"]): row.get("name", "Competency") for row in (client.table("competencies").select("id, name").execute().data or [])}
        concept_names = {str(row["id"]): row.get("name", "Concept") for row in (client.table("concepts").select("id, name").execute().data or [])}

        def skill_items(kind: str, ids: set[str], names: dict[str, str]) -> list[SkillProgress]:
            return [SkillProgress(id=row[f"{kind}_id"], name=names.get(str(row[f"{kind}_id"]), kind.title()), kind=kind, level=row.get("level", "novice"), score=float(row.get("current_score", 0)), demonstrated=row.get("level") in {"proficient", "advanced"}) for row in skills if row.get(f"{kind}_id") and str(row[f"{kind}_id"]) in ids]

        competencies = skill_items("competency", competency_ids, competency_names)
        concepts = skill_items("concept", concept_ids, concept_names)

    total = len(task_progress)
    completed_count = len(completed_task_ids)
    progress = round(completed_count / total * 100, 2) if total else 0
    return ProjectPerformanceResponse(
        project_id=project_id,
        total_tasks=total,
        completed_tasks=completed_count,
        progress=progress,
        completed=total > 0 and completed_count == total,
        tasks=task_progress,
        competencies=competencies,
        concepts=concepts,
    )


def get_task_evaluation(*, learner_id: str, project_id: UUID, task_id: UUID) -> EvaluationResponse | None:
    performance = get_project_performance(learner_id=learner_id, project_id=project_id)
    task = next((item for item in performance.tasks if item.task_id == task_id), None)
    if not task or task.attempts == 0:
        return None
    client = get_supabase_client()
    task_subs = _all_submissions(client, learner_id, project_id).get(str(task_id), [])
    if not task_subs:
        return None
    latest = task_subs[-1]
    records = _evaluation_map(client, [str(latest["id"])])
    evaluation = records.get(str(latest["id"]), [])[-1:] 
    if not evaluation:
        return None
    row = evaluation[0]
    payload = _payload(row)
    return EvaluationResponse(
        submission_id=latest["id"], evaluation_type=row["evaluation_type"], status=row["status"], score=float(row["score"]) if row.get("score") is not None else None,
        feedback=row.get("feedback"), evaluated_at=row.get("evaluated_at"), strengths=payload.get("strengths", []), areas_for_improvement=payload.get("areas_for_improvement", []), evidence=payload.get("evidence", []),
    )


def get_learner_progress(*, learner_id: str) -> LearnerProgressResponse:
    """Return the learner's aggregate project progress without duplicating runtime tables."""
    client = get_supabase_client()
    simulations = (
        client.table("simulations")
        .select("id, project_id, status, started_at, completed_at, progress")
        .eq("learner_id", learner_id)
        .order("started_at", desc=True)
        .execute()
        .data
        or []
    )
    if not simulations:
        return LearnerProgressResponse(
            projects=[],
            totals=LearnerProgressTotals(),
            recent_activity=[],
        )

    unique_project_ids = []
    seen_project_ids: set[str] = set()
    for simulation in simulations:
        project_id = simulation.get("project_id")
        if not project_id or str(project_id) in seen_project_ids:
            continue
        seen_project_ids.add(str(project_id))
        unique_project_ids.append(str(project_id))

    project_rows = {}
    if unique_project_ids:
        project_response = (
            client.table("projects")
            .select("id, name, status")
            .in_("id", unique_project_ids)
            .execute()
        )
        project_rows = {str(row["id"]): row for row in (project_response.data or [])}

    project_entries: list[LearnerProjectProgress] = []
    simulation_by_project: dict[str, list[dict]] = {}
    for simulation in simulations:
        project_id = str(simulation.get("project_id") or "")
        if not project_id:
            continue
        simulation_by_project.setdefault(project_id, []).append(simulation)

    for project_id in unique_project_ids:
        project_row = project_rows.get(project_id, {})
        project_simulations = simulation_by_project.get(project_id, [])
        latest_simulation = project_simulations[0] if project_simulations else {}
        project_status = latest_simulation.get("status") or project_row.get("status") or "active"
        completed_flag = bool(latest_simulation.get("completed_at") or project_status == "completed")
        project_progress = float(latest_simulation.get("progress") or 0)
        try:
            project_performance = get_project_performance(
                learner_id=learner_id,
                project_id=UUID(project_id),
                include_skill_details=False,
            )
            total_tasks = project_performance.total_tasks
            completed_tasks = project_performance.completed_tasks
            project_progress = project_performance.progress
            completed_flag = completed_flag or project_performance.completed
        except HTTPException:
            total_tasks = 0
            completed_tasks = 0
        project_entries.append(
            LearnerProjectProgress(
                project_id=UUID(project_id),
                project_name=project_row.get("name") or "Project",
                status=project_status,
                total_tasks=total_tasks,
                completed_tasks=completed_tasks,
                progress=project_progress,
                completed=completed_flag,
            )
        )

    project_entries.sort(key=lambda item: item.project_name or "", reverse=False)
    totals = LearnerProgressTotals(
        projects_started=len(project_entries),
        completed_projects=sum(1 for project in project_entries if project.completed),
        total_tasks=sum(project.total_tasks for project in project_entries),
        completed_tasks=sum(project.completed_tasks for project in project_entries),
        average_progress=round(
            sum(project.progress for project in project_entries) / len(project_entries),
            2,
        ) if project_entries else 0.0,
    )

    submission_rows = (
        client.table("submissions")
        .select("id, task_id, simulation_id, status, submitted_at, attempt_number")
        .eq("learner_id", learner_id)
        .order("submitted_at", desc=True)
        .limit(10)
        .execute()
        .data
        or []
    )
    simulation_project_map = {str(row["id"]): str(row["project_id"]) for row in simulations if row.get("project_id")}
    task_name_map: dict[str, str] = {}
    if submission_rows:
        task_ids = {str(row["task_id"]) for row in submission_rows if row.get("task_id")}
        if task_ids:
            task_results = (
                client.table("tasks")
                .select("id, title")
                .in_("id", sorted(task_ids))
                .execute()
                .data
                or []
            )
            task_name_map = {str(task["id"]): task.get("title") or "Task" for task in task_results}

    recent_activity: list[LearnerRecentActivity] = []
    for submission in submission_rows:
        project_id = simulation_project_map.get(str(submission.get("simulation_id")))
        if not project_id:
            continue
        task_id = submission.get("task_id")
        task_title = task_name_map.get(str(task_id), "Task")
        recent_activity.append(
            LearnerRecentActivity(
                project_id=UUID(project_id),
                project_name=project_rows.get(project_id, {}).get("name") or "Project",
                task_id=UUID(task_id) if task_id else None,
                task_title=task_title,
                status=submission.get("status") or "submitted",
                submitted_at=submission.get("submitted_at"),
                attempt_number=int(submission.get("attempt_number") or 0),
            )
        )

    return LearnerProgressResponse(projects=project_entries, totals=totals, recent_activity=recent_activity)


def get_learner_skills(*, learner_id: str) -> LearnerSkillsResponse:
    """Aggregate learner skill evidence across competency and concept records without duplicating runtime tables."""
    client = get_supabase_client()
    rows = (
        client.table("user_skills")
        .select("id, learner_id, competency_id, concept_id, current_score, level, last_evaluated_at")
        .eq("learner_id", learner_id)
        .execute()
        .data
        or []
    )
    if not rows:
        return LearnerSkillsResponse(skills=[], totals=LearnerSkillTotals())

    competency_names = {
        str(row["id"]): row.get("name") or "Competency"
        for row in (client.table("competencies").select("id, name").execute().data or [])
    }
    concept_names = {
        str(row["id"]): row.get("name") or "Concept"
        for row in (client.table("concepts").select("id, name").execute().data or [])
    }

    task_competencies = (
        client.table("task_competencies")
        .select("task_id, competency_id")
        .execute()
        .data
        or []
    )
    task_concepts = (
        client.table("task_concepts")
        .select("task_id, concept_id")
        .execute()
        .data
        or []
    )
    task_ids = {str(row["task_id"]) for row in task_competencies + task_concepts if row.get("task_id")}
    task_project_map: dict[str, str] = {}
    if task_ids:
        task_rows = (
            client.table("tasks")
            .select("id, project_id")
            .in_("id", sorted(task_ids))
            .execute()
            .data
            or []
        )
        task_project_map = {str(row["id"]): str(row["project_id"]) for row in task_rows if row.get("project_id")}

    relationship_map: dict[tuple[str, str], dict[str, set[str]]] = {}
    for row in task_competencies:
        competency_id = str(row.get("competency_id") or "")
        task_id = str(row.get("task_id") or "")
        if not competency_id or not task_id:
            continue
        relationship_map.setdefault(("competency", competency_id), {"project_ids": set(), "task_ids": set()})
        relationship_map[("competency", competency_id)]["task_ids"].add(task_id)
        project_id = task_project_map.get(task_id)
        if project_id:
            relationship_map[("competency", competency_id)]["project_ids"].add(project_id)

    for row in task_concepts:
        concept_id = str(row.get("concept_id") or "")
        task_id = str(row.get("task_id") or "")
        if not concept_id or not task_id:
            continue
        relationship_map.setdefault(("concept", concept_id), {"project_ids": set(), "task_ids": set()})
        relationship_map[("concept", concept_id)]["task_ids"].add(task_id)
        project_id = task_project_map.get(task_id)
        if project_id:
            relationship_map[("concept", concept_id)]["project_ids"].add(project_id)

    aggregated: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        kind = "competency" if row.get("competency_id") else "concept"
        entity_id = row.get("competency_id") or row.get("concept_id")
        if not entity_id:
            continue
        key = (kind, str(entity_id))
        bucket = aggregated.setdefault(
            key,
            {
                "id": entity_id,
                "name": competency_names.get(str(entity_id), concept_names.get(str(entity_id), "Skill")),
                "kind": kind,
                "level": row.get("level") or "novice",
                "score": 0.0,
                "demonstrated": False,
                "evidence_count": 0,
                "last_evaluated_at": None,
            },
        )
        bucket["score"] = max(float(bucket["score"]), float(row.get("current_score") or 0))
        bucket["evidence_count"] += 1
        if row.get("last_evaluated_at") and (not bucket["last_evaluated_at"] or row["last_evaluated_at"] > bucket["last_evaluated_at"]):
            bucket["last_evaluated_at"] = row["last_evaluated_at"]
        current_level = str(row.get("level") or "novice")
        rank = {"novice": 0, "developing": 1, "proficient": 2, "advanced": 3}
        if rank.get(current_level, 0) >= rank.get(str(bucket["level"]), 0):
            bucket["level"] = current_level
        bucket["demonstrated"] = bucket["level"] in {"proficient", "advanced"}

    summary: list[LearnerSkillSummary] = []
    for _, bucket in aggregated.items():
        kind = bucket["kind"]
        entity_id = str(bucket["id"])
        source_details = relationship_map.get((kind, entity_id), {"project_ids": set(), "task_ids": set()})
        summary.append(
            LearnerSkillSummary(
                id=UUID(str(bucket["id"])),
                name=bucket["name"],
                kind=kind,
                level=bucket["level"],
                score=float(bucket["score"]),
                demonstrated=bool(bucket["demonstrated"]),
                evidence_count=int(bucket["evidence_count"]),
                source_project_ids=[UUID(project_id) for project_id in sorted(source_details["project_ids"])],
                source_task_ids=[UUID(task_id) for task_id in sorted(source_details["task_ids"])],
                last_evaluated_at=bucket["last_evaluated_at"],
            )
        )

    summary.sort(key=lambda skill: (-float(skill.score), str(skill.name).casefold()))
    totals = LearnerSkillTotals(
        total_skills=len(summary),
        demonstrated_skills=sum(1 for skill in summary if skill.demonstrated),
        average_score=round(sum(skill.score for skill in summary) / len(summary), 2) if summary else 0.0,
    )
    return LearnerSkillsResponse(skills=summary, totals=totals)


def refresh_simulation_progress(*, learner_id: str, project_id: UUID) -> None:
    """Persist the aggregate state on the learner's existing simulation row."""
    performance = get_project_performance(learner_id=learner_id, project_id=project_id)
    client = get_supabase_client()
    simulations = (
        client.table("simulations")
        .select("id, status")
        .eq("learner_id", learner_id)
        .eq("project_id", str(project_id))
        .in_("status", ["active", "paused"])
        .execute()
        .data
        or []
    )
    for simulation in simulations:
        changes: dict[str, Any] = {"progress": performance.progress}
        if performance.completed:
            from datetime import datetime, timezone

            changes.update({"status": "completed", "completed_at": datetime.now(timezone.utc).isoformat()})
        client.table("simulations").update(changes).eq("id", simulation["id"]).execute()