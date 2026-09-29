import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from app.services.performance_service import get_learner_progress, get_learner_skills


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


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
        allowed = {str(v) for v in values}
        self._data = [row for row in self._data if str(row.get(field)) in allowed]
        return self

    def order(self, field, *, desc=False):
        self._data = sorted(self._data, key=lambda row: row.get(field) or "", reverse=desc)
        return self

    def limit(self, n):
        self._data = self._data[:n]
        return self

    def maybe_single(self):
        self._single = True
        self._data = self._data[:1]
        return self

    def update(self, payload):
        self.client.operations.append(("update", self.table_name, payload))
        self._pending_update = payload
        return self

    def execute(self):
        if self._pending_update is not None:
            for row in self.client.records.get(self.table_name, []):
                if row in self._data:
                    row.update(self._pending_update)
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


class TestLearnerDataContracts(unittest.TestCase):
    def setUp(self):
        self.learner_id = str(uuid4())
        self.other_learner_id = str(uuid4())
        self.project_a = uuid4()
        self.project_b = uuid4()
        self.task_a = uuid4()
        self.task_b = uuid4()
        self.competency_id = uuid4()
        self.concept_id = uuid4()

    def _fake_client(self):
        return FakeClient({
            "projects": [
                {"id": str(self.project_a), "name": "Customer Churn Analysis", "status": "active"},
                {"id": str(self.project_b), "name": "Website Development", "status": "active"},
            ],
            "tasks": [
                {"id": str(self.task_a), "project_id": str(self.project_a), "title": "Prepare data", "status": "active", "position": 0},
                {"id": str(self.task_b), "project_id": str(self.project_b), "title": "Ship frontend", "status": "active", "position": 0},
            ],
            "simulations": [
                {"id": str(uuid4()), "learner_id": self.learner_id, "project_id": str(self.project_a), "status": "active", "started_at": _ts(), "completed_at": None, "progress": 50},
                {"id": str(uuid4()), "learner_id": self.other_learner_id, "project_id": str(self.project_a), "status": "active", "started_at": _ts(), "completed_at": None, "progress": 90},
                {"id": str(uuid4()), "learner_id": self.learner_id, "project_id": str(self.project_b), "status": "completed", "started_at": _ts(), "completed_at": _ts(), "progress": 100},
            ],
            "submissions": [
                {"id": str(uuid4()), "learner_id": self.learner_id, "simulation_id": str(uuid4()), "task_id": str(self.task_a), "status": "submitted", "attempt_number": 1, "submitted_at": _ts()},
                {"id": str(uuid4()), "learner_id": self.other_learner_id, "simulation_id": str(uuid4()), "task_id": str(self.task_a), "status": "submitted", "attempt_number": 1, "submitted_at": _ts()},
                {"id": str(uuid4()), "learner_id": self.learner_id, "simulation_id": str(uuid4()), "task_id": str(self.task_b), "status": "submitted", "attempt_number": 2, "submitted_at": _ts()},
            ],
            "evaluations": [
                {"submission_id": list(filter(lambda s: s["learner_id"] == self.learner_id and s["task_id"] == str(self.task_a), self._fake_client_data()["submissions"]))[0]["id"], "status": "completed", "evaluation_type": "deterministic", "score": 100, "ai_result": {"status": "passed"}, "deterministic_result": {"status": "passed"}, "evaluated_at": _ts()},
            ],
            "task_competencies": [
                {"task_id": str(self.task_a), "competency_id": str(self.competency_id)},
                {"task_id": str(self.task_b), "competency_id": str(uuid4())},
            ],
            "task_concepts": [
                {"task_id": str(self.task_a), "concept_id": str(self.concept_id)},
            ],
            "user_skills": [
                {"id": str(uuid4()), "learner_id": self.learner_id, "competency_id": str(self.competency_id), "current_score": 85, "level": "proficient", "last_evaluated_at": _ts()},
                {"id": str(uuid4()), "learner_id": self.learner_id, "concept_id": str(self.concept_id), "current_score": 60, "level": "developing", "last_evaluated_at": _ts()},
                {"id": str(uuid4()), "learner_id": self.other_learner_id, "competency_id": str(self.competency_id), "current_score": 95, "level": "advanced", "last_evaluated_at": _ts()},
            ],
            "competencies": [
                {"id": str(self.competency_id), "name": "Data Quality"},
            ],
            "concepts": [
                {"id": str(self.concept_id), "name": "Feature Engineering"},
            ],
        })

    def _fake_client_data(self):
        client = FakeClient({
            "submissions": [
                {"id": str(uuid4()), "learner_id": self.learner_id, "simulation_id": str(uuid4()), "task_id": str(self.task_a), "status": "submitted", "attempt_number": 1, "submitted_at": _ts()},
                {"id": str(uuid4()), "learner_id": self.other_learner_id, "simulation_id": str(uuid4()), "task_id": str(self.task_a), "status": "submitted", "attempt_number": 1, "submitted_at": _ts()},
                {"id": str(uuid4()), "learner_id": self.learner_id, "simulation_id": str(uuid4()), "task_id": str(self.task_b), "status": "submitted", "attempt_number": 2, "submitted_at": _ts()},
            ]
        })
        return client.records

    def test_learner_progress_only_includes_own_projects(self):
        client = self._fake_client()
        from app.services.performance_service import get_project_performance

        with patch("app.services.performance_service.get_supabase_client", return_value=client), patch(
            "app.services.performance_service.get_project_performance",
            wraps=get_project_performance,
        ) as project_performance:
            response = get_learner_progress(learner_id=self.learner_id)

        self.assertEqual(len(response.projects), 2)
        self.assertEqual({str(project.project_id) for project in response.projects}, {str(self.project_a), str(self.project_b)})
        self.assertEqual(response.totals.projects_started, 2)
        self.assertEqual(response.totals.completed_projects, 1)
        self.assertEqual(response.totals.total_tasks, 2)
        self.assertEqual(response.totals.completed_tasks, 0)
        self.assertEqual(response.totals.average_progress, 0)
        self.assertEqual([project.status for project in response.projects], ["active", "completed"])
        self.assertEqual([project.progress for project in response.projects], [0, 0])
        self.assertEqual(set(response.model_dump().keys()), {"projects", "totals", "recent_activity"})
        self.assertEqual(
            set(response.projects[0].model_dump().keys()),
            {"project_id", "project_name", "status", "total_tasks", "completed_tasks", "progress", "completed", "started_at", "completed_at"},
        )
        self.assertEqual(
            set(response.totals.model_dump().keys()),
            {"projects_started", "completed_projects", "total_tasks", "completed_tasks", "average_progress"},
        )
        self.assertEqual(
            {call.kwargs["include_skill_details"] for call in project_performance.call_args_list},
            {False},
        )

    def test_learner_progress_ignores_another_learners_passing_submission(self):
        other_simulation_id = str(uuid4())
        task_id = str(uuid4())
        foreign_submission_id = str(uuid4())
        client = FakeClient({
            "projects": [{"id": str(self.project_a), "name": "Customer Churn Analysis", "status": "active"}],
            "tasks": [{"id": task_id, "project_id": str(self.project_a), "title": "Prepare data", "status": "active", "position": 0}],
            "simulations": [
                {"id": str(uuid4()), "learner_id": self.learner_id, "project_id": str(self.project_a), "status": "active", "started_at": _ts(), "completed_at": None, "progress": 0},
                {"id": other_simulation_id, "learner_id": self.other_learner_id, "project_id": str(self.project_a), "status": "active", "started_at": _ts(), "completed_at": None, "progress": 100},
            ],
            "submissions": [{"id": foreign_submission_id, "learner_id": self.other_learner_id, "simulation_id": other_simulation_id, "task_id": task_id, "status": "submitted", "attempt_number": 1, "submitted_at": _ts()}],
            "evaluations": [{"submission_id": foreign_submission_id, "status": "completed", "ai_result": {"status": "passed"}}],
        })

        with patch("app.services.performance_service.get_supabase_client", return_value=client):
            response = get_learner_progress(learner_id=self.learner_id)

        self.assertEqual(len(response.projects), 1)
        self.assertEqual(response.projects[0].total_tasks, 1)
        self.assertEqual(response.projects[0].completed_tasks, 0)
        self.assertEqual(response.projects[0].progress, 0)
        self.assertEqual(response.totals.completed_tasks, 0)

    def test_learner_skills_only_includes_own_records(self):
        client = self._fake_client()
        with patch("app.services.performance_service.get_supabase_client", return_value=client):
            response = get_learner_skills(learner_id=self.learner_id)

        self.assertEqual(len(response.skills), 2)
        names = {skill.name for skill in response.skills}
        self.assertIn("Data Quality", names)
        self.assertIn("Feature Engineering", names)
        self.assertNotIn("Other Learner", names)

    def test_empty_learner_has_empty_contract(self):
        client = FakeClient({
            "projects": [],
            "tasks": [],
            "simulations": [],
            "submissions": [],
            "evaluations": [],
            "task_competencies": [],
            "task_concepts": [],
            "user_skills": [],
            "competencies": [],
            "concepts": [],
        })
        with patch("app.services.performance_service.get_supabase_client", return_value=client):
            progress = get_learner_progress(learner_id=self.learner_id)
            skills = get_learner_skills(learner_id=self.learner_id)

        self.assertEqual(progress.projects, [])
        self.assertEqual(progress.totals.projects_started, 0)
        self.assertEqual(skills.skills, [])
        self.assertEqual(skills.totals.total_skills, 0)


if __name__ == "__main__":
    unittest.main()
