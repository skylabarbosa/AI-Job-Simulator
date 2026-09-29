import csv
import io
import os
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import PurePosixPath
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status

from app.core.auth import get_current_profile, get_current_user
from app.core.config import settings
from app.db.client import get_supabase_client
from app.schemas.auth import AuthenticatedUser, UserProfile
from app.schemas.datasets import DatasetDownloadResponse, DatasetPreviewResponse, DatasetResponse
from app.api.routes.projects import _get_project, _require_project_access, _require_project_manager


router = APIRouter(prefix="/projects/{project_id}/datasets", tags=["datasets"])
STORAGE_BUCKET = "project-datasets"
ALLOWED_CONTENT_TYPES = {"", "text/csv", "application/csv", "application/vnd.ms-excel", "application/octet-stream"}
SPREADSHEET_FORMULA_PREFIXES = ("=", "+", "@")


def _require_dataset_access(project_id: UUID, user: AuthenticatedUser, profile: UserProfile) -> None:
    _require_project_manager(profile)
    project = _get_project(project_id)
    _require_project_access(project, user, profile)
    if project.get("status") != "draft":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Published project datasets are immutable; create a revision and release with new resources",
        )


def _require_dataset_read_access(project_id: UUID, user: AuthenticatedUser, profile: UserProfile) -> None:
    if profile.role == "learner":
        client = get_supabase_client()
        project_resp = (
            client.table("projects")
            .select("id, status")
            .eq("id", str(project_id))
            .eq("status", "active")
            .maybe_single()
            .execute()
        )
        if not project_resp.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

        blueprint_resp = (
            client.table("project_blueprints")
            .select("id")
            .eq("project_id", str(project_id))
            .eq("status", "approved")
            .limit(1)
            .execute()
        )
        if not blueprint_resp.data:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Project does not have an approved blueprint")
        return

    _require_project_manager(profile)
    project = _get_project(project_id)
    _require_project_access(project, user, profile)


def _dataset_response(data: dict) -> DatasetResponse:
    return DatasetResponse.model_validate(data)


def _infer_type(values: list[str]) -> str:
    non_empty = [value.strip() for value in values if value.strip()]
    if not non_empty:
        return "null"
    if all(value.lower() in {"true", "false"} for value in non_empty):
        return "boolean"
    try:
        for value in non_empty:
            int(value)
        return "integer"
    except ValueError:
        pass
    try:
        for value in non_empty:
            float(value)
        return "number"
    except ValueError:
        return "string"


def _numeric_profile(values: list[str], inferred_type: str) -> dict[str, int | float]:
    if inferred_type not in {"integer", "number"}:
        return {}
    numeric_values = [float(value.strip()) for value in values if value.strip()]
    if inferred_type == "integer":
        return {"min": int(min(numeric_values)), "max": int(max(numeric_values))}
    return {"min": min(numeric_values), "max": max(numeric_values)}


def _is_spreadsheet_formula(value: str) -> bool:
    candidate = value.lstrip()
    if candidate.startswith(SPREADSHEET_FORMULA_PREFIXES):
        return True
    # Preserve legitimate negative numbers while rejecting formula expressions
    # such as `-cmd()` that spreadsheets can evaluate.
    return candidate.startswith("-") and re.match(r"^-\d+(?:\.\d+)?(?:\s*)$", candidate) is None


def _escape_spreadsheet_formulas(content: bytes) -> bytes:
    text = content.decode("utf-8-sig")
    rows = list(csv.reader(io.StringIO(text, newline=""), strict=True))
    if not any(_is_spreadsheet_formula(value) for row in rows for value in row):
        return content

    output = io.StringIO(newline="")
    writer = csv.writer(output)
    for row in rows:
        writer.writerow([f"'{value}" if _is_spreadsheet_formula(value) else value for value in row])
    return output.getvalue().encode("utf-8")


def _inspect_csv(content: bytes, file_name: str) -> tuple[int, int, dict]:
    try:
        text = content.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text), strict=True)
        fieldnames = reader.fieldnames
        if not fieldnames or any(not name.strip() for name in fieldnames):
            raise ValueError("CSV must contain a non-empty header row")
        if len(set(fieldnames)) != len(fieldnames):
            raise ValueError("CSV column names must be unique")

        values = {name: [] for name in fieldnames}
        missing = Counter()
        row_count = 0
        for row in reader:
            if None in row:
                raise ValueError("CSV rows do not match the header columns")
            row_count += 1
            for name in fieldnames:
                value = row.get(name, "") or ""
                values[name].append(value)
                if not value.strip():
                    missing[name] += 1

        columns = []
        for name in fieldnames:
            inferred_type = _infer_type(values[name])
            column = {
                "name": name,
                "inferred_type": inferred_type,
                "missing_count": missing[name],
                "unique_count": len({value.strip() for value in values[name] if value.strip()}),
            }
            column.update(_numeric_profile(values[name], inferred_type))
            columns.append(column)
        table_name = PurePosixPath(file_name).stem
        return row_count, len(fieldnames), {
            "profile_version": 1,
            "file_name": file_name,
            "table_name": table_name,
            "row_count": row_count,
            "column_count": len(fieldnames),
            "columns": columns,
        }
    except (UnicodeDecodeError, csv.Error, ValueError) as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Invalid CSV: {error}") from error


def _preview_csv(content: bytes, *, dataset: dict, row_limit: int) -> DatasetPreviewResponse:
    try:
        text = content.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text), strict=True)
        columns = reader.fieldnames or []
        rows = []
        for index, row in enumerate(reader):
            if index >= row_limit:
                break
            if None in row:
                raise ValueError("CSV rows do not match the header columns")
            rows.append({column: row.get(column, "") or "" for column in columns})
        return DatasetPreviewResponse(
            dataset_id=dataset["id"],
            file_name=dataset["file_name"],
            columns=columns,
            rows=rows,
            row_limit=row_limit,
            total_rows=dataset.get("row_count"),
        )
    except (UnicodeDecodeError, csv.Error, ValueError) as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Dataset preview unavailable: {error}") from error


async def _read_csv(file: UploadFile) -> bytes:
    file_name = file.filename or ""
    if PurePosixPath(file_name).suffix.lower() != ".csv":
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Only .csv files are supported")
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="The uploaded file must be a CSV")

    content = await file.read(settings.dataset_max_file_size_bytes + 1)
    if not content:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="The CSV file is empty")
    if len(content) > settings.dataset_max_file_size_bytes:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="The CSV file is too large")
    return content


def _storage_path(project_id: UUID, file_name: str) -> str:
    safe_name = os.path.basename(file_name).replace("/", "_").replace("\\", "_")
    return f"{project_id}/{uuid4()}/{safe_name}"


def _remove_storage(path: str) -> None:
    try:
        get_supabase_client().storage.from_(STORAGE_BUCKET).remove([path])
    except Exception:
        pass


@router.post("", response_model=DatasetResponse, status_code=status.HTTP_201_CREATED)
async def upload_dataset(
    project_id: UUID,
    file: UploadFile = File(...),
    user: AuthenticatedUser = Depends(get_current_user),
    profile: UserProfile = Depends(get_current_profile),
) -> DatasetResponse:
    _require_dataset_access(project_id, user, profile)
    content = await _read_csv(file)
    _inspect_csv(content, file.filename or "dataset.csv")
    content = _escape_spreadsheet_formulas(content)
    if len(content) > settings.dataset_max_file_size_bytes:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="The CSV file is too large")
    row_count, column_count, metadata = _inspect_csv(content, file.filename or "dataset.csv")
    storage_path = _storage_path(project_id, file.filename or "dataset.csv")
    client = get_supabase_client()

    try:
        client.storage.from_(STORAGE_BUCKET).upload(
            storage_path,
            content,
            {"content-type": "text/csv", "upsert": False},
        )
        response = client.table("datasets").insert(
            {
                "project_id": str(project_id),
                "file_name": file.filename or "dataset.csv",
                "storage_path": storage_path,
                "file_type": "text/csv",
                "file_size": len(content),
                "row_count": row_count,
                "column_count": column_count,
                "schema_metadata": metadata,
                "status": "ready",
                "uploaded_at": datetime.now(timezone.utc).isoformat(),
            }
        ).execute()
        if not response.data:
            raise RuntimeError("Dataset record was not created")
        return _dataset_response(response.data[0])
    except HTTPException:
        _remove_storage(storage_path)
        raise
    except Exception as error:
        _remove_storage(storage_path)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Unable to store the dataset") from error


