import csv
import io
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from fastapi import HTTPException

from app.api.routes.datasets import _inspect_csv
from app.api.routes.projects import list_available_projects
from app.core.auth import AuthenticatedUser
from app.schemas.auth import UserProfile
from app.schemas.blueprints import BlueprintRecord, ProjectBlueprint
from app.services.blueprint_service import _learner_project, _validate_dataset_fields, _validate_task_grounding, build_blueprint_overview


def _blueprint(**task_changes) -> ProjectBlueprint:
    task = {
        "title": "Produce an analysis",
        "workplace_context": "A manager needs a reliable weekly view.",
        "instruction": "Analyze the supplied data and report the result.",
        "expected_outcome": "A concise result with a business interpretation.",
        "difficulty": "easy",
        "task_kind": "analysis",
        "related_module": "Analysis",
        "related_competencies": ["Data analysis"],
        "related_concepts": ["Grouping"],
        "dataset_fields": ["Department"],
        "evaluation_criteria": [{
            "name": "Result correctness",
            "description": "The result answers the business question.",
            "what_should_be_checked": "Check the result against the supplied fields.",
            "evaluation_type": "deterministic",
        }],
    }
    task.update(task_changes)
    return ProjectBlueprint.model_validate({
        "project_summary": "A grounded project summary.",
        "workplace_goal": "Help the team make a better decision.",
        "modules": [{
            "name": "Analysis",
            "description": "Analysis skills.",
            "rationale": "The project needs analysis.",
            "competencies": [{
                "name": "Data analysis",
                "description": "Analyze business data.",
                "concepts": [{"name": "Grouping", "description": "Group records."}],
            }],
        }],
        "tasks": [task],
    })


def _dataset_profile() -> dict:
    return {
        "file_name": "employees.csv",
        "schema_metadata": {
            "table_name": "employees",
            "columns": [
                {"name": "Department", "missing_count": 0},
                {"name": "Salary", "missing_count": 1},
            ],
        },
    }


