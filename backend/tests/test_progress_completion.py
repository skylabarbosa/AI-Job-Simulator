"""Phase 3: Progress & Project Completion regression tests.

Tests the full chain:
  Evaluation → Evidence → Task Completion → Competency/Concept Progress
  → Project Progress → Project Completion

Gemini/LLM calls: ZERO.
"""

import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from app.schemas.submissions import SubmissionCreate
from app.services.performance_service import get_project_performance
from app.services.submission_service import submit_task_work


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_project(project_id, *, status="active"):
    return {"id": str(project_id), "name": "Test Project", "status": status}


def make_blueprint(project_id):
    return {"id": str(uuid4()), "project_id": str(project_id), "status": "approved"}


def make_module(module_id, project_id):
    return {
        "id": str(module_id),
        "project_id": str(project_id),
        "name": "Work Area",
        "slug": "work-area",
        "status": "active",
    }


def make_task(
    task_id,
    project_id,
    module_id=None,
    *,
    task_type="sql",
    reference_solution=None,
    status="active",
    position=0,
    title="Test Task",
):
    return {
        "id": str(task_id),
        "project_id": str(project_id),
        "module_id": str(module_id or uuid4()),
        "title": title,
        "instructions": None,
        "task_type": task_type,
        "expected_outcome": None,
        "reference_solution": reference_solution
        if reference_solution is not None
        else {
            "sql_tables": ["items"],
            "dataset_fields": ["name", "price"],
            "sql_concepts": ["SELECT"],
        },
        "status": status,
        "position": position,
        "difficulty": "beginner",
    }


