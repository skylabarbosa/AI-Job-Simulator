"""Tests for task submission and deterministic validation.

Gemini/LLM calls: ZERO.
"""

import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.core.auth import get_current_profile, get_current_user
from app.schemas.auth import AuthenticatedUser, UserProfile
from app.schemas.submissions import SubmissionCreate
from app.services.evaluation_service import (
    DataAnalysisEvaluator,
    DataCleaningEvaluator,
    FallbackEvaluator,
    SQLEvaluator,
    evaluator_for_task_type,
)
from app.services.submission_service import submit_task_work
from main import create_app


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_project(project_id, *, status="active"):
    return {"id": str(project_id), "name": "Project", "status": status}


def make_blueprint(project_id):
    return {"id": str(uuid4()), "project_id": str(project_id), "status": "approved"}


def make_task(
    task_id,
    project_id,
    *,
    task_type="sql",
    reference_solution=None,
    status="active",
    instructions=None,
    expected_outcome=None,
):
    return {
        "id": str(task_id),
        "project_id": str(project_id),
        "module_id": str(uuid4()),
        "title": "Generic task",
        "instructions": instructions,
        "task_type": task_type,
        "expected_outcome": expected_outcome,
        "reference_solution": reference_solution
        if reference_solution is not None
        else {
            "sql_tables": ["employees"],
            "dataset_fields": ["department", "salary"],
            "sql_concepts": ["SELECT", "GROUP BY", "Aggregates"],
        },
        "status": status,
    }


def make_simulation(sim_id, learner_id, project_id, task_id, *, status="active"):
    return {
        "id": str(sim_id),
        "learner_id": str(learner_id),
        "project_id": str(project_id),
        "current_task_id": str(task_id),
        "status": status,
        "started_at": _ts(),
    }


class FakeQuery:
    def __init__(self, client, table_name: str):
        self.client = client
        self.table_name = table_name
        self._data = list(client.records.get(table_name, []))
        self._single = False
        self._filters_applied = False
        self._pending_update = None

    def select(self, *_):
        return self

    def eq(self, field, value):
        self._filters_applied = True
        self._data = [row for row in self._data if str(row.get(field)) == str(value)]
        return self

    def in_(self, field, values):
        self._filters_applied = True
        expected = {str(value) for value in values}
        self._data = [row for row in self._data if str(row.get(field)) in expected]
        return self

    def order(self, field, *, desc=False):
        self._data = sorted(self._data, key=lambda row: row.get(field) or 0, reverse=desc)
        return self

    def limit(self, n):
        self._data = self._data[:n]
        return self

    def maybe_single(self):
        self._single = True
        self._data = self._data[:1]
        return self

    def insert(self, payload):
        self.client.operations.append(("insert", self.table_name, payload))
        row = {"id": str(uuid4()), "created_at": _ts(), "updated_at": _ts(), **payload}
        self.client.records.setdefault(self.table_name, []).append(row)
        self._data = [row]
        return self

    def update(self, payload):
        if self._filters_applied:
            raise AttributeError("'NoneType' object has no attribute 'data'")
        self.client.operations.append(("update", self.table_name, payload))
        self._pending_update = payload
        return self

    def execute(self):
        if self._pending_update is not None:
            updated = []
            for row in self.client.records.get(self.table_name, []):
                if row in self._data:
                    row.update(self._pending_update)
                    updated.append(row)
            self._data = updated
        if self._single:
            return SimpleNamespace(data=self._data[0] if self._data else None)
        return SimpleNamespace(data=self._data)


class FakeClient:
    def __init__(self, records):
        self.records = {key: list(value) for key, value in records.items()}
        self.operations = []

    def table(self, table_name: str):
        self.operations.append(("select", table_name, None))
        return FakeQuery(self, table_name)