class BlueprintQualityTests(unittest.TestCase):
    def test_learner_projects_require_active_project_and_approved_blueprint(self) -> None:
        project_id = uuid4()

        class Query:
            def __init__(self, table: str):
                self.table = table

            def select(self, *_args):
                return self

            def eq(self, *_args):
                return self

            def in_(self, *_args):
                return self

            def order(self, *_args, **_kwargs):
                return self

            def execute(self):
                if self.table == "project_blueprints":
                    return SimpleNamespace(data=[{"project_id": str(project_id), "blueprint_json": _blueprint().model_dump(mode="json")}])
                return SimpleNamespace(data=[{"id": str(project_id), "name": "Published project", "slug": "published-project", "desired_outcome": "A useful result."}])

        class Client:
            def table(self, table: str):
                return Query(table)

        learner = UserProfile(id=str(uuid4()), email="learner@example.com", role="learner")
        with patch("app.api.routes.projects.get_supabase_client", return_value=Client()):
            projects = list_available_projects(learner)

        self.assertEqual([project.id for project in projects], [project_id])
        self.assertEqual(projects[0].work_areas[0].name, "Analysis")
        self.assertNotIn("competencies", projects[0].model_dump())
        self.assertNotIn("evaluation_criteria", projects[0].model_dump())

    @patch("app.services.blueprint_service.get_supabase_client")
    @patch("app.services.blueprint_service._get_project")
    def test_learner_overview_rejects_active_project_without_approved_blueprint(self, get_project, get_client) -> None:
        get_project.return_value = {"id": str(uuid4()), "status": "active"}

        class Query:
            def select(self, *_args):
                return self

            def eq(self, *_args):
                return self

            def limit(self, *_args):
                return self

            def execute(self):
                return SimpleNamespace(data=[])

        class Client:
            def table(self, _table: str):
                return Query()

        get_client.return_value = Client()
        learner = UserProfile(id=str(uuid4()), email="learner@example.com", role="learner")

        with self.assertRaises(HTTPException) as error:
            _learner_project(uuid4(), AuthenticatedUser(id=learner.id, email=learner.email), learner)

        self.assertEqual(error.exception.status_code, 404)

    def test_profile_calculates_employee_scale_facts(self) -> None:
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["EmployeeID", "Department", "Salary", "PerformanceScore", "HireYear", "Remote", "Region", "Manager"])
        for row_number in range(1000):
            writer.writerow([row_number, "Sales", 50000 + row_number, 1 + row_number % 5, 2020, "true", "North", "Manager A"])

        row_count, column_count, profile = _inspect_csv(output.getvalue().encode(), "employees.csv")

        self.assertEqual((row_count, column_count), (1000, 8))
        self.assertEqual([column["name"] for column in profile["columns"]], ["EmployeeID", "Department", "Salary", "PerformanceScore", "HireYear", "Remote", "Region", "Manager"])
        self.assertEqual(profile["columns"][2]["min"], 50000)
        self.assertEqual(profile["columns"][2]["max"], 50999)
        self.assertTrue(all(column["missing_count"] == 0 for column in profile["columns"]))

    def test_unknown_dataset_field_is_rejected(self) -> None:
        with self.assertRaises(HTTPException):
            _validate_dataset_fields(_blueprint(dataset_fields=["NotAColumn"]), [_dataset_profile()])

    def test_unknown_hierarchy_reference_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            _blueprint(related_competencies=["NotACompetency"])

    def test_unknown_sql_table_and_single_table_join_are_rejected(self) -> None:
        sql_task = {
            "task_kind": "sql",
            "sql_tables": ["missing_table"],
            "sql_concepts": ["SELECT"],
            "instruction": "Write a SQL query.",
        }
        with self.assertRaises(HTTPException):
            _validate_task_grounding(_blueprint(**sql_task), [_dataset_profile()])

        join_task = {
            "task_kind": "sql",
            "sql_tables": ["employees"],
            "sql_concepts": ["JOIN"],
            "instruction": "Write a SQL query using a JOIN.",
        }
        with self.assertRaises(HTTPException):
            _validate_task_grounding(_blueprint(**join_task), [_dataset_profile()])

    def test_unsupported_missing_value_claim_is_rejected(self) -> None:
        with self.assertRaises(HTTPException):
            _validate_task_grounding(
                _blueprint(instruction="Verify that missing values are zero for every column."),
                [_dataset_profile()],
            )

    def test_valid_project_with_different_fields_is_accepted(self) -> None:
        profile = {
            "file_name": "visits.csv",
            "schema_metadata": {
                "table_name": "visits",
                "columns": [{"name": "VisitType", "missing_count": 0}],
            },
        }
        blueprint = _blueprint(dataset_fields=["VisitType"])
        _validate_dataset_fields(blueprint, [profile])
        _validate_task_grounding(blueprint, [profile])

    def test_overview_projects_persisted_data_without_internal_hierarchy(self) -> None:
        project_id = uuid4()
        record = BlueprintRecord(
            id=uuid4(),
            project_id=project_id,
            version=2,
            status="approved",
            source_dataset_ids=[],
            blueprint_json=_blueprint(),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        overview = build_blueprint_overview(record, {
            "name": "A future project",
            "desired_outcome": "A decision-ready result.",
        })

        self.assertEqual(overview.project_name, "A future project")
        self.assertEqual(overview.version, 2)
        self.assertEqual(overview.work_areas[0].name, "Analysis")
        self.assertEqual(overview.assignments[0].related_work_area, "Analysis")
        self.assertNotIn("competencies", overview.model_dump())
        self.assertNotIn("concepts", overview.model_dump())
        self.assertNotIn("evaluation_criteria", overview.model_dump())

    def test_overview_separates_work_area_method_and_outcome_from_task_output(self) -> None:
        project_id = uuid4()
        blueprint = _blueprint(
            instruction="Inspect the supplied records, group them by department, and calculate the requested metrics.",
            expected_outcome="A result set showing each department and its corresponding average salary.",
        )
        record = BlueprintRecord(
            id=uuid4(),
            project_id=project_id,
            version=2,
            status="approved",
            source_dataset_ids=[],
            blueprint_json=blueprint,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        overview = build_blueprint_overview(record, {"name": "Employee project", "desired_outcome": "Decision-ready analysis."})

        self.assertEqual(overview.work_areas[0].how_it_will_be_done, blueprint.tasks[0].instruction)
        self.assertEqual(overview.work_areas[0].expected_outcome, blueprint.modules[0].description)
        self.assertEqual(overview.assignments[0].expected_output, blueprint.tasks[0].expected_outcome)


if __name__ == "__main__":
    unittest.main()