def make_simulation(sim_id, learner_id, project_id, task_id, *, status="active"):
    return {
        "id": str(sim_id),
        "learner_id": str(learner_id),
        "project_id": str(project_id),
        "current_task_id": str(task_id),
        "status": status,
        "started_at": _ts(),
        "progress": 0,
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


class TestTaskCompletion(unittest.TestCase):
    """Step 3: Task completion from evaluation status."""

    def setUp(self):
        self.learner_id = str(uuid4())
        self.project_id = uuid4()
        self.task_id = uuid4()
        self.simulation_id = uuid4()
        self.base_records = {
            "projects": [make_project(self.project_id)],
            "project_blueprints": [make_blueprint(self.project_id)],
            "tasks": [make_task(self.task_id, self.project_id)],
            "simulations": [
                make_simulation(self.simulation_id, self.learner_id, self.project_id, self.task_id)
            ],
            "submissions": [],
            "rubrics": [{"id": str(uuid4()), "task_id": str(self.task_id), "criteria": [], "status": "active", "version": 1}],
            "task_competencies": [],
            "task_concepts": [],
            "evaluations": [],
            "user_skills": [],
            "competencies": [],
            "concepts": [],
        }

    def _client(self, overrides=None):
        return FakeClient({**self.base_records, **(overrides or {})})

    def _submit(self, client, response="SELECT name, price FROM items;"):
        with patch("app.services.submission_service.get_supabase_client", return_value=client):
            return submit_task_work(
                learner_id=self.learner_id,
                project_id=self.project_id,
                task_id=self.task_id,
                payload=SubmissionCreate(response=response),
            )

    def _performance(self, client):
        with patch("app.services.performance_service.get_supabase_client", return_value=client):
            return get_project_performance(
                learner_id=self.learner_id, project_id=self.project_id
            )

    def test_successful_evaluation_marks_task_completed(self):
        client = self._client()
        result = self._submit(client)

        self.assertEqual(result.validation_status, "passed")
        performance = self._performance(client)
        self.assertEqual(performance.completed_tasks, 1)
        self.assertTrue(performance.tasks[0].completed)

    def test_failed_evaluation_does_not_mark_task_completed(self):
        client = self._client()
        result = self._submit(client, response="xsxb")

        self.assertEqual(result.validation_status, "failed")
        performance = self._performance(client)
        self.assertEqual(performance.completed_tasks, 0)
        self.assertFalse(performance.tasks[0].completed)

    def test_needs_evaluation_does_not_mark_task_completed(self):
        client = self._client({
            "tasks": [make_task(self.task_id, self.project_id, task_type="analysis", reference_solution={})],
            "rubrics": [{
                "id": str(uuid4()), "task_id": str(self.task_id),
                "criteria": [{"name": "Quality", "evaluation_type": "qualitative"}],
                "status": "active", "version": 1,
            }],
        })
        with patch("app.services.evaluation_service.get_llm_provider", side_effect=Exception("LLM offline")):
            result = self._submit(client, response="My analysis shows a trend.")

        self.assertEqual(result.validation_status, "needs_evaluation")
        performance = self._performance(client)
        self.assertEqual(performance.completed_tasks, 0)
        self.assertFalse(performance.tasks[0].completed)

    def test_starting_task_does_not_complete_it(self):
        """Starting a simulation (opening a task) must not count as completion."""
        client = self._client()
        # No submissions at all — only a simulation exists.
        performance = self._performance(client)
        self.assertEqual(performance.completed_tasks, 0)
        self.assertFalse(performance.tasks[0].completed)
        self.assertEqual(performance.progress, 0)

    def test_viewing_task_does_not_complete_it(self):
        """Having a simulation row is not completion — completion requires evaluation."""
        client = self._client()
        performance = self._performance(client)
        self.assertEqual(performance.completed_tasks, 0)
        self.assertEqual(performance.progress, 0)


class TestCompletionIdempotency(unittest.TestCase):
    """Step 8: Repeated submissions do not duplicate progress."""

    def setUp(self):
        self.learner_id = str(uuid4())
        self.project_id = uuid4()
        self.task_id = uuid4()
        self.simulation_id = uuid4()
        self.base_records = {
            "projects": [make_project(self.project_id)],
            "project_blueprints": [make_blueprint(self.project_id)],
            "tasks": [make_task(self.task_id, self.project_id)],
            "simulations": [
                make_simulation(self.simulation_id, self.learner_id, self.project_id, self.task_id)
            ],
            "submissions": [],
            "rubrics": [{"id": str(uuid4()), "task_id": str(self.task_id), "criteria": [], "status": "active", "version": 1}],
            "task_competencies": [],
            "task_concepts": [],
            "evaluations": [],
            "user_skills": [],
            "competencies": [],
            "concepts": [],
        }

    def _client(self, overrides=None):
        return FakeClient({**self.base_records, **(overrides or {})})

    def _submit(self, client, response="SELECT name, price FROM items;"):
        with patch("app.services.submission_service.get_supabase_client", return_value=client):
            return submit_task_work(
                learner_id=self.learner_id,
                project_id=self.project_id,
                task_id=self.task_id,
                payload=SubmissionCreate(response=response),
            )

    def _performance(self, client):
        with patch("app.services.performance_service.get_supabase_client", return_value=client):
            return get_project_performance(
                learner_id=self.learner_id, project_id=self.project_id
            )

    def test_failed_then_success_completes_task(self):
        client = self._client()
        r1 = self._submit(client, response="xsxb")
        self.assertEqual(r1.validation_status, "failed")

        r2 = self._submit(client, response="SELECT name, price FROM items;")
        self.assertEqual(r2.validation_status, "passed")

        performance = self._performance(client)
        self.assertEqual(performance.completed_tasks, 1)
        self.assertTrue(performance.tasks[0].completed)
        self.assertEqual(performance.progress, 100)

    def test_success_then_failed_keeps_task_completed(self):
        """A later failed attempt must NOT un-complete a previously passed task."""
        client = self._client()
        r1 = self._submit(client, response="SELECT name, price FROM items;")
        self.assertEqual(r1.validation_status, "passed")

        r2 = self._submit(client, response="xsxb")
        self.assertEqual(r2.validation_status, "failed")

        performance = self._performance(client)
        self.assertEqual(performance.completed_tasks, 1)
        self.assertTrue(performance.tasks[0].completed)
        self.assertEqual(performance.progress, 100)

    def test_success_then_success_does_not_duplicate_progress(self):
        client = self._client()
        self._submit(client, response="SELECT name, price FROM items;")
        self._submit(client, response="SELECT name, price FROM items;")

        performance = self._performance(client)
        self.assertEqual(performance.completed_tasks, 1)
        self.assertEqual(performance.progress, 100)
        self.assertLessEqual(performance.progress, 100)


class TestProjectProgress(unittest.TestCase):
    """Steps 5–6: Project progress and completion."""

    def setUp(self):
        self.learner_id = str(uuid4())
        self.project_id = uuid4()
        self.task1_id = uuid4()
        self.task2_id = uuid4()
        self.task3_id = uuid4()
        self.simulation_id = uuid4()
        self.base_records = {
            "projects": [make_project(self.project_id)],
            "project_blueprints": [make_blueprint(self.project_id)],
            "tasks": [
                make_task(self.task1_id, self.project_id, title="Task 1", position=0),
                make_task(self.task2_id, self.project_id, title="Task 2", position=1),
                make_task(self.task3_id, self.project_id, title="Task 3", position=2),
            ],
            "simulations": [
                make_simulation(self.simulation_id, self.learner_id, self.project_id, self.task1_id)
            ],
            "submissions": [],
            "rubrics": [
                {"id": str(uuid4()), "task_id": str(self.task1_id), "criteria": [], "status": "active", "version": 1},
                {"id": str(uuid4()), "task_id": str(self.task2_id), "criteria": [], "status": "active", "version": 1},
                {"id": str(uuid4()), "task_id": str(self.task3_id), "criteria": [], "status": "active", "version": 1},
            ],
            "task_competencies": [],
            "task_concepts": [],
            "evaluations": [],
            "user_skills": [],
            "competencies": [],
            "concepts": [],
        }

    def _client(self, overrides=None):
        return FakeClient({**self.base_records, **(overrides or {})})

    def _submit(self, client, task_id, response="SELECT name, price FROM items;"):
        # Update simulation's current_task_id for this submission.
        for sim in client.records["simulations"]:
            if sim["learner_id"] == self.learner_id:
                sim["current_task_id"] = str(task_id)
        with patch("app.services.submission_service.get_supabase_client", return_value=client):
            return submit_task_work(
                learner_id=self.learner_id,
                project_id=self.project_id,
                task_id=task_id,
                payload=SubmissionCreate(response=response),
            )

    def _performance(self, client):
        with patch("app.services.performance_service.get_supabase_client", return_value=client):
            return get_project_performance(
                learner_id=self.learner_id, project_id=self.project_id
            )

    def test_zero_completed_gives_zero_progress(self):
        client = self._client()
        performance = self._performance(client)
        self.assertEqual(performance.progress, 0)
        self.assertFalse(performance.completed)
        self.assertEqual(performance.completed_tasks, 0)
        self.assertEqual(performance.total_tasks, 3)

    def test_published_release_excludes_active_legacy_tasks_from_progress(self):
        release_id = uuid4()
        project = {**make_project(self.project_id), "published_release_id": str(release_id)}
        release_tasks = [{**task, "release_id": str(release_id)} for task in self.base_records["tasks"]]
        legacy_task = make_task(uuid4(), self.project_id, title="Legacy task", position=3)
        legacy_task["release_id"] = None
        client = self._client({"projects": [project], "tasks": [*release_tasks, legacy_task]})
        with patch("app.services.performance_service.get_supabase_client", return_value=client):
            performance = get_project_performance(
                learner_id=self.learner_id,
                project_id=self.project_id,
                include_skill_details=False,
            )

        self.assertEqual(performance.total_tasks, 3)
        self.assertEqual(performance.completed_tasks, 0)
        self.assertEqual(performance.progress, 0)

    def test_disabling_skill_details_skips_only_skill_detail_reads(self):
        client = self._client()
        self._submit(client, self.task1_id)
        client.operations.clear()
        with patch("app.services.performance_service.get_supabase_client", return_value=client):
            performance = get_project_performance(learner_id=self.learner_id, project_id=self.project_id, include_skill_details=False)

        queried_tables = [table for operation, table, _ in client.operations if operation == "select"]
        self.assertEqual(performance.total_tasks, 3)
        self.assertEqual(performance.completed_tasks, 1)
        self.assertEqual(performance.progress, 33.33)
        self.assertFalse(performance.completed)
        self.assertEqual(performance.competencies, [])
        self.assertEqual(performance.concepts, [])
        self.assertTrue({"projects", "tasks", "simulations", "submissions", "evaluations"}.issubset(queried_tables))
        self.assertTrue({"user_skills", "task_competencies", "task_concepts", "competencies", "concepts"}.isdisjoint(queried_tables))

    def test_partial_completion_gives_partial_progress(self):
        client = self._client()
        self._submit(client, self.task1_id)

        performance = self._performance(client)
        self.assertAlmostEqual(performance.progress, 33.33, places=1)
        self.assertEqual(performance.completed_tasks, 1)
        self.assertFalse(performance.completed)

    def test_all_completed_gives_100_progress_and_completed_true(self):
        client = self._client()
        self._submit(client, self.task1_id)
        self._submit(client, self.task2_id)
        self._submit(client, self.task3_id)

        performance = self._performance(client)
        self.assertEqual(performance.progress, 100)
        self.assertEqual(performance.completed_tasks, 3)
        self.assertTrue(performance.completed)

    def test_all_started_but_all_failed_is_zero_progress(self):
        client = self._client()
        self._submit(client, self.task1_id, response="xsxb")
        self._submit(client, self.task2_id, response="xsxb")
        self._submit(client, self.task3_id, response="xsxb")

        performance = self._performance(client)
        self.assertEqual(performance.progress, 0)
        self.assertEqual(performance.completed_tasks, 0)
        self.assertFalse(performance.completed)

class TestCompetencyConceptProgress(unittest.TestCase):
    """Step 4: Competency/concept progress from skill evidence."""

    def setUp(self):
        self.learner_id = str(uuid4())
        self.project_id = uuid4()
        self.task_id = uuid4()
        self.simulation_id = uuid4()
        self.competency_id = uuid4()
        self.concept_id = uuid4()
        self.base_records = {
            "projects": [make_project(self.project_id)],
            "project_blueprints": [make_blueprint(self.project_id)],
            "tasks": [make_task(self.task_id, self.project_id)],
            "simulations": [
                make_simulation(self.simulation_id, self.learner_id, self.project_id, self.task_id)
            ],
            "submissions": [],
            "rubrics": [{"id": str(uuid4()), "task_id": str(self.task_id), "criteria": [], "status": "active", "version": 1}],
            "task_competencies": [{"task_id": str(self.task_id), "competency_id": str(self.competency_id)}],
            "task_concepts": [{"task_id": str(self.task_id), "concept_id": str(self.concept_id)}],
            "evaluations": [],
            "user_skills": [],
            "competencies": [{"id": str(self.competency_id), "name": "Test Competency"}],
            "concepts": [{"id": str(self.concept_id), "name": "Test Concept"}],
        }

    def _client(self, overrides=None):
        return FakeClient({**self.base_records, **(overrides or {})})

    def _submit(self, client, response="SELECT name, price FROM items;"):
        with patch("app.services.submission_service.get_supabase_client", return_value=client):
            return submit_task_work(
                learner_id=self.learner_id,
                project_id=self.project_id,
                task_id=self.task_id,
                payload=SubmissionCreate(response=response),
            )

    def _performance(self, client):
        with patch("app.services.performance_service.get_supabase_client", return_value=client):
            return get_project_performance(
                learner_id=self.learner_id, project_id=self.project_id
            )

    def test_passing_evaluation_creates_skill_evidence(self):
        client = self._client()
        result = self._submit(client)

        self.assertEqual(result.validation_status, "passed")
        learner_skills = [row for row in client.records["user_skills"] if row["learner_id"] == self.learner_id]
        self.assertEqual(len(learner_skills), 2)  # competency + concept

    def test_passing_evaluation_reflects_in_competency_progress(self):
        client = self._client()
        self._submit(client)

        performance = self._performance(client)
        self.assertTrue(len(performance.competencies) > 0)
        comp = performance.competencies[0]
        self.assertTrue(comp.demonstrated)

    def test_default_skill_details_remain_available(self):
        client = self._client()
        self._submit(client)

        with patch("app.services.performance_service.get_supabase_client", return_value=client):
            performance = get_project_performance(learner_id=self.learner_id, project_id=self.project_id)

        self.assertEqual(performance.competencies[0].name, "Test Competency")
        self.assertEqual(performance.concepts[0].name, "Test Concept")
        queried_tables = [table for operation, table, _ in client.operations if operation == "select"]
        self.assertTrue({"user_skills", "task_competencies", "task_concepts", "competencies", "concepts"}.issubset(queried_tables))

    def test_passing_evaluation_reflects_in_concept_progress(self):
        client = self._client()
        self._submit(client)

        performance = self._performance(client)
        self.assertTrue(len(performance.concepts) > 0)
        concept = performance.concepts[0]
        self.assertTrue(concept.demonstrated)

    def test_failed_evaluation_does_not_create_demonstrated_evidence(self):
        client = self._client()
        result = self._submit(client, response="xsxb")

        self.assertEqual(result.validation_status, "failed")
        learner_skills = [row for row in client.records["user_skills"] if row["learner_id"] == self.learner_id]
        demonstrated = [s for s in learner_skills if s.get("level") in {"proficient", "advanced"}]
        self.assertEqual(len(demonstrated), 0)


class TestMultiLearnerIsolation(unittest.TestCase):
    """Step 7: Learner isolation."""

    def setUp(self):
        self.learner_a = str(uuid4())
        self.learner_b = str(uuid4())
        self.project_id = uuid4()
        self.task1_id = uuid4()
        self.task2_id = uuid4()
        self.sim_a = uuid4()
        self.sim_b = uuid4()
        self.base_records = {
            "projects": [make_project(self.project_id)],
            "project_blueprints": [make_blueprint(self.project_id)],
            "tasks": [
                make_task(self.task1_id, self.project_id, title="Task 1", position=0),
                make_task(self.task2_id, self.project_id, title="Task 2", position=1),
            ],
            "simulations": [
                make_simulation(self.sim_a, self.learner_a, self.project_id, self.task1_id),
                make_simulation(self.sim_b, self.learner_b, self.project_id, self.task1_id),
            ],
            "submissions": [],
            "rubrics": [
                {"id": str(uuid4()), "task_id": str(self.task1_id), "criteria": [], "status": "active", "version": 1},
                {"id": str(uuid4()), "task_id": str(self.task2_id), "criteria": [], "status": "active", "version": 1},
            ],
            "task_competencies": [],
            "task_concepts": [],
            "evaluations": [],
            "user_skills": [],
            "competencies": [],
            "concepts": [],
        }

    def _client(self, overrides=None):
        return FakeClient({**self.base_records, **(overrides or {})})

    def _submit(self, client, learner_id, task_id, response="SELECT name, price FROM items;"):
        for sim in client.records["simulations"]:
            if sim["learner_id"] == learner_id:
                sim["current_task_id"] = str(task_id)
        with patch("app.services.submission_service.get_supabase_client", return_value=client):
            return submit_task_work(
                learner_id=learner_id,
                project_id=self.project_id,
                task_id=task_id,
                payload=SubmissionCreate(response=response),
            )

    def _performance(self, client, learner_id):
        with patch("app.services.performance_service.get_supabase_client", return_value=client):
            return get_project_performance(
                learner_id=learner_id, project_id=self.project_id
            )

    def test_learner_a_completion_does_not_affect_learner_b(self):
        client = self._client()

        # Learner A completes task 1.
        r = self._submit(client, self.learner_a, self.task1_id)
        self.assertEqual(r.validation_status, "passed")

        # Learner A sees progress.
        perf_a = self._performance(client, self.learner_a)
        self.assertEqual(perf_a.completed_tasks, 1)
        self.assertEqual(perf_a.progress, 50)

        # Learner B has zero progress.
        perf_b = self._performance(client, self.learner_b)
        self.assertEqual(perf_b.completed_tasks, 0)
        self.assertEqual(perf_b.progress, 0)

    def test_learners_have_independent_progress(self):
        client = self._client()

        # Learner A completes both tasks.
        self._submit(client, self.learner_a, self.task1_id)
        self._submit(client, self.learner_a, self.task2_id)

        # Learner B completes only task 1.
        self._submit(client, self.learner_b, self.task1_id)

        perf_a = self._performance(client, self.learner_a)
        perf_b = self._performance(client, self.learner_b)

        self.assertEqual(perf_a.completed_tasks, 2)
        self.assertEqual(perf_a.progress, 100)
        self.assertTrue(perf_a.completed)

        self.assertEqual(perf_b.completed_tasks, 1)
        self.assertEqual(perf_b.progress, 50)
        self.assertFalse(perf_b.completed)


class TestProgressNeverExceedsBounds(unittest.TestCase):
    """Step 8: Progress bounds verification."""

    def setUp(self):
        self.learner_id = str(uuid4())
        self.project_id = uuid4()
        self.task_id = uuid4()
        self.simulation_id = uuid4()
        self.base_records = {
            "projects": [make_project(self.project_id)],
            "project_blueprints": [make_blueprint(self.project_id)],
            "tasks": [make_task(self.task_id, self.project_id)],
            "simulations": [
                make_simulation(self.simulation_id, self.learner_id, self.project_id, self.task_id)
            ],
            "submissions": [],
            "rubrics": [{"id": str(uuid4()), "task_id": str(self.task_id), "criteria": [], "status": "active", "version": 1}],
            "task_competencies": [],
            "task_concepts": [],
            "evaluations": [],
            "user_skills": [],
            "competencies": [],
            "concepts": [],
        }

    def _client(self, overrides=None):
        return FakeClient({**self.base_records, **(overrides or {})})

    def _submit(self, client, response="SELECT name, price FROM items;"):
        with patch("app.services.submission_service.get_supabase_client", return_value=client):
            return submit_task_work(
                learner_id=self.learner_id,
                project_id=self.project_id,
                task_id=self.task_id,
                payload=SubmissionCreate(response=response),
            )

    def _performance(self, client):
        with patch("app.services.performance_service.get_supabase_client", return_value=client):
            return get_project_performance(
                learner_id=self.learner_id, project_id=self.project_id
            )

    def test_many_submissions_do_not_exceed_100_percent(self):
        client = self._client()
        for _ in range(5):
            self._submit(client)

        performance = self._performance(client)
        self.assertLessEqual(performance.progress, 100)
        self.assertEqual(performance.completed_tasks, 1)
        self.assertTrue(performance.completed)

    def test_no_submissions_gives_zero_progress(self):
        client = self._client()
        performance = self._performance(client)
        self.assertEqual(performance.progress, 0)
        self.assertEqual(performance.completed_tasks, 0)
        self.assertFalse(performance.completed)


if __name__ == "__main__":
    unittest.main()
