import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from fastapi import HTTPException

from app.api.routes.projects import _publish_project, update_project
from app.core.auth import AuthenticatedUser
from app.schemas.auth import UserProfile
from app.schemas.projects import ProjectUpdate


class FakeQuery:
    def __init__(self, client, table_name):
        self.client = client
        self.table_name = table_name
        self.data = client.records.get(table_name, [])

    def select(self, *_args):
        return self

    def eq(self, field, value):
        self.data = [record for record in self.data if str(record.get(field)) == str(value)]
        return self

    def order(self, *_args, **_kwargs):
        return self

    def limit(self, count):
        self.data = self.data[:count]
        return self

    def update(self, changes):
        self.client.operations.append(("update", self.table_name, changes))
        self.update_changes = changes
        return self

    def execute(self):
        if hasattr(self, "update_changes"):
            self.data = [{**record, **self.update_changes} for record in self.data]
        return SimpleNamespace(data=self.data)


class FakeClient:
    def __init__(self, records):
        self.records = records
        self.operations = []

    def table(self, table_name):
        return FakeQuery(self, table_name)


def project_record(project_id, owner_id, project_status="draft"):
    timestamp = datetime.now(timezone.utc)
    return {
        "id": str(project_id),
        "name": "Project",
        "slug": "project",
        "business_problem": "Problem",
        "work_requirements": "Requirements",
        "desired_outcome": "Outcome",
        "created_by": owner_id,
        "status": project_status,
        "created_at": timestamp.isoformat(),
        "updated_at": timestamp.isoformat(),
    }


def approved_blueprint(project_id):
    return {
        "id": str(uuid4()),
        "project_id": str(project_id),
        "version": 1,
        "status": "approved",
        "blueprint_json": {
            "project_summary": "A project summary.",
            "workplace_goal": "A useful result.",
            "modules": [{
                "name": "Analysis",
                "description": "Analyze data.",
                "rationale": "Use the data.",
                "competencies": [{
                    "name": "Analysis",
                    "description": "Analyze records.",
                    "concepts": [{"name": "Grouping", "description": "Group records."}],
                }],
            }],
            "tasks": [{
                "title": "Analyze records",
                "workplace_context": "A team needs an answer.",
                "instruction": "Analyze records.",
                "expected_outcome": "A useful answer.",
                "difficulty": "easy",
                "task_kind": "analysis",
                "related_module": "Analysis",
                "related_competencies": ["Analysis"],
                "related_concepts": ["Grouping"],
                "dataset_fields": [],
                "sql_tables": [],
                "sql_concepts": [],
                "evaluation_criteria": [{
                    "name": "Correctness",
                    "description": "The answer is correct.",
                    "what_should_be_checked": "Check the answer.",
                    "evaluation_type": "qualitative",
                }],
            }],
        },
    }


