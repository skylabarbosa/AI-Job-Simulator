from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class SimulationContext(BaseModel):
    """The context returned after starting or resuming a simulation."""

    model_config = ConfigDict(from_attributes=True)

    simulation_id: UUID
    project_id: UUID
    project_name: str
    task_id: UUID
    task_title: str
    task_description: str | None = None
    task_instructions: str | None = None
    task_expected_outcome: str | None = None
    task_type: str
    task_difficulty: str
    module_id: UUID
    module_name: str
    status: str
    started_at: datetime
    activity_state: str
