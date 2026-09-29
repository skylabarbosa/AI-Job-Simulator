from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TaskProgress(BaseModel):
    task_id: UUID
    title: str
    completed: bool
    attempts: int
    latest_evaluation_status: str | None = None
    latest_score: float | None = None


class SkillProgress(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    kind: str
    level: str
    score: float
    demonstrated: bool


class EvaluationResponse(BaseModel):
    submission_id: UUID
    evaluation_type: str
    status: str
    score: float | None = None
    feedback: str | None = None
    evaluated_at: datetime | None = None
    strengths: list[str] = []
    areas_for_improvement: list[str] = []
    evidence: list[str] = []


class ProjectPerformanceResponse(BaseModel):
    project_id: UUID
    total_tasks: int
    completed_tasks: int
    progress: float
    completed: bool
    tasks: list[TaskProgress]
    competencies: list[SkillProgress]
    concepts: list[SkillProgress]


class LearnerProgressTotals(BaseModel):
    projects_started: int = 0
    completed_projects: int = 0
    total_tasks: int = 0
    completed_tasks: int = 0
    average_progress: float = 0.0


class LearnerProjectProgress(BaseModel):
    project_id: UUID
    project_name: str | None = None
    status: str | None = None
    total_tasks: int = 0
    completed_tasks: int = 0
    progress: float = 0.0
    completed: bool = False
    started_at: datetime | None = None
    completed_at: datetime | None = None


class LearnerRecentActivity(BaseModel):
    project_id: UUID | None = None
    project_name: str | None = None
    task_id: UUID | None = None
    task_title: str | None = None
    status: str | None = None
    submitted_at: datetime | None = None
    attempt_number: int = 0
    evaluation_status: str | None = None
    score: float | None = None


class LearnerProgressResponse(BaseModel):
    projects: list[LearnerProjectProgress] = Field(default_factory=list)
    totals: LearnerProgressTotals = LearnerProgressTotals()
    recent_activity: list[LearnerRecentActivity] = Field(default_factory=list)


class LearnerSkillTotals(BaseModel):
    total_skills: int = 0
    demonstrated_skills: int = 0
    average_score: float = 0.0


class LearnerSkillSummary(BaseModel):
    id: UUID
    name: str
    kind: str
    level: str
    score: float = 0.0
    demonstrated: bool = False
    evidence_count: int = 0
    source_project_ids: list[UUID] = Field(default_factory=list)
    source_task_ids: list[UUID] = Field(default_factory=list)
    last_evaluated_at: datetime | None = None


class LearnerSkillsResponse(BaseModel):
    skills: list[LearnerSkillSummary] = Field(default_factory=list)
    totals: LearnerSkillTotals = LearnerSkillTotals()