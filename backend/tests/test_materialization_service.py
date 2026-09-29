import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

from fastapi import HTTPException

from app.schemas.auth import AuthenticatedUser, UserProfile
from app.services.materialization_service import materialize_project


class FakeQuery:
    def __init__(self, data):
        self.data = data

    def select(self, *_args):
        return self

    def eq(self, *_args):
        return self

    def order(self, *_args, **_kwargs):
        return self

    def limit(self, *_args):
        return self

    def execute(self):
        return SimpleNamespace(data=self.data)


class FakeClient:
    def __init__(self, approved_blueprints, rpc_error=None):
        self.approved_blueprints = approved_blueprints
        self.rpc_error = rpc_error
        self.rpc_calls = []

    def table(self, table_name):
        if table_name == "project_blueprints":
            return FakeQuery(self.approved_blueprints)
        raise AssertionError(f"Unexpected table access: {table_name}")

    def rpc(self, function_name, arguments):
        self.rpc_calls.append((function_name, arguments))
        if self.rpc_error:
            raise self.rpc_error
        return FakeQuery({
            "status": "materialized",
            "blueprint_version": 2,
            "modules_created": 2,
            "competencies_created": 3,
            "concepts_created": 4,
            "tasks_created": 3,
            "task_competencies_created": 3,
            "task_concepts_created": 3,
            "rubrics_created": 3,
        })


class MaterializationServiceTests(unittest.TestCase):
    def setUp(self):
        self.project_id = uuid4()
        self.user = AuthenticatedUser(id=str(uuid4()), email="business@example.com")
        self.profile = UserProfile(id=self.user.id, email=self.user.email, role="business")
        self.project = {"id": str(self.project_id), "created_by": self.user.id}

    @staticmethod
    def valid_blueprint() -> dict:
        return {
            "project_summary": "A valid project.",
            "workplace_goal": "Produce a useful result.",
            "modules": [{
                "name": "Analysis",
                "description": "Analyze the data.",
                "rationale": "Use the available data.",
                "competencies": [{
                    "name": "Data analysis",
                    "description": "Analyze records.",
                    "concepts": [{"name": "Grouping", "description": "Group records."}],
                }],
            }],
            "tasks": [{
                "task_key": str(uuid4()),
                "title": "Analyze records",
                "workplace_context": "A team needs an answer.",
                "instruction": "Analyze the records.",
                "expected_outcome": "A useful answer.",
                "difficulty": "easy",
                "task_kind": "analysis",
                "related_module": "Analysis",
                "related_competencies": ["Data analysis"],
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
        }

    @patch("app.services.materialization_service.get_supabase_client")
    @patch("app.services.materialization_service._get_project")
    def test_approved_blueprint_version_is_sent_to_single_rpc(self, get_project, get_client):
        client = FakeClient([{ "id": str(uuid4()), "version": 2, "status": "approved", "blueprint_json": self.valid_blueprint() }])
        get_project.return_value = self.project
        get_client.return_value = client

        result = materialize_project(self.project_id, self.user, self.profile)

        self.assertEqual(result.status, "materialized")
        self.assertEqual(result.blueprint_version, 2)
        self.assertEqual(client.rpc_calls[0][0], "materialize_approved_blueprint")
        self.assertEqual(client.rpc_calls[0][1]["target_project_id"], str(self.project_id))

    @patch("app.services.materialization_service._get_project")
    def test_learner_is_rejected_before_database_access(self, get_project):
        learner = UserProfile(id=str(uuid4()), email="learner@example.com", role="learner")

        with self.assertRaises(HTTPException) as error:
            materialize_project(self.project_id, self.user, learner)

        self.assertEqual(error.exception.status_code, 403)
        get_project.assert_not_called()

    @patch("app.services.materialization_service.get_supabase_client")
    @patch("app.services.materialization_service._get_project")
    def test_missing_approved_blueprint_is_rejected(self, get_project, get_client):
        get_project.return_value = self.project
        get_client.return_value = FakeClient([])

        with self.assertRaises(HTTPException) as error:
            materialize_project(self.project_id, self.user, self.profile)

        self.assertEqual(error.exception.status_code, 409)

    @patch("app.services.materialization_service.get_supabase_client")
    @patch("app.services.materialization_service._get_project")
    def test_invalid_approved_blueprint_is_rejected_before_rpc(self, get_project, get_client):
        client = FakeClient([{ "id": str(uuid4()), "version": 2, "status": "approved", "blueprint_json": {} }])
        get_project.return_value = self.project
        get_client.return_value = client

        with self.assertRaises(HTTPException) as error:
            materialize_project(self.project_id, self.user, self.profile)

        self.assertEqual(error.exception.status_code, 422)
        self.assertEqual(client.rpc_calls, [])

    @patch("app.services.materialization_service.get_supabase_client")
    @patch("app.services.materialization_service._get_project")
    def test_legacy_blueprint_without_persisted_task_keys_requires_revision(self, get_project, get_client):
        old_blueprint = self.valid_blueprint()
        old_blueprint["tasks"][0].pop("task_key")
        client = FakeClient([{"id": str(uuid4()), "version": 2, "status": "approved", "blueprint_json": old_blueprint}])
        get_project.return_value = self.project
        get_client.return_value = client

        with self.assertRaises(HTTPException) as error:
            materialize_project(self.project_id, self.user, self.profile)

        self.assertEqual(error.exception.status_code, 409)
        self.assertIn("blueprint revision", error.exception.detail)
        self.assertEqual(client.rpc_calls, [])

    @patch("app.services.materialization_service.get_supabase_client")
    @patch("app.services.materialization_service._get_project")
    def test_published_release_immutability_rejection_is_not_bypassed(self, get_project, get_client):
        client = FakeClient(
            [{"id": str(uuid4()), "version": 2, "status": "approved", "blueprint_json": self.valid_blueprint()}],
            rpc_error=RuntimeError("Published or superseded releases are immutable"),
        )
        get_project.return_value = self.project
        get_client.return_value = client

        with self.assertRaises(HTTPException) as error:
            materialize_project(self.project_id, self.user, self.profile)

        self.assertEqual(error.exception.status_code, 422)
        self.assertEqual(len(client.rpc_calls), 1)

    @patch("app.services.materialization_service.get_supabase_client")
    @patch("app.services.materialization_service._get_project")
    def test_project_access_is_checked_before_rpc(self, get_project, get_client):
        another_owner = AuthenticatedUser(id=str(uuid4()), email="other@example.com")
        get_project.return_value = {"id": str(self.project_id), "created_by": another_owner.id}
        client = Mock()
        get_client.return_value = client

        with self.assertRaises(HTTPException) as error:
            materialize_project(self.project_id, self.user, self.profile)

        self.assertEqual(error.exception.status_code, 404)
        client.rpc.assert_not_called()


if __name__ == "__main__":
    unittest.main()