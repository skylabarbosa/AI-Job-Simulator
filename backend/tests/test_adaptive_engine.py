import unittest
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.auth import get_current_profile, get_current_user
from app.schemas.adaptive import AdaptivePresentationDecision
from app.schemas.auth import AuthenticatedUser, UserProfile
from app.services.adaptive_engine import EvidenceSnapshot, TaskMetadata, decide_presentation
from main import create_app


class AdaptiveEngineTests(unittest.TestCase):
    def setUp(self):
        self.project_id = uuid4()
        self.task_id = uuid4()
        self.concept_id = uuid4()
        self.competency_id = uuid4()
        self.task = TaskMetadata(
            project_id=self.project_id,
            task_id=self.task_id,
            task_type="SQL",
            difficulty="intermediate",
            concept_ids=(self.concept_id,),
            competency_ids=(self.competency_id,),
        )

    def test_strong_evidence_is_independent_and_more_challenging(self):
        evidence = EvidenceSnapshot(
            skill_scores={self.concept_id: 90, self.competency_id: 80},
            demonstrated_ids={self.concept_id, self.competency_id},
        )
        decision = decide_presentation(task=self.task, evidence=evidence)
        self.assertEqual(decision.support_level, "independent")
        self.assertEqual(decision.presentation_difficulty, "stretch")
        self.assertFalse(decision.hints_available)
        self.assertFalse(decision.examples_available)

    def test_mixed_evidence_uses_standard_presentation(self):
        decision = decide_presentation(
            task=self.task,
            evidence=EvidenceSnapshot(skill_scores={self.concept_id: 60}),
        )
        self.assertEqual(decision.support_level, "moderate")
        self.assertEqual(decision.presentation_difficulty, "standard")
        self.assertTrue(decision.hints_available)
        self.assertEqual(decision.guided_step_level, "moderate")

    def test_one_failed_attempt_does_not_overreact(self):
        decision = decide_presentation(
            task=self.task,
            evidence=EvidenceSnapshot(failure_counts={self.concept_id: 1}),
        )
        self.assertEqual(decision.support_level, "moderate")
        self.assertEqual(decision.evidence_used.repeated_failure_count, 0)

    def test_repeated_failure_on_same_concept_is_guided(self):
        decision = decide_presentation(
            task=self.task,
            evidence=EvidenceSnapshot(failure_counts={self.concept_id: 2}),
        )
        self.assertEqual(decision.support_level, "guided")
        self.assertEqual(decision.presentation_difficulty, "foundational")
        self.assertTrue(decision.hints_available)
        self.assertTrue(decision.examples_available)
        self.assertEqual(decision.guided_step_level, "explicit")

    def test_previous_mastery_is_preserved_after_later_failure(self):
        evidence = EvidenceSnapshot(
            skill_scores={self.concept_id: 10},
            demonstrated_ids={self.concept_id},
            failure_counts={self.concept_id: 1},
        )
        decision = decide_presentation(task=self.task, evidence=evidence)
        self.assertTrue(decision.evidence_used.historical_mastery_preserved)
        self.assertEqual(decision.evidence_used.demonstrated_evidence_count, 1)
        self.assertEqual(decision.support_level, "moderate")

    def test_repeated_failure_still_increases_support_after_mastery(self):
        evidence = EvidenceSnapshot(
            skill_scores={self.concept_id: 10},
            demonstrated_ids={self.concept_id},
            failure_counts={self.concept_id: 2},
        )
        decision = decide_presentation(task=self.task, evidence=evidence)
        self.assertTrue(decision.evidence_used.historical_mastery_preserved)
        self.assertEqual(decision.support_level, "guided")

    def test_target_required_task_is_never_replaced(self):
        decision = decide_presentation(task=self.task, evidence=EvidenceSnapshot())
        self.assertEqual(decision.project_id, self.project_id)
        self.assertEqual(decision.target_task_id, self.task_id)

    def test_different_learners_do_not_share_snapshots(self):
        learner_a = EvidenceSnapshot(skill_scores={self.concept_id: 90, self.competency_id: 90})
        learner_b = EvidenceSnapshot()
        self.assertEqual(decide_presentation(task=self.task, evidence=learner_a).support_level, "independent")
        self.assertEqual(decide_presentation(task=self.task, evidence=learner_b).support_level, "moderate")

    def test_different_projects_do_not_share_task_metadata(self):
        other_task = TaskMetadata(
            project_id=uuid4(), task_id=uuid4(), task_type="Data Cleaning", difficulty="beginner"
        )
        decision = decide_presentation(task=other_task, evidence=EvidenceSnapshot())
        self.assertEqual(decision.project_id, other_task.project_id)
        self.assertEqual(decision.target_task_id, other_task.task_id)

    def test_task_types_use_the_same_generic_rules(self):
        for task_type in ("SQL", "Data Cleaning", "Data Analysis", "future-type"):
            task = TaskMetadata(
                project_id=self.project_id,
                task_id=uuid4(),
                task_type=task_type,
                difficulty="beginner",
                concept_ids=(self.concept_id,),
            )
            decision = decide_presentation(
                task=task,
                evidence=EvidenceSnapshot(skill_scores={self.concept_id: 90}),
            )
            self.assertEqual(decision.support_level, "independent")
            self.assertEqual(decision.task_type, task_type)

    def test_decision_has_no_completion_or_access_controls(self):
        decision = decide_presentation(task=self.task, evidence=EvidenceSnapshot())
        self.assertIsInstance(decision, AdaptivePresentationDecision)
        self.assertFalse(hasattr(decision, "completed"))
        self.assertFalse(hasattr(decision, "locked"))


class _Query:
    def __init__(self, client, table):
        self.client = client
        self.data = list(client.records.get(table, []))
        self.single = False

    def select(self, *_):
        return self

    def eq(self, field, value):
        self.data = [row for row in self.data if str(row.get(field)) == str(value)]
        return self

    def in_(self, field, values):
        expected = {str(value) for value in values}
        self.data = [row for row in self.data if str(row.get(field)) in expected]
        return self

    def limit(self, count):
        self.data = self.data[:count]
        return self

    def maybe_single(self):
        self.single = True
        self.data = self.data[:1]
        return self

    def execute(self):
        return SimpleNamespace(data=self.data[0] if self.single and self.data else (None if self.single else self.data))


class _Client:
    def __init__(self, records):
        self.records = records
        self.operations = []

    def table(self, table):
        self.operations.append(("select", table))
        return _Query(self, table)


class AdaptiveApiTests(unittest.TestCase):
    def test_authenticated_api_is_scoped_and_does_not_mutate_progress(self):
        learner_id = str(uuid4())
        project_id = uuid4()
        task_id = uuid4()
        concept_id = uuid4()
        records = {
            "projects": [{"id": str(project_id), "name": "Project", "status": "active"}],
            "project_blueprints": [{"id": str(uuid4()), "project_id": str(project_id), "status": "approved"}],
            "tasks": [{"id": str(task_id), "project_id": str(project_id), "task_type": "Data Analysis", "difficulty": "intermediate", "status": "active"}],
            "task_competencies": [],
            "task_concepts": [{"task_id": str(task_id), "concept_id": str(concept_id)}],
            "user_skills": [{"learner_id": learner_id, "concept_id": str(concept_id), "current_score": 90}],
            "simulations": [{"id": str(uuid4()), "learner_id": learner_id, "project_id": str(project_id)}],
            "submissions": [],
            "evaluations": [],
        }
        client = _Client(records)
        app = create_app()
        app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(id=learner_id, email="learner@example.com")
        app.dependency_overrides[get_current_profile] = lambda: UserProfile(id=learner_id, email="learner@example.com", role="learner")
        with patch("app.services.adaptive_service.get_supabase_client", return_value=client):
            response = TestClient(app).get(f"/api/projects/{project_id}/tasks/{task_id}/adaptive-decision")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["target_task_id"], str(task_id))
        self.assertEqual(payload["support_level"], "independent")
        self.assertEqual([op for op in client.operations if op[0] != "select"], [])


if __name__ == "__main__":
    unittest.main()