class TestTaskSubmissions(unittest.TestCase):
    def setUp(self):
        self.learner_id = str(uuid4())
        self.other_learner_id = str(uuid4())
        self.project_id = uuid4()
        self.other_project_id = uuid4()
        self.task_id = uuid4()
        self.simulation_id = uuid4()
        self.base_records = {
            "projects": [make_project(self.project_id)],
            "project_blueprints": [make_blueprint(self.project_id)],
            "tasks": [make_task(self.task_id, self.project_id)],
            "simulations": [
                make_simulation(
                    self.simulation_id,
                    self.learner_id,
                    self.project_id,
                    self.task_id,
                )
            ],
            "submissions": [],
            "rubrics": [{"id": str(uuid4()), "task_id": str(self.task_id), "criteria": [], "status": "active", "version": 1}],
            "task_competencies": [],
            "task_concepts": [],
            "evaluations": [],
            "user_skills": [],
        }

    def _client(self, overrides=None):
        return FakeClient({**self.base_records, **(overrides or {})})

    def _submit(self, client, response="SELECT department, AVG(salary) FROM employees GROUP BY department"):
        with patch("app.services.submission_service.get_supabase_client", return_value=client):
            return submit_task_work(
                learner_id=self.learner_id,
                project_id=self.project_id,
                task_id=self.task_id,
                payload=SubmissionCreate(response=response),
            )

    def _route_client(self, *, role="learner"):
        app = create_app()
        app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
            id=self.learner_id,
            email="learner@example.com",
        )
        app.dependency_overrides[get_current_profile] = lambda: UserProfile(
            id=self.learner_id,
            email="learner@example.com",
            role=role,
        )
        return TestClient(app)

    def test_authenticated_learner_can_submit_valid_started_task(self):
        client = self._client()
        result = self._submit(client)

        self.assertEqual(result.validation_status, "passed")
        self.assertEqual(len(client.records["submissions"]), 1)
        submission = client.records["submissions"][0]
        self.assertEqual(submission["learner_id"], self.learner_id)
        self.assertEqual(submission["simulation_id"], str(self.simulation_id))
        self.assertEqual(submission["task_id"], str(self.task_id))
        self.assertEqual(submission["status"], "submitted")
        self.assertEqual(submission["attempt_number"], 1)
        self.assertIsNotNone(result.evaluation_id)

    def test_sql_run_check_validates_without_creating_submission(self):
        client = self._client()
        app = create_app()
        app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
            id=self.learner_id,
            email="learner@example.com",
        )
        app.dependency_overrides[get_current_profile] = lambda: UserProfile(
            id=self.learner_id,
            email="learner@example.com",
            role="learner",
        )
        with (
            patch("app.services.submission_service.get_supabase_client", return_value=client),
            patch("app.services.submission_service.execute_task_sql", return_value={
                "execution_status": "success",
                "columns": ["department", "salary"],
                "rows": [["Sales", "10"]],
                "row_count": 1,
                "displayed_row_count": 1,
                "truncated": False,
                "execution_time_ms": 1.0,
            }),
        ):
            with TestClient(app) as test_client:
                valid_response = test_client.post(
                    f"/api/projects/{self.project_id}/tasks/{self.task_id}/check",
                    json={"response": "SELECT department, AVG(salary) FROM employees GROUP BY department"},
                )
                self.assertEqual(valid_response.status_code, 200)
                payload = valid_response.json()
                self.assertEqual(payload["validation_status"], "passed")
                self.assertEqual(len(client.records["submissions"]), 0)
                self.assertEqual(len(client.records["evaluations"]), 0)

                invalid_response = test_client.post(
                    f"/api/projects/{self.project_id}/tasks/{self.task_id}/check",
                    json={"response": "SELECT department FROM employees"},
                )
                self.assertEqual(invalid_response.status_code, 200)
                invalid_payload = invalid_response.json()
                self.assertEqual(invalid_payload["validation_status"], "failed")
                self.assertTrue(any(check["name"].startswith("required_field:") for check in invalid_payload["checks"]))

    def test_valid_select_star_sql_submission_passes_and_returns_evaluation_id(self):
        client = self._client(
            {
                "tasks": [
                    make_task(
                        self.task_id,
                        self.project_id,
                        reference_solution={
                            "sql_tables": ["employee_clean_readable"],
                            "dataset_fields": ["Department", "Salary"],
                            "sql_concepts": ["SELECT"],
                        },
                    )
                ]
            }
        )
        result = self._submit(client, response="SELECT * FROM employee_clean_readable;")

        self.assertEqual(result.validation_status, "passed")
        self.assertIsNotNone(result.evaluation_id)
        self.assertEqual(str(result.evaluation_id), client.records["evaluations"][0]["id"])
        self.assertEqual([check.name for check in result.checks], ["deterministic_validation"])

    def test_evaluator_routing_uses_task_type_only(self):
        self.assertIsInstance(evaluator_for_task_type("sql"), SQLEvaluator)
        self.assertIsInstance(evaluator_for_task_type("Data Cleaning"), DataCleaningEvaluator)
        self.assertIsInstance(evaluator_for_task_type("data-analysis"), DataAnalysisEvaluator)
        self.assertIsInstance(evaluator_for_task_type("future_task"), FallbackEvaluator)

    def test_unauthenticated_user_is_rejected(self):
        response = TestClient(create_app()).post(
            f"/api/projects/{self.project_id}/tasks/{self.task_id}/submissions",
            json={"response": "work"},
        )

        self.assertEqual(response.status_code, 401)

    @patch("app.services.submission_service.get_supabase_client")
    def test_non_learner_role_is_rejected(self, mock_get_client):
        client = self._client()
        mock_get_client.return_value = client
        response = self._route_client(role="business").post(
            f"/api/projects/{self.project_id}/tasks/{self.task_id}/submissions",
            json={"response": "work"},
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(client.records["submissions"], [])

    @patch("app.services.submission_service.get_supabase_client")
    def test_submit_and_submissions_routes_use_same_service_response(self, mock_get_client):
        client = self._client()
        mock_get_client.return_value = client
        api_client = self._route_client()

        submit_response = api_client.post(
            f"/api/projects/{self.project_id}/tasks/{self.task_id}/submit",
            json={"response": "SELECT department, AVG(salary) FROM employees GROUP BY department"},
        )
        submissions_response = api_client.post(
            f"/api/projects/{self.project_id}/tasks/{self.task_id}/submissions",
            json={"response": "SELECT department, AVG(salary) FROM employees GROUP BY department"},
        )

        self.assertEqual(submit_response.status_code, 201)
        self.assertEqual(submissions_response.status_code, 201)
        self.assertEqual(submit_response.json()["validation_status"], "passed")
        self.assertEqual(submissions_response.json()["validation_status"], "passed")
        self.assertIsNotNone(submit_response.json()["evaluation_id"])
        self.assertIsNotNone(submissions_response.json()["evaluation_id"])
        self.assertEqual(len(client.records["submissions"]), 2)
        self.assertEqual(len(client.records["evaluations"]), 2)

    def test_learner_cannot_submit_without_active_simulation(self):
        client = self._client({"simulations": []})
        with self.assertRaises(HTTPException) as ctx:
            self._submit(client)

        self.assertEqual(ctx.exception.status_code, 409)
        self.assertEqual(client.records["submissions"], [])

    def test_learner_cannot_submit_to_another_learners_simulation(self):
        client = self._client(
            {
                "simulations": [
                    make_simulation(
                        self.simulation_id,
                        self.other_learner_id,
                        self.project_id,
                        self.task_id,
                    )
                ]
            }
        )
        with self.assertRaises(HTTPException) as ctx:
            self._submit(client)

        self.assertEqual(ctx.exception.status_code, 409)
        self.assertEqual(client.records["submissions"], [])

    def test_learner_cannot_submit_task_from_another_project(self):
        client = self._client(
            {
                "projects": [make_project(self.project_id), make_project(self.other_project_id)],
                "project_blueprints": [
                    make_blueprint(self.project_id),
                    make_blueprint(self.other_project_id),
                ],
            }
        )
        with patch("app.services.submission_service.get_supabase_client", return_value=client):
            with self.assertRaises(HTTPException) as ctx:
                submit_task_work(
                    learner_id=self.learner_id,
                    project_id=self.other_project_id,
                    task_id=self.task_id,
                    payload=SubmissionCreate(response="SELECT * FROM employees"),
                )

        self.assertEqual(ctx.exception.status_code, 404)
        self.assertEqual(client.records["submissions"], [])

    def test_learner_cannot_submit_to_inactive_project(self):
        client = self._client({"projects": [make_project(self.project_id, status="draft")]})
        with self.assertRaises(HTTPException) as ctx:
            self._submit(client)

        self.assertEqual(ctx.exception.status_code, 404)
        self.assertEqual(client.records["submissions"], [])

    def test_learner_id_comes_from_auth_not_request_content(self):
        client = self._client()
        attacker_id = str(uuid4())
        with patch("app.services.submission_service.get_supabase_client", return_value=client):
            submit_task_work(
                learner_id=self.learner_id,
                project_id=self.project_id,
                task_id=self.task_id,
                payload=SubmissionCreate(content={"response": "SELECT * FROM employees", "learner_id": attacker_id}),
            )

        submission = client.records["submissions"][0]
        self.assertEqual(submission["learner_id"], self.learner_id)
        self.assertNotEqual(submission["learner_id"], attacker_id)

    def test_deterministic_validation_runs_without_llm_and_never_executes_sql(self):
        client = self._client()
        with patch("app.services.evaluation_service.get_llm_provider") as mock_llm:
            result = self._submit(client)

        mock_llm.assert_not_called()
        self.assertEqual(result.validation_status, "passed")
        self.assertNotIn(("rpc", "sql", None), client.operations)
        self.assertTrue(any(op[1] == "evaluations" and op[0] == "insert" for op in client.operations))

    def test_failed_deterministic_check_does_not_delete_submission(self):
        client = self._client()
        result = self._submit(client, response="SELECT department FROM employees")

        self.assertEqual(result.validation_status, "failed")
        self.assertEqual(len(client.records["submissions"]), 1)
        self.assertTrue(any(not check.passed for check in result.checks))

    def test_sql_explicit_fields_pass_when_metadata_requires_them(self):
        client = self._client()
        result = self._submit(client, response="SELECT department, AVG(salary) FROM employees GROUP BY department;")

        self.assertEqual(result.validation_status, "passed")

    def test_sql_required_fields_are_only_checked_when_metadata_requires_them(self):
        client = self._client(
            {
                "tasks": [
                    make_task(
                        self.task_id,
                        self.project_id,
                        reference_solution={
                            "sql_tables": ["orders"],
                            "dataset_fields": [],
                            "sql_concepts": ["SELECT"],
                        },
                    )
                ]
            }
        )
        result = self._submit(client, response="SELECT order_id FROM orders;")

        self.assertEqual(result.validation_status, "passed")

    def test_sql_required_table_is_checked_generically(self):
        client = self._client(
            {
                "tasks": [
                    make_task(
                        self.task_id,
                        self.project_id,
                        reference_solution={
                            "sql_tables": ["orders"],
                            "dataset_fields": [],
                            "sql_concepts": ["SELECT"],
                        },
                    )
                ]
            }
        )
        result = self._submit(client, response="SELECT * FROM customers;")

        self.assertEqual(result.validation_status, "failed")
        self.assertTrue(any("orders" in check.message for check in result.checks))

    def test_sql_non_select_and_multiple_statement_fail(self):
        client = self._client()
        non_select = self._submit(client, response="DELETE FROM employees")
        multiple = self._submit(client, response="SELECT * FROM employees; SELECT * FROM employees;")

        self.assertEqual(non_select.validation_status, "failed")
        self.assertEqual(multiple.validation_status, "failed")

    def test_data_analysis_task_routes_to_analysis_evaluator(self):
        client = self._client(
            {
                "tasks": [
                    make_task(
                        self.task_id,
                        self.project_id,
                        task_type="analysis",
                        reference_solution={"sql_tables": [], "dataset_fields": [], "sql_concepts": []},
                    )
                ]
            }
        )
        with patch("app.services.evaluation_service.get_llm_provider", side_effect=Exception("LLM offline")):
            result = self._submit(client, response="Here is my analysis.")

        self.assertEqual(result.validation_status, "needs_evaluation")
        self.assertEqual(result.checks[0].name, "ready_for_review")
        self.assertEqual(len(client.records["submissions"]), 1)

    def test_data_cleaning_task_routes_to_cleaning_evaluator(self):
        client = self._client(
            {
                "tasks": [
                    make_task(
                        self.task_id,
                        self.project_id,
                        task_type="data_cleaning",
                        reference_solution={"dataset_fields": ["name"]},
                    )
                ],
                "rubrics": [
                    {
                        "id": str(uuid4()),
                        "task_id": str(self.task_id),
                        "criteria": [{"name": "Missing value handling", "evaluation_type": "qualitative"}],
                        "status": "active",
                        "version": 1,
                    }
                ],
            }
        )
        with patch("app.services.evaluation_service.get_llm_provider", side_effect=Exception("LLM offline")):
            result = self._submit(client, response="I removed invalid rows and documented missing value handling.")

        self.assertEqual(result.validation_status, "needs_evaluation")
        self.assertEqual(result.checks[0].name, "ready_for_review")

    def test_unknown_task_type_uses_safe_generic_fallback(self):
        client = self._client(
            {
                "tasks": [
                    make_task(
                        self.task_id,
                        self.project_id,
                        task_type="future_task",
                        reference_solution={},
                    )
                ],
            }
        )
        with patch("app.services.evaluation_service.get_llm_provider", side_effect=Exception("LLM offline")):
            result = self._submit(client, response="Future task work.")

        self.assertEqual(result.validation_status, "needs_evaluation")
        self.assertEqual(result.checks[0].name, "ready_for_review")

    def test_data_cleaning_valid_metadata_evidence_passes_deterministically(self):
        client = self._client(
            {
                "tasks": [
                    make_task(
                        self.task_id,
                        self.project_id,
                        task_type="data_cleaning",
                        reference_solution={},
                        instructions="Handle missing values and validate the cleaned output.",
                        expected_outcome="A cleaned customer dataset with validation notes.",
                    )
                ],
                "rubrics": [
                    {
                        "id": str(uuid4()),
                        "task_id": str(self.task_id),
                        "criteria": [{"name": "Cleaning operations", "evaluation_type": "deterministic", "what_should_be_checked": "missing value handling and validation"}],
                        "status": "active",
                        "version": 1,
                    }
                ],
            }
        )

        result = self._submit(client, response="I handled missing values, cleaned the data, and validated the output.")

        self.assertEqual(result.validation_status, "passed")
        self.assertEqual(result.checks[0].name, "deterministic_validation")

    def test_data_cleaning_missing_required_evidence_fails_without_gemini(self):
        client = self._client(
            {
                "tasks": [
                    make_task(
                        self.task_id,
                        self.project_id,
                        task_type="data_cleaning",
                        reference_solution={},
                        instructions="Handle missing values and validate the cleaned output.",
                    )
                ],
                "rubrics": [
                    {
                        "id": str(uuid4()),
                        "task_id": str(self.task_id),
                        "criteria": [{"name": "Cleaning operations", "evaluation_type": "qualitative"}],
                        "status": "active",
                        "version": 1,
                    }
                ],
            }
        )
        with patch("app.services.evaluation_service.get_llm_provider") as mock_llm:
            result = self._submit(client, response="I reviewed the file.")

        mock_llm.assert_not_called()
        self.assertEqual(result.validation_status, "failed")

    def test_data_analysis_valid_metadata_evidence_passes_deterministically(self):
        client = self._client(
            {
                "tasks": [
                    make_task(
                        self.task_id,
                        self.project_id,
                        task_type="data_analysis",
                        reference_solution={},
                        instructions="Explain findings with data evidence and a conclusion.",
                    )
                ],
                "rubrics": [
                    {
                        "id": str(uuid4()),
                        "task_id": str(self.task_id),
                        "criteria": [{"name": "Findings", "evaluation_type": "deterministic", "what_should_be_checked": "findings data evidence conclusion"}],
                        "status": "active",
                        "version": 1,
                    }
                ],
            }
        )

        result = self._submit(client, response="The findings show a trend in the data because the metric changed. My conclusion is to investigate.")

        self.assertEqual(result.validation_status, "passed")

    def test_data_analysis_incomplete_evidence_fails_without_gemini(self):
        client = self._client(
            {
                "tasks": [
                    make_task(
                        self.task_id,
                        self.project_id,
                        task_type="data_analysis",
                        reference_solution={},
                        instructions="Explain findings with data evidence and a conclusion.",
                    )
                ],
                "rubrics": [
                    {
                        "id": str(uuid4()),
                        "task_id": str(self.task_id),
                        "criteria": [{"name": "Findings", "evaluation_type": "qualitative"}],
                        "status": "active",
                        "version": 1,
                    }
                ],
            }
        )
        with patch("app.services.evaluation_service.get_llm_provider") as mock_llm:
            result = self._submit(client, response="Looks fine.")

        mock_llm.assert_not_called()
        self.assertEqual(result.validation_status, "failed")

    def test_obviously_invalid_sql_does_not_call_gemini(self):
        client = self._client()
        with patch("app.services.evaluation_service.get_llm_provider") as mock_llm:
            result = self._submit(client, response="xsxb")

        mock_llm.assert_not_called()
        self.assertEqual(result.validation_status, "failed")
        self.assertEqual(len(client.records["submissions"]), 1)

    def test_duplicate_submissions_create_next_attempt_only(self):
        existing = {
            "id": str(uuid4()),
            "simulation_id": str(self.simulation_id),
            "task_id": str(self.task_id),
            "learner_id": self.learner_id,
            "attempt_number": 1,
            "content": {"response": "first"},
            "status": "submitted",
        }
        client = self._client({"submissions": [existing]})
        self._submit(client)

        attempts = [row["attempt_number"] for row in client.records["submissions"]]
        self.assertEqual(attempts, [1, 2])

    def test_evaluation_record_is_created_without_adaptive_records(self):
        client = self._client()
        self._submit(client)

        inserts = [op for op in client.operations if op[0] == "insert"]
        self.assertEqual([op[1] for op in inserts], ["submissions", "evaluations"])
        self.assertEqual(len(client.records["evaluations"]), 1)
        self.assertEqual(client.records["user_skills"], [])

    def test_existing_skill_evidence_is_updated_with_supabase_update_order(self):
        competency_id = uuid4()
        existing_skill = {
            "id": str(uuid4()),
            "learner_id": self.learner_id,
            "competency_id": str(competency_id),
            "current_score": 10,
            "level": "novice",
        }
        client = self._client(
            {
                "task_competencies": [{"task_id": str(self.task_id), "competency_id": str(competency_id)}],
                "user_skills": [existing_skill],
            }
        )

        result = self._submit(client)

        self.assertEqual(result.validation_status, "passed")
        self.assertEqual(existing_skill["previous_score"], 10)
        self.assertEqual(existing_skill["current_score"], 80)
        self.assertEqual(existing_skill["level"], "proficient")

    def test_skill_evidence_updates_only_submitting_learner(self):
        competency_id = uuid4()
        concept_id = uuid4()
        other_skill = {
            "id": str(uuid4()),
            "learner_id": self.other_learner_id,
            "concept_id": str(concept_id),
            "current_score": 99,
            "level": "advanced",
        }
        client = self._client(
            {
                "task_competencies": [{"task_id": str(self.task_id), "competency_id": str(competency_id)}],
                "task_concepts": [{"task_id": str(self.task_id), "concept_id": str(concept_id)}],
                "user_skills": [other_skill],
            }
        )
        result = self._submit(client)

        self.assertEqual(result.validation_status, "passed")
        learner_skills = [row for row in client.records["user_skills"] if row["learner_id"] == self.learner_id]
        self.assertEqual(len(learner_skills), 2)
        self.assertEqual(other_skill["current_score"], 99)

    def test_duplicate_skill_evidence_is_prevented_for_one_evaluation(self):
        competency_id = uuid4()
        client = self._client(
            {
                "task_competencies": [
                    {"task_id": str(self.task_id), "competency_id": str(competency_id)},
                    {"task_id": str(self.task_id), "competency_id": str(competency_id)},
                ],
            }
        )

        result = self._submit(client)

        learner_skills = [row for row in client.records["user_skills"] if row["learner_id"] == self.learner_id]
        self.assertEqual(result.validation_status, "passed")
        self.assertEqual(len(result.skill_evidence), 1)
        self.assertEqual(len(learner_skills), 1)

    def test_malformed_gemini_output_becomes_needs_evaluation(self):
        class BadProvider:
            def generate(self, _prompt):
                return SimpleNamespace(content="{bad json")

        client = self._client(
            {
                "rubrics": [
                    {
                        "id": str(uuid4()),
                        "task_id": str(self.task_id),
                        "criteria": [{"name": "Interpretation", "evaluation_type": "qualitative"}],
                        "status": "active",
                        "version": 1,
                    }
                ],
            }
        )
        with patch("app.services.evaluation_service.get_llm_provider", return_value=BadProvider()):
            result = self._submit(client)

        self.assertEqual(result.validation_status, "needs_evaluation")
        self.assertEqual(len(client.records["submissions"]), 1)

    def test_structured_semantic_evaluation_returns_safe_feedback(self):
        concept_id = uuid4()

        provider = Mock()
        provider.generate.return_value = SimpleNamespace(
            content=(
                '{"status":"passed","summary":"You explained the pattern clearly.",'
                '"strengths":["Clear reasoning"],"areas_for_improvement":[],'
                '"evidence":["Reasoning was connected to the task"],'
                f'"concept_evidence":[{{"concept_id":"{concept_id}","evidence":"Connected findings to requirements","level":"demonstrated"}}]}}'
            )
        )

        class GoodProvider:
            def generate(self, _prompt):
                return provider.generate(_prompt)

        client = self._client(
            {
                "tasks": [make_task(self.task_id, self.project_id, task_type="analysis", reference_solution={})],
                "task_concepts": [{"task_id": str(self.task_id), "concept_id": str(concept_id)}],
                "rubrics": [
                    {
                        "id": str(uuid4()),
                        "task_id": str(self.task_id),
                        "criteria": [{"name": "Interpretation", "evaluation_type": "qualitative"}],
                        "status": "active",
                        "version": 1,
                    }
                ],
            }
        )
        with patch("app.services.evaluation_service.get_llm_provider", return_value=GoodProvider()):
            result = self._submit(client, response="My analysis explains the pattern.")

        self.assertEqual(result.validation_status, "passed")
        provider.generate.assert_called_once()
        self.assertEqual(result.strengths, ["Clear reasoning"])
        self.assertEqual(len(result.skill_evidence), 1)

    def test_generic_sql_regression_uses_non_employee_metadata(self):
        client = self._client(
            {
                "tasks": [
                    make_task(
                        self.task_id,
                        self.project_id,
                        reference_solution={
                            "sql_tables": ["inventory_items"],
                            "dataset_fields": ["sku", "stock_count"],
                            "sql_concepts": ["SELECT"],
                        },
                    )
                ],
            }
        )

        result = self._submit(client, response="SELECT sku, stock_count FROM inventory_items;")

        self.assertEqual(result.validation_status, "passed")


if __name__ == "__main__":
    unittest.main()
