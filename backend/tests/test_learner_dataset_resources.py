import asyncio
import csv
import io
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from fastapi import HTTPException, UploadFile
from fastapi.testclient import TestClient
from starlette.datastructures import Headers

from app.api.routes.datasets import _require_dataset_access, download_dataset, list_datasets, preview_dataset, upload_dataset
from app.core.auth import get_current_profile, get_current_user
from app.schemas.auth import AuthenticatedUser, UserProfile
from main import app


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


class FakeQuery:
    def __init__(self, client, table_name: str):
        self.client = client
        self.table_name = table_name
        self._data = list(client.records.get(table_name, []))
        self._single = False

    def select(self, *_):
        return self

    def eq(self, field, value):
        self._data = [row for row in self._data if str(row.get(field)) == str(value)]
        return self

    def order(self, *_args, **_kwargs):
        return self

    def limit(self, count):
        self._data = self._data[:count]
        return self

    def maybe_single(self):
        self._single = True
        self._data = self._data[:1]
        return self

    def execute(self):
        if self._single:
            return SimpleNamespace(data=self._data[0] if self._data else None)
        return SimpleNamespace(data=self._data)


class FakeStorageBucket:
    def __init__(self, client):
        self.client = client

    def create_signed_url(self, path, _ttl):
        return {"signedURL": f"https://example.test/{path}"}

    def download(self, path):
        return self.client.storage_files[path]


class FakeStorage:
    def __init__(self, client):
        self.client = client

    def from_(self, _bucket):
        return FakeStorageBucket(self.client)


class FakeClient:
    def __init__(self, records, storage_files=None):
        self.records = {key: list(value) for key, value in records.items()}
        self.storage_files = storage_files or {}
        self.storage = FakeStorage(self)

    def table(self, table_name: str):
        return FakeQuery(self, table_name)


