import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient
from fastapi import HTTPException

from app.core.auth import get_current_profile
from app.schemas.auth import UserProfile
from app.api.routes.projects import list_project_tasks
from main import create_app


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def project_record(project_id, *, status="active", owner_id=None):
    return {
        "id": str(project_id),
        "name": "Learner project",
        "slug": "learner-project",
        "status": status,
        "created_by": owner_id or str(uuid4()),
        "created_at": _ts(),
        "updated_at": _ts(),
    }


def module_record(module_id, project_id, name):
    return {
        "id": str(module_id),
        "project_id": str(project_id),
        "name": name,
        "status": "active",
    }


def task_record(task_id, project_id, module_id, title, *, position=1):
    return {
        "id": str(task_id),
        "project_id": str(project_id),
        "module_id": str(module_id),
        "title": title,
        "description": f"{title} description",
        "instructions": f"{title} instructions",
        "task_type": "analysis",
        "difficulty": "easy",
        "expected_outcome": f"{title} outcome",
        "status": "active",
        "position": position,
    }


class FakeQuery:
    def __init__(self, client, table_name):
        self.client = client
        self.table_name = table_name
        self.data = list(client.records.get(table_name, []))
        self._single = False

    def select(self, *_args):
        return self

    def eq(self, field, value):
        self.data = [record for record in self.data if str(record.get(field)) == str(value)]
        return self

    def order(self, field, desc=False):
        self.data.sort(key=lambda record: record.get(field, 0), reverse=desc)
        return self

    def maybe_single(self):
        self._single = True
        self.data = self.data[:1]
        return self

    def execute(self):
        if self._single:
            return SimpleNamespace(data=self.data[0] if self.data else None)
        return SimpleNamespace(data=self.data)


class FakeClient:
    def __init__(self, records):
        self.records = {table: list(rows) for table, rows in records.items()}

    def table(self, table_name):
        return FakeQuery(self, table_name)


class TaskDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.project_id = uuid4()
        self.other_project_id = uuid4()
        self.cleaning_module_id = uuid4()
        self.sql_module_id = uuid4()
        self.other_cleaning_module_id = uuid4()
        self.cleaning_task_id = uuid4()
        self.sql_task_id = uuid4()
        self.other_project_task_id = uuid4()
        self.learner_profile = UserProfile(
            id=str(uuid4()),
            email="learner@example.com",
            role="learner",
        )
        self.records = {
            "projects": [
                project_record(self.project_id),
                project_record(self.other_project_id),
            ],
            "modules": [
                module_record(self.cleaning_module_id, self.project_id, "Data Cleaning"),
                module_record(self.sql_module_id, self.project_id, "SQL"),
                module_record(self.other_cleaning_module_id, self.other_project_id, "Data Cleaning"),
            ],
            "tasks": [
                task_record(self.cleaning_task_id, self.project_id, self.cleaning_module_id, "Clean records", position=1),
                task_record(self.sql_task_id, self.project_id, self.sql_module_id, "Query records", position=2),
                task_record(
                    self.other_project_task_id,
                    self.other_project_id,
                    self.other_cleaning_module_id,
                    "Other project cleaning",
                    position=1,
                ),
            ],
        }

    def _api_client(self, records=None, profile=None):
        app = create_app()
        app.dependency_overrides[get_current_profile] = lambda: profile or self.learner_profile
        return TestClient(app), FakeClient(records or self.records)

    @patch("app.api.routes.projects.get_supabase_client")
    def test_valid_module_slug_returns_only_that_modules_tasks(self, get_client):
        api_client, fake_client = self._api_client()
        get_client.return_value = fake_client

        response = api_client.get(f"/api/projects/{self.project_id}/tasks?module_slug=data-cleaning")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual([task["id"] for task in payload], [str(self.cleaning_task_id)])
        self.assertEqual(payload[0]["module_id"], str(self.cleaning_module_id))

    @patch("app.api.routes.projects.get_supabase_client")
    def test_another_valid_module_slug_returns_its_tasks(self, get_client):
        api_client, fake_client = self._api_client()
        get_client.return_value = fake_client

        response = api_client.get(f"/api/projects/{self.project_id}/tasks?module_slug=sql")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual([task["id"] for task in payload], [str(self.sql_task_id)])
        self.assertEqual(payload[0]["module_id"], str(self.sql_module_id))

    @patch("app.api.routes.projects.get_supabase_client")
    def test_invalid_module_slug_returns_empty_list(self, get_client):
        api_client, fake_client = self._api_client()
        get_client.return_value = fake_client

        response = api_client.get(f"/api/projects/{self.project_id}/tasks?module_slug=missing-module")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    @patch("app.api.routes.projects.get_supabase_client")
    def test_module_slug_filter_is_scoped_to_requested_project(self, get_client):
        api_client, fake_client = self._api_client()
        get_client.return_value = fake_client

        response = api_client.get(f"/api/projects/{self.other_project_id}/tasks?module_slug=data-cleaning")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual([task["id"] for task in payload], [str(self.other_project_task_id)])
        self.assertEqual(payload[0]["module_id"], str(self.other_cleaning_module_id))

    @patch("app.api.routes.projects.get_supabase_client")
    def test_published_release_scopes_module_task_and_blueprint_identity(self, get_client):
        release_id = uuid4()
        retired_module_id = uuid4()
        published_module_id = uuid4()
        published_task_id = uuid4()
        assignment_key = uuid4()
        project = project_record(self.project_id)
        project["published_release_id"] = str(release_id)
        records = {
            "projects": [project],
            "modules": [
                {**module_record(retired_module_id, self.project_id, "Data Cleaning"), "release_id": str(uuid4())},
                {**module_record(published_module_id, self.project_id, "Data Cleaning"), "release_id": str(release_id)},
            ],
            "tasks": [
                {
                    **task_record(published_task_id, self.project_id, published_module_id, "Clean published records"),
                    "release_id": str(release_id),
                    "reference_solution": {"blueprint_task_key": str(assignment_key)},
                },
            ],
        }
        api_client, fake_client = self._api_client(records=records)
        get_client.return_value = fake_client

        response = api_client.get(f"/api/projects/{self.project_id}/tasks?module_slug=data-cleaning")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)
        self.assertEqual(response.json()[0]["id"], str(published_task_id))
        self.assertEqual(response.json()[0]["module_id"], str(published_module_id))
        self.assertEqual(response.json()[0]["blueprint_task_key"], str(assignment_key))

    @patch("app.api.routes.projects.get_supabase_client")
    def test_learner_cannot_discover_tasks_for_unpublished_project(self, get_client):
        records = {
            **self.records,
            "projects": [project_record(self.project_id, status="draft")],
        }
        api_client, fake_client = self._api_client(records=records)
        get_client.return_value = fake_client

        response = api_client.get(f"/api/projects/{self.project_id}/tasks?module_slug=data-cleaning")

        self.assertEqual(response.status_code, 404)

    @patch("app.api.routes.projects.get_supabase_client")
    def test_unfiltered_task_listing_still_returns_all_active_project_tasks(self, get_client):
        api_client, fake_client = self._api_client()
        get_client.return_value = fake_client

        response = api_client.get(f"/api/projects/{self.project_id}/tasks")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [task["id"] for task in response.json()],
            [str(self.cleaning_task_id), str(self.sql_task_id)],
        )

    @patch("app.api.routes.projects.get_supabase_client")
    def test_business_owner_can_list_own_project_tasks(self, get_client):
        owner = UserProfile(id=str(uuid4()), email="owner@example.com", role="business")
        records = {**self.records, "projects": [project_record(self.project_id, owner_id=owner.id)]}
        get_client.return_value = FakeClient(records)

        tasks = list_project_tasks(self.project_id, None, owner)

        self.assertEqual(len(tasks), 2)

    @patch("app.api.routes.projects.get_supabase_client")
    def test_business_owner_cannot_list_another_users_project_tasks(self, get_client):
        owner = UserProfile(id=str(uuid4()), email="owner@example.com", role="business")
        records = {**self.records, "projects": [project_record(self.project_id, owner_id=str(uuid4()))]}
        get_client.return_value = FakeClient(records)

        with self.assertRaises(HTTPException) as context:
            list_project_tasks(self.project_id, None, owner)

        self.assertEqual(context.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
