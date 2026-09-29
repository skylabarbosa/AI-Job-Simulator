from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    business_problem: str = Field(min_length=1)
    work_requirements: str = Field(min_length=1)
    desired_outcome: str = Field(min_length=1)


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    business_problem: str | None = Field(default=None, min_length=1)
    work_requirements: str | None = Field(default=None, min_length=1)
    desired_outcome: str | None = Field(default=None, min_length=1)


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    slug: str
    business_problem: str | None = None
    work_requirements: str | None = None
    desired_outcome: str | None = None
    created_by: UUID | None = None
    status: str
    materialized: bool = False
    created_at: datetime
    updated_at: datetime


class LearnerWorkAreaSummary(BaseModel):
    name: str
    description: str


class LearnerProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    slug: str
    project_summary: str
    business_objective: str
    expected_outcome: str
    work_areas: list[LearnerWorkAreaSummary]


class LearnerTaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    description: str | None = None
    instructions: str | None = None
    task_type: str
    difficulty: str
    expected_outcome: str | None = None
    module_id: UUID | None = None
    blueprint_task_key: UUID | None = None