class TestLearnerDatasetResources(unittest.TestCase):
    def setUp(self):
        self.project_id = uuid4()
        self.dataset_id = uuid4()
        self.user = AuthenticatedUser(id=str(uuid4()), email="learner@example.com")
        self.profile = UserProfile(id=self.user.id, email=self.user.email, role="learner")
        self.dataset = {
            "id": str(self.dataset_id),
            "project_id": str(self.project_id),
            "file_name": "source.csv",
            "storage_path": f"{self.project_id}/source.csv",
            "file_type": "text/csv",
            "file_size": 32,
            "row_count": 2,
            "column_count": 2,
            "schema_metadata": {"columns": [{"name": "department", "inferred_type": "string", "missing_count": 0}]},
            "status": "ready",
            "uploaded_at": _ts(),
            "created_at": _ts(),
            "updated_at": _ts(),
        }
        self.records = {
            "projects": [{"id": str(self.project_id), "status": "active"}],
            "project_blueprints": [{"id": str(uuid4()), "project_id": str(self.project_id), "status": "approved"}],
            "datasets": [self.dataset],
        }

    def _client(self, records=None):
        return FakeClient(
            records or self.records,
            {self.dataset["storage_path"]: b"department,salary\nSales,10\nOps,20\n"},
        )

    def test_learner_can_list_ready_project_resources(self):
        with patch("app.api.routes.datasets.get_supabase_client", return_value=self._client()):
            resources = list_datasets(self.project_id, self.user, self.profile)

        self.assertEqual(len(resources), 1)
        self.assertEqual(str(resources[0].id), str(self.dataset_id))

    def test_learner_resource_read_rejects_unpublished_project(self):
        records = {**self.records, "projects": [{"id": str(self.project_id), "status": "draft"}]}
        with patch("app.api.routes.datasets.get_supabase_client", return_value=self._client(records)):
            with self.assertRaises(HTTPException) as ctx:
                list_datasets(self.project_id, self.user, self.profile)

        self.assertEqual(ctx.exception.status_code, 404)

    def test_business_can_read_published_datasets_but_cannot_mutate_them(self):
        business = AuthenticatedUser(id=str(uuid4()), email="business@example.com")
        profile = UserProfile(id=business.id, email=business.email, role="business")
        records = {
            **self.records,
            "projects": [{"id": str(self.project_id), "status": "active", "created_by": business.id}],
        }

        client = self._client(records)
        with (
            patch("app.api.routes.datasets.get_supabase_client", return_value=client),
            patch("app.api.routes.projects.get_supabase_client", return_value=client),
        ):
            resources = list_datasets(self.project_id, business, profile)
            with self.assertRaises(HTTPException) as ctx:
                _require_dataset_access(self.project_id, business, profile)

        self.assertEqual(len(resources), 1)
        self.assertEqual(ctx.exception.status_code, 409)

    def test_learner_can_open_dataset_with_signed_url(self):
        with patch("app.api.routes.datasets.get_supabase_client", return_value=self._client()):
            result = download_dataset(self.project_id, self.dataset_id, self.user, self.profile)

        self.assertIn("source.csv", result.url)

    def test_dataset_preview_returns_limited_real_rows(self):
        with patch("app.api.routes.datasets.get_supabase_client", return_value=self._client()):
            result = preview_dataset(self.project_id, self.dataset_id, 1, self.user, self.profile)

        self.assertEqual(result.columns, ["department", "salary"])
        self.assertEqual(result.rows, [{"department": "Sales", "salary": "10"}])

    def test_formula_like_csv_upload_is_saved_as_plain_text(self):
        stored_files = {}

        class StorageBucket:
            def upload(self, path, content, _options):
                stored_files[path] = content

        class Storage:
            def from_(self, _bucket):
                return StorageBucket()

        class InsertQuery:
            def insert(self, record):
                self.record = record
                return self

            def execute(self):
                return SimpleNamespace(data=[{**self.record, "id": str(uuid4())}])

        class Client:
            storage = Storage()

            def table(self, _table):
                return InsertQuery()

        source = b"name,value\nAlice,=1+1\nBob,-cmd()\n"
        file = UploadFile(
            file=io.BytesIO(source),
            filename="toxic_preprocessed.csv",
            headers=Headers({"content-type": "text/csv"}),
        )
        with (
            patch("app.api.routes.datasets._require_dataset_access"),
            patch("app.api.routes.datasets.get_supabase_client", return_value=Client()),
            patch("app.api.routes.datasets._dataset_response", side_effect=lambda record: record),
        ):
            result = asyncio.run(upload_dataset(self.project_id, file, self.user, self.profile))

        self.assertEqual(result["file_name"], "toxic_preprocessed.csv")
        self.assertEqual(result["row_count"], 2)
        self.assertEqual(len(stored_files), 1)
        stored_rows = list(csv.reader(io.StringIO(next(iter(stored_files.values())).decode("utf-8"))))
        self.assertEqual(stored_rows[1], ["Alice", "'=1+1"])
        self.assertEqual(stored_rows[2], ["Bob", "'-cmd()"])

    def test_cors_preflight_allows_local_origins_and_methods(self):
        client = TestClient(app)
        for origin in ["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:3000"]:
            response = client.options(
                f"/api/projects/{self.project_id}/datasets",
                headers={
                    "Origin": origin,
                    "Access-Control-Request-Method": "GET",
                    "Access-Control-Request-Headers": "authorization,content-type,accept,x-client-info",
                },
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.headers.get("access-control-allow-origin"), origin)
            self.assertIn("GET", response.headers.get("access-control-allow-methods", ""))

    def test_http_client_learner_dataset_flow(self):
        app.dependency_overrides[get_current_user] = lambda: self.user
        app.dependency_overrides[get_current_profile] = lambda: self.profile
        try:
            with patch("app.api.routes.datasets.get_supabase_client", return_value=self._client()):
                client = TestClient(app)
                # List
                list_resp = client.get(
                    f"/api/projects/{self.project_id}/datasets",
                    headers={"Origin": "http://127.0.0.1:5173"},
                )
                self.assertEqual(list_resp.status_code, 200)
                datasets = list_resp.json()
                self.assertEqual(len(datasets), 1)
                self.assertEqual(datasets[0]["id"], str(self.dataset_id))
                self.assertEqual(datasets[0]["file_name"], "source.csv")

                # Preview
                prev_resp = client.get(
                    f"/api/projects/{self.project_id}/datasets/{self.dataset_id}/preview?limit=1",
                    headers={"Origin": "http://localhost:5173"},
                )
                self.assertEqual(prev_resp.status_code, 200)
                prev_data = prev_resp.json()
                self.assertEqual(prev_data["columns"], ["department", "salary"])
                self.assertEqual(len(prev_data["rows"]), 1)

                # Download
                dl_resp = client.get(
                    f"/api/projects/{self.project_id}/datasets/{self.dataset_id}/download",
                    headers={"Origin": "http://localhost:5173"},
                )
                self.assertEqual(dl_resp.status_code, 200)
                self.assertIn("source.csv", dl_resp.json()["url"])
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            app.dependency_overrides.pop(get_current_profile, None)


if __name__ == "__main__":
    unittest.main()