class ProjectPublishingTests(unittest.TestCase):
    def setUp(self):
        self.project_id = uuid4()
        self.user = AuthenticatedUser(id=str(uuid4()), email="business@example.com")
        self.business = UserProfile(id=self.user.id, email=self.user.email, role="business")
        self.project = project_record(self.project_id, self.user.id)

    def client(self, *, blueprint=True, modules=True, tasks=True):
        return FakeClient({
            "project_blueprints": [approved_blueprint(self.project_id)] if blueprint else [],
            "modules": [{"id": str(uuid4()), "project_id": str(self.project_id), "status": "active"}] if modules else [],
            "tasks": [{"id": str(uuid4()), "project_id": str(self.project_id), "status": "active"}] if tasks else [],
            "projects": [self.project],
        })

    @patch("app.api.routes.projects._get_project")
    @patch("app.api.routes.projects.get_supabase_client")
    def test_business_owner_can_publish_prepared_project(self, get_client, get_project):
        client = self.client()
        get_project.return_value = self.project
        get_client.return_value = client

        result = _publish_project(self.project_id, self.user, self.business)

        self.assertEqual(result.status, "active")
        self.assertEqual(client.operations, [("update", "projects", {"status": "active"})])

    @patch("app.api.routes.projects._get_project")
    def test_learner_cannot_publish(self, get_project):
        learner = UserProfile(id=str(uuid4()), email="learner@example.com", role="learner")

        with self.assertRaises(HTTPException) as error:
            _publish_project(self.project_id, self.user, learner)

        self.assertEqual(error.exception.status_code, 403)
        get_project.assert_not_called()

    @patch("app.api.routes.projects._get_project")
    def test_business_user_cannot_publish_another_users_project(self, get_project):
        get_project.return_value = project_record(self.project_id, str(uuid4()))

        with self.assertRaises(HTTPException) as error:
            _publish_project(self.project_id, self.user, self.business)

        self.assertEqual(error.exception.status_code, 404)

    @patch("app.api.routes.projects._get_project")
    @patch("app.api.routes.projects.get_supabase_client")
    def test_project_without_approved_blueprint_cannot_publish(self, get_client, get_project):
        get_project.return_value = self.project
        get_client.return_value = self.client(blueprint=False)

        with self.assertRaises(HTTPException) as error:
            _publish_project(self.project_id, self.user, self.business)

        self.assertEqual(error.exception.status_code, 409)

    @patch("app.api.routes.projects._get_project")
    @patch("app.api.routes.projects.get_supabase_client")
    def test_project_without_materialized_structure_cannot_publish(self, get_client, get_project):
        get_project.return_value = self.project
        get_client.return_value = self.client(modules=False)

        with self.assertRaises(HTTPException) as error:
            _publish_project(self.project_id, self.user, self.business)

        self.assertEqual(error.exception.status_code, 409)

    @patch("app.api.routes.projects._get_project")
    @patch("app.api.routes.projects.get_supabase_client")
    def test_already_published_project_is_idempotent(self, get_client, get_project):
        active_project = project_record(self.project_id, self.user.id, "active")
        client = self.client()
        get_project.return_value = active_project
        get_client.return_value = client

        result = _publish_project(self.project_id, self.user, self.business)

        self.assertEqual(result.status, "active")
        self.assertEqual(client.operations, [])

    @patch("app.api.routes.projects._get_project")
    @patch("app.api.routes.projects.get_supabase_client")
    def test_publishing_does_not_modify_blueprint_data(self, get_client, get_project):
        client = self.client()
        blueprint_before = client.records["project_blueprints"][0].copy()
        get_project.return_value = self.project
        get_client.return_value = client

        _publish_project(self.project_id, self.user, self.business)

        self.assertEqual(client.records["project_blueprints"][0], blueprint_before)
        self.assertFalse(any(operation[1] == "project_blueprints" and operation[0] == "update" for operation in client.operations))

    @patch("app.api.routes.projects._get_project")
    @patch("app.api.routes.projects.get_supabase_client")
    def test_publishing_does_not_modify_runtime_tables(self, get_client, get_project):
        client = self.client()
        get_project.return_value = self.project
        get_client.return_value = client

        _publish_project(self.project_id, self.user, self.business)

        self.assertFalse(any(operation[1] in {"modules", "tasks"} for operation in client.operations))

    @patch("app.api.routes.projects._get_project")
    @patch("app.api.routes.projects.get_supabase_client")
    def test_draft_project_can_still_be_edited(self, get_client, get_project):
        client = self.client()
        get_project.return_value = self.project
        get_client.return_value = client

        result = update_project(
            self.project_id,
            ProjectUpdate(name="Updated project"),
            self.user,
            self.business,
        )

        self.assertEqual(result.name, "Updated project")
        self.assertEqual(client.operations, [("update", "projects", {"name": "Updated project"})])

    @patch("app.api.routes.projects._get_project")
    @patch("app.api.routes.projects.get_supabase_client")
    def test_published_project_cannot_be_edited(self, get_client, get_project):
        active_project = project_record(self.project_id, self.user.id, "active")
        client = self.client()
        get_project.return_value = active_project
        get_client.return_value = client

        with self.assertRaises(HTTPException) as error:
            update_project(
                self.project_id,
                ProjectUpdate(name="Must not change"),
                self.user,
                self.business,
            )

        self.assertEqual(error.exception.status_code, 409)
        self.assertEqual(client.operations, [])


if __name__ == "__main__":
    unittest.main()