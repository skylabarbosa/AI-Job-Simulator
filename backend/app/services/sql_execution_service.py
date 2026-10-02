"""Ephemeral, read-only SQL execution for learner workspace previews."""

import csv
import io
import json
import logging
import re
import sqlite3
import time
from typing import Any

from fastapi import HTTPException, status

from app.db.client import get_supabase_client


logger = logging.getLogger(__name__)


MAX_QUERY_LENGTH = 20_000
MAX_RESULT_ROWS = 100
MAX_RESULT_COLUMNS = 50
MAX_RESULT_BYTES = 1_000_000
EXECUTION_TIMEOUT_SECONDS = 3
READ_ONLY_START = re.compile(r"^\s*(select|with)\b", re.IGNORECASE)
FORBIDDEN_SQL = re.compile(
    r"\b(insert|update|delete|drop|alter|create|truncate|grant|revoke|attach|detach|copy|call|execute|pragma|begin|commit|rollback|transaction|vacuum|install|load)\b",
    re.IGNORECASE,
)


def _identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _safe_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _validate_query(query: str) -> None:
    if not query.strip():
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Enter a SQL query to run.")
    if len(query) > MAX_QUERY_LENGTH:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Your query is too long to run.")
    if not READ_ONLY_START.match(query) or FORBIDDEN_SQL.search(query):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Only one read-only SELECT query is allowed.")


def _dataset_table_names(dataset: dict[str, Any]) -> str:
    metadata = dataset.get("schema_metadata") or {}
    return str(metadata.get("table_name") or dataset.get("file_name", "dataset").rsplit(".", 1)[0])


def _load_task_datasets(client: Any, project_id: str, table_names: set[str]) -> list[tuple[dict[str, Any], bytes]]:
    response = (
        client.table("datasets")
        .select("*")
        .eq("project_id", project_id)
        .eq("status", "ready")
        .execute()
    )
    datasets = response.data or []
    selected = [dataset for dataset in datasets if _dataset_table_names(dataset) in table_names]
    if not selected or len(selected) != len(table_names):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="The task dataset is not available.")
    loaded: list[tuple[dict[str, Any], bytes]] = []
    for dataset in selected:
        try:
            content = client.storage.from_("project-datasets").download(dataset["storage_path"])
        except Exception as error:
            logger.exception("Unable to download SQL dataset from Supabase Storage")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Unable to load the task dataset.") from error
        loaded.append((dataset, content))
    return loaded


def _authorizer(action: int, _arg1: str | None, _arg2: str | None, _db: str | None, _source: str | None) -> int:
    denied = {
        sqlite3.SQLITE_INSERT, sqlite3.SQLITE_UPDATE, sqlite3.SQLITE_DELETE,
        sqlite3.SQLITE_CREATE_INDEX, sqlite3.SQLITE_CREATE_TABLE, sqlite3.SQLITE_CREATE_TEMP_INDEX,
        sqlite3.SQLITE_CREATE_TEMP_TABLE, sqlite3.SQLITE_CREATE_TEMP_TRIGGER, sqlite3.SQLITE_CREATE_TEMP_VIEW,
        sqlite3.SQLITE_CREATE_TRIGGER, sqlite3.SQLITE_CREATE_VIEW, sqlite3.SQLITE_DROP_INDEX,
        sqlite3.SQLITE_DROP_TABLE, sqlite3.SQLITE_DROP_TEMP_INDEX, sqlite3.SQLITE_DROP_TEMP_TABLE,
        sqlite3.SQLITE_DROP_TEMP_TRIGGER, sqlite3.SQLITE_DROP_TEMP_VIEW, sqlite3.SQLITE_DROP_TRIGGER,
        sqlite3.SQLITE_DROP_VIEW, sqlite3.SQLITE_ALTER_TABLE, sqlite3.SQLITE_ATTACH,
        sqlite3.SQLITE_DETACH, sqlite3.SQLITE_PRAGMA, sqlite3.SQLITE_TRANSACTION,
    }
    return sqlite3.SQLITE_DENY if action in denied else sqlite3.SQLITE_OK


def _execute(connection: sqlite3.Connection, query: str) -> tuple[list[str], list[tuple[Any, ...]]]:
    result = connection.execute(query)
    columns = [item[0] for item in (result.description or [])]
    if len(columns) > MAX_RESULT_COLUMNS:
        raise ValueError("Your query returned too many columns. Select only the fields you need.")
    return columns, result.fetchmany(MAX_RESULT_ROWS + 1)


def execute_task_sql(*, project_id: str, task: dict[str, Any], query: str) -> dict[str, Any]:
    _validate_query(query)
    reference = task.get("reference_solution") if isinstance(task.get("reference_solution"), dict) else {}
    table_names = {str(name) for name in reference.get("sql_tables", []) if str(name).strip()}
    if not table_names:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="This SQL task has no available dataset table.")

    client = get_supabase_client()
    datasets = _load_task_datasets(client, project_id, table_names)
    connection = sqlite3.connect(":memory:")
    started = time.perf_counter()
    try:
        connection.set_authorizer(_authorizer)
        deadline = time.perf_counter() + EXECUTION_TIMEOUT_SECONDS
        connection.set_progress_handler(lambda: 1 if time.perf_counter() > deadline else 0, 10_000)
        for dataset, content in datasets:
            table_name = _dataset_table_names(dataset)
            reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig"), newline=""), strict=True)
            columns = reader.fieldnames or []
            if not columns:
                raise ValueError("The task dataset has no columns.")
            connection.set_authorizer(None)
            connection.execute(f"CREATE TABLE {_identifier(table_name)} ({', '.join(f'{_identifier(column)} TEXT' for column in columns)})")
            connection.set_authorizer(_authorizer)
            rows = [[row.get(column) or None for column in columns] for row in reader]
            if rows:
                placeholders = ", ".join("?" for _ in columns)
                connection.set_authorizer(None)
                connection.executemany(f"INSERT INTO {_identifier(table_name)} VALUES ({placeholders})", rows)
                connection.set_authorizer(_authorizer)

        try:
            columns, raw_rows = _execute(connection, query)
        except sqlite3.OperationalError as error:
            error_message = str(error)
            if "interrupted" in error_message.lower():
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Your query took too long to complete. Try narrowing the result.") from error
            logger.info("SQL query failed during execution: %s", error_message)
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"SQL could not be run: {error_message}") from error

        truncated = len(raw_rows) > MAX_RESULT_ROWS
        rows = [[_safe_value(value) for value in row] for row in raw_rows[:MAX_RESULT_ROWS]]
        payload_size = len(json.dumps(rows, ensure_ascii=True, default=str).encode("utf-8"))
        if payload_size > MAX_RESULT_BYTES:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Your result is too large to display. Try adding filters or LIMIT.")
        return {
            "execution_status": "success",
            "columns": columns,
            "rows": rows,
            "row_count": len(rows),
            "displayed_row_count": len(rows),
            "truncated": truncated,
            "execution_time_ms": round((time.perf_counter() - started) * 1000, 2),
        }
    except HTTPException:
        raise
    except (UnicodeDecodeError, csv.Error, ValueError) as error:
        logger.info("SQL query could not be processed: %s", error)
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"SQL could not be run: {error}") from error
    except Exception as error:
        logger.exception("Unexpected SQL query execution failure")
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"SQL could not be run: {error}") from error
    finally:
        connection.close()
