from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DatasetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    file_name: str
    storage_path: str
    file_type: str
    file_size: int | None = None
    row_count: int | None = None
    column_count: int | None = None
    schema_metadata: dict[str, Any]
    status: str
    uploaded_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class DatasetDownloadResponse(BaseModel):
    url: str


class DatasetPreviewResponse(BaseModel):
    dataset_id: UUID
    file_name: str
    columns: list[str]
    rows: list[dict[str, str]]
    row_limit: int
    total_rows: int | None = None
