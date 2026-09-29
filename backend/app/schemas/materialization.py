from uuid import UUID

from pydantic import BaseModel


class MaterializationResult(BaseModel):
    status: str
    blueprint_version: int
    blueprint_id: UUID | None = None
    release_id: UUID | None = None
    modules_created: int = 0
    competencies_created: int = 0
    concepts_created: int = 0
    tasks_created: int = 0
    task_competencies_created: int = 0
    task_concepts_created: int = 0
    rubrics_created: int = 0