@router.get("", response_model=list[DatasetResponse])
def list_datasets(
    project_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    profile: UserProfile = Depends(get_current_profile),
) -> list[DatasetResponse]:
    _require_dataset_read_access(project_id, user, profile)
    try:
        response = get_supabase_client().table("datasets").select("*").eq("project_id", str(project_id)).order("created_at", desc=True).execute()
        return [_dataset_response(dataset) for dataset in (response.data or [])]
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Unable to load project resources") from error


@router.get("/{dataset_id}", response_model=DatasetResponse)
def get_dataset(
    project_id: UUID,
    dataset_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    profile: UserProfile = Depends(get_current_profile),
) -> DatasetResponse:
    _require_dataset_read_access(project_id, user, profile)
    response = get_supabase_client().table("datasets").select("*").eq("id", str(dataset_id)).eq("project_id", str(project_id)).maybe_single().execute()
    if not response.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found")
    return _dataset_response(response.data)


@router.delete("/{dataset_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_dataset(
    project_id: UUID,
    dataset_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    profile: UserProfile = Depends(get_current_profile),
) -> None:
    _require_dataset_access(project_id, user, profile)
    response = get_supabase_client().table("datasets").select("storage_path").eq("id", str(dataset_id)).eq("project_id", str(project_id)).maybe_single().execute()
    if not response.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found")
    storage_path = response.data["storage_path"]
    _remove_storage(storage_path)
    get_supabase_client().table("datasets").delete().eq("id", str(dataset_id)).eq("project_id", str(project_id)).execute()


@router.get("/{dataset_id}/download", response_model=DatasetDownloadResponse)
def download_dataset(
    project_id: UUID,
    dataset_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    profile: UserProfile = Depends(get_current_profile),
) -> DatasetDownloadResponse:
    _require_dataset_read_access(project_id, user, profile)
    try:
        response = get_supabase_client().table("datasets").select("storage_path").eq("id", str(dataset_id)).eq("project_id", str(project_id)).maybe_single().execute()
        if not response.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found")
        signed = get_supabase_client().storage.from_(STORAGE_BUCKET).create_signed_url(response.data["storage_path"], 600)
        url = signed.get("signedURL") or signed.get("signedUrl")
        if not url:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Unable to create dataset access URL")
        return DatasetDownloadResponse(url=url)
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Unable to create dataset access URL") from error


@router.get("/{dataset_id}/preview", response_model=DatasetPreviewResponse)
def preview_dataset(
    project_id: UUID,
    dataset_id: UUID,
    limit: int = Query(default=10, ge=1, le=25),
    user: AuthenticatedUser = Depends(get_current_user),
    profile: UserProfile = Depends(get_current_profile),
) -> DatasetPreviewResponse:
    _require_dataset_read_access(project_id, user, profile)
    response = (
        get_supabase_client()
        .table("datasets")
        .select("*")
        .eq("id", str(dataset_id))
        .eq("project_id", str(project_id))
        .eq("status", "ready")
        .maybe_single()
        .execute()
    )
    if not response.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ready dataset not found")
    dataset = response.data
    try:
        content = get_supabase_client().storage.from_(STORAGE_BUCKET).download(dataset["storage_path"])
    except Exception as error:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Unable to load dataset preview") from error
    return _preview_csv(content, dataset=dataset, row_limit=limit)
