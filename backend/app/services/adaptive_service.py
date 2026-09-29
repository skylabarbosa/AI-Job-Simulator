"""Load scoped Phase 3 evidence and produce a presentation-only decision."""

from typing import Any
from uuid import UUID

from fastapi import HTTPException, status

from app.db.client import get_supabase_client
from app.services.adaptive_engine import EvidenceSnapshot, TaskMetadata, decide_presentation
from app.services.simulation_service import _require_active_project_with_blueprint


def _load_task(client: Any, project_id: UUID, task_id: UUID) -> dict[str, Any]:
    response = (
        client.table("tasks")
        .select("id, project_id, task_type, difficulty, status")
        .eq("id", str(task_id))
        .eq("project_id", str(project_id))
        .eq("status", "active")
        .maybe_single()
        .execute()
    )
    if not response.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found in this project")
    return response.data


def _uuid(value: Any) -> UUID | None:
    try:
        return UUID(str(value))
    except (TypeError, ValueError):
        return None


def _load_evidence(client: Any, learner_id: str, project_id: UUID, relevant: set[UUID]) -> EvidenceSnapshot:
    snapshot = EvidenceSnapshot()
    if not relevant:
        return snapshot

    skills = (
        client.table("user_skills")
        .select("competency_id, concept_id, current_score")
        .eq("learner_id", learner_id)
        .execute()
        .data
        or []
    )
    for skill in skills:
        skill_id = _uuid(skill.get("concept_id") or skill.get("competency_id"))
        if skill_id in relevant:
            snapshot.skill_scores[skill_id] = float(skill.get("current_score") or 0)

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
        return snapshot

    submissions = (
        client.table("submissions")
        .select("id, simulation_id, learner_id, status")
        .eq("learner_id", learner_id)
        .execute()
        .data
        or []
    )
    submission_ids = [str(row["id"]) for row in submissions if str(row.get("simulation_id")) in simulation_ids and row.get("status") == "submitted"]
    if not submission_ids:
        return snapshot
    evaluations = client.table("evaluations").select("*").in_("submission_id", submission_ids).execute().data or []
    for evaluation in evaluations:
        if evaluation.get("status") != "completed":
            continue
        payload = evaluation.get("ai_result") or evaluation.get("deterministic_result") or {}
        passed = payload.get("status") == "passed"
        for item in payload.get("skill_evidence") or []:
            evidence_id = _uuid(item.get("concept_id") or item.get("competency_id"))
            if evidence_id not in relevant:
                continue
            level = str(item.get("level") or "insufficient_evidence")
            if level == "demonstrated" or passed:
                snapshot.demonstrated_ids.add(evidence_id)
            elif level == "developing":
                snapshot.developing_ids.add(evidence_id)
            if level in {"developing", "insufficient_evidence"} or not passed:
                snapshot.failure_counts[evidence_id] = snapshot.failure_counts.get(evidence_id, 0) + 1
    return snapshot


def get_adaptive_decision(*, learner_id: str, project_id: UUID, task_id: UUID):
    client = get_supabase_client()
    _require_active_project_with_blueprint(client, project_id)
    task = _load_task(client, project_id, task_id)
    competency_rows = client.table("task_competencies").select("competency_id").eq("task_id", str(task_id)).execute().data or []
    concept_rows = client.table("task_concepts").select("concept_id").eq("task_id", str(task_id)).execute().data or []
    competency_ids = tuple(filter(None, (_uuid(row.get("competency_id")) for row in competency_rows)))
    concept_ids = tuple(filter(None, (_uuid(row.get("concept_id")) for row in concept_rows)))
    metadata = TaskMetadata(
        project_id=project_id,
        task_id=task_id,
        task_type=str(task.get("task_type") or "other"),
        difficulty=str(task.get("difficulty") or "beginner"),
        concept_ids=concept_ids,
        competency_ids=competency_ids,
    )
    return decide_presentation(
        task=metadata,
        evidence=_load_evidence(client, learner_id, project_id, set(concept_ids) | set(competency_ids)),
    )