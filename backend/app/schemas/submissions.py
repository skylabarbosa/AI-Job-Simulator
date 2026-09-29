from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


ValidationStatus = Literal["passed", "failed", "needs_evaluation"]


class SubmissionCreate(BaseModel):
    """Generic learner submission payload.

    Learner identity and lifecycle fields are always derived server-side.
    """

    response: str | None = Field(default=None, max_length=20000)
    content: dict[str, Any] | None = None

    @model_validator(mode="after")
    def require_submission_content(self) -> "SubmissionCreate":
        has_response = bool(self.response and self.response.strip())
        has_content = bool(self.content)
        if not has_response and not has_content:
            raise ValueError("Submission content is required")
        return self


class DeterministicCheck(BaseModel):
    name: str
    passed: bool
    message: str


class SkillEvidence(BaseModel):
    competency_id: UUID | None = None
    concept_id: UUID | None = None
    evidence: str
    level: Literal["demonstrated", "developing", "insufficient_evidence"]


class SubmissionResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    submission_id: UUID
    evaluation_id: UUID | None = None
    validation_status: ValidationStatus
    checks: list[DeterministicCheck]
    message: str
    strengths: list[str] = []
    areas_for_improvement: list[str] = []
    evidence: list[str] = []
    skill_evidence: list[SkillEvidence] = []
    execution_status: Literal["success", "error"] | None = None
    columns: list[str] = []
    rows: list[list[Any]] = []
    row_count: int | None = None
    displayed_row_count: int | None = None
    truncated: bool = False
    execution_time_ms: float | None = None
