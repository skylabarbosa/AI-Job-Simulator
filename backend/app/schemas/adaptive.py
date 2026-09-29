from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


SupportLevel = Literal["independent", "moderate", "guided"]
PresentationDifficulty = Literal["foundational", "standard", "stretch"]
GuidedStepLevel = Literal["none", "moderate", "explicit"]
ExplanationDepth = Literal["concise", "standard", "detailed"]


class AdaptiveEvidenceSummary(BaseModel):
    relevant_concept_ids: list[UUID] = []
    relevant_competency_ids: list[UUID] = []
    demonstrated_evidence_count: int = 0
    developing_evidence_count: int = 0
    relevant_failure_count: int = 0
    repeated_failure_count: int = 0
    historical_mastery_preserved: bool = False


class AdaptivePresentationDecision(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    project_id: UUID
    target_task_id: UUID
    task_type: str
    task_difficulty: str
    support_level: SupportLevel
    presentation_difficulty: PresentationDifficulty
    hints_available: bool
    examples_available: bool
    guided_step_level: GuidedStepLevel
    explanation_depth: ExplanationDepth
    reason: str
    evidence_used: AdaptiveEvidenceSummary