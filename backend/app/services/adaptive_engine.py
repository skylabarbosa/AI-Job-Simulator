"""Deterministic presentation decisions for a required project task."""

from dataclasses import dataclass, field
from uuid import UUID

from app.schemas.adaptive import AdaptiveEvidenceSummary, AdaptivePresentationDecision


# These thresholds are the single rule configuration for Phase 4.
STRONG_SCORE_THRESHOLD = 75
REPEATED_FAILURE_THRESHOLD = 2


@dataclass(frozen=True)
class TaskMetadata:
    project_id: UUID
    task_id: UUID
    task_type: str
    difficulty: str
    concept_ids: tuple[UUID, ...] = ()
    competency_ids: tuple[UUID, ...] = ()


@dataclass
class EvidenceSnapshot:
    skill_scores: dict[UUID, float] = field(default_factory=dict)
    demonstrated_ids: set[UUID] = field(default_factory=set)
    developing_ids: set[UUID] = field(default_factory=set)
    failure_counts: dict[UUID, int] = field(default_factory=dict)


def _relevant_ids(task: TaskMetadata) -> set[UUID]:
    return set(task.concept_ids) | set(task.competency_ids)


def _summary(task: TaskMetadata, snapshot: EvidenceSnapshot) -> AdaptiveEvidenceSummary:
    relevant = _relevant_ids(task)
    failures = sum(snapshot.failure_counts.get(item, 0) for item in relevant)
    repeated = sum(
        1 for item in relevant
        if snapshot.failure_counts.get(item, 0) >= REPEATED_FAILURE_THRESHOLD
    )
    demonstrated_ids = snapshot.demonstrated_ids | {
        item for item in relevant
        if snapshot.skill_scores.get(item, 0) >= STRONG_SCORE_THRESHOLD
    }
    demonstrated = len(demonstrated_ids & relevant)
    developing = len(snapshot.developing_ids & relevant)
    return AdaptiveEvidenceSummary(
        relevant_concept_ids=list(task.concept_ids),
        relevant_competency_ids=list(task.competency_ids),
        demonstrated_evidence_count=demonstrated,
        developing_evidence_count=developing,
        relevant_failure_count=failures,
        repeated_failure_count=repeated,
        historical_mastery_preserved=demonstrated > 0,
    )


def decide_presentation(*, task: TaskMetadata, evidence: EvidenceSnapshot) -> AdaptivePresentationDecision:
    """Return presentation settings without changing task, progress, or completion."""
    relevant = _relevant_ids(task)
    summary = _summary(task, evidence)
    mastered = {
        item for item in relevant
        if evidence.skill_scores.get(item, 0) >= STRONG_SCORE_THRESHOLD
        or item in evidence.demonstrated_ids
    }
    has_repeated_failure = summary.repeated_failure_count > 0
    strong = bool(relevant) and len(mastered) == len(relevant) and not has_repeated_failure

    if has_repeated_failure:
        support = "guided"
        difficulty = "foundational"
        hints = True
        examples = True
        guided_steps = "explicit"
        explanation = "detailed"
        reason = "Repeated difficulty on relevant evidence calls for explicit support on this required task."
    elif strong:
        support = "independent"
        difficulty = "stretch"
        hints = False
        examples = False
        guided_steps = "none"
        explanation = "concise"
        reason = "Relevant concepts and competencies have demonstrated strong evidence."
    else:
        support = "moderate"
        difficulty = "standard"
        hints = True
        examples = True
        guided_steps = "moderate"
        explanation = "standard"
        reason = "Relevant evidence is mixed or still developing, so the required task stays at standard support."

    return AdaptivePresentationDecision(
        project_id=task.project_id,
        target_task_id=task.task_id,
        task_type=task.task_type,
        task_difficulty=task.difficulty,
        support_level=support,
        presentation_difficulty=difficulty,
        hints_available=hints,
        examples_available=examples,
        guided_step_level=guided_steps,
        explanation_depth=explanation,
        reason=reason,
        evidence_used=summary,
    )