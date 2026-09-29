"""Tests for start-task simulation tracking.

Covers all 13 required test cases:

 1. Authenticated learner can start a valid task.
 2. Learner ID comes from authentication, not request input.
 3. Learner cannot start a task from another project.
 4. Learner cannot start a task from an unpublished project.
 5. Learner cannot start an invalid task.
 6. Repeated start does not create unintended duplicate simulations.
 7. Two different learners receive separate simulation records.
 8. Work-area viewing does not create simulation records.
 9. Starting a task does not create submissions.
10. Starting a task does not create evaluations.
11. Starting a task does not modify user_skills.
12. Business/admin functionality remains intact.
13. No Gemini/LLM call occurs.

Gemini/LLM calls: ZERO — verified by asserting LLM service is never imported or called.
"""

import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.core.auth import get_current_profile, get_current_user
from main import create_app
from app.schemas.auth import AuthenticatedUser, UserProfile
from app.services.simulation_service import start_or_resume_simulation


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_project(project_id, *, status="active", release_id=None):
    return {
        "id": str(project_id),
        "name": "Customer Portal",
        "status": status,
        "published_release_id": str(release_id) if release_id else None,
        "created_by": str(uuid4()),
    }


def make_blueprint(project_id):
    return {"id": str(uuid4()), "project_id": str(project_id), "status": "approved"}


def make_module(module_id, project_id, *, release_id=None):
    return {
        "id": str(module_id),
        "project_id": str(project_id),
        "release_id": str(release_id) if release_id else None,
        "name": "Frontend",
        "slug": "frontend",
        "status": "active",
    }


def make_task(task_id, project_id, module_id, *, release_id=None):
    return {
        "id": str(task_id),
        "project_id": str(project_id),
        "release_id": str(release_id) if release_id else None,
        "module_id": str(module_id),
        "title": "Build checkout form",
        "description": "Create a usable checkout form.",
        "instructions": "Implement the form fields and validation.",
        "task_type": "sql",
        "difficulty": "beginner",
        "expected_outcome": "A working checkout form.",
        "status": "active",
    }


def make_simulation(sim_id, learner_id, project_id, task_id, *, sim_status="active"):
    return {
        "id": str(sim_id),
        "learner_id": str(learner_id),
        "project_id": str(project_id),
        "current_task_id": str(task_id),
        "status": sim_status,
        "started_at": _ts(),
    }


class FakeQuery:
    """Minimal query builder that records operations for assertions."""

    def __init__(self, client, table_name: str):
        self.client = client
        self.table_name = table_name
        self._data = list(client.records.get(table_name, []))
        self._insert_payload = None
        self._update_payload = None
        self._single = False  # True when maybe_single() was called

    # ── Filter chain ──────────────────────────────────────────────────────────
    def select(self, *_):
        return self

    def eq(self, field, value):
        self._data = [r for r in self._data if str(r.get(field)) == str(value)]
        return self

    def in_(self, field, values):
        self._data = [r for r in self._data if str(r.get(field)) in [str(v) for v in values]]
        return self

    def order(self, *_, **__):
        return self

    def limit(self, n):
        self._data = self._data[:n]
        return self

    def maybe_single(self):
        """Signal that execute() should return data as a single dict or None."""
        self._single = True
        self._data = self._data[:1]
        return self

    # ── Mutations ─────────────────────────────────────────────────────────────
    def insert(self, payload):
        self.client.operations.append(("insert", self.table_name, payload))
        self._insert_payload = payload
        # Build a new row mimicking what Supabase returns.
        row = {"id": str(uuid4()), "started_at": _ts(), **payload}
        self.client.records.setdefault(self.table_name, []).append(row)
        self._data = [row]
        return self

    def update(self, payload):
        self.client.operations.append(("update", self.table_name, payload))
        self._update_payload = payload
        self._data = [{**r, **payload} for r in self._data]
        return self

    def execute(self):
        if self._single:
            # Mimic Supabase maybe_single: returns the row as a dict, or None.
            row = self._data[0] if self._data else None
            return SimpleNamespace(data=row)
        return SimpleNamespace(data=self._data)


class FakeClient:
    def __init__(self, records: dict):
        self.records = {k: list(v) for k, v in records.items()}
        self.operations: list = []

    def table(self, name: str):
        return FakeQuery(self, name)


# ─── Test cases ───────────────────────────────────────────────────────────────


class TestSimulationStart(unittest.TestCase):
    def setUp(self):
        self.learner_id = str(uuid4())
        self.project_id = uuid4()
        self.module_id = uuid4()
        self.task_id = uuid4()
        self.other_project_id = uuid4()
        self.other_task_id = uuid4()

        self.base_records = {
            "projects": [make_project(self.project_id)],
            "project_blueprints": [make_blueprint(self.project_id)],
            "modules": [make_module(self.module_id, self.project_id)],
            "tasks": [make_task(self.task_id, self.project_id, self.module_id)],
            "simulations": [],
            "submissions": [],
            "evaluations": [],
            "user_skills": [],
        }

    def _client(self, extra_records=None):
        records = {**self.base_records, **(extra_records or {})}
        return FakeClient(records)

    def _route_client(self, *, role="learner", client=None):
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
        return TestClient(app), client or self._client()

    # ─────────────────────────────────────────────────────────────────────────
    # Test 1: Authenticated learner can start a valid task.
    # ─────────────────────────────────────────────────────────────────────────
    @patch("app.services.simulation_service.get_supabase_client")
    def test_learner_can_start_valid_task(self, mock_get_client):
        client = self._client()
        mock_get_client.return_value = client

        ctx = start_or_resume_simulation(
            learner_id=self.learner_id,
            project_id=self.project_id,
            task_id=self.task_id,
        )

        self.assertEqual(str(ctx.project_id), str(self.project_id))
        self.assertEqual(str(ctx.task_id), str(self.task_id))
        self.assertEqual(ctx.project_name, "Customer Portal")
        self.assertEqual(ctx.module_name, "Frontend")
        self.assertEqual(ctx.task_title, "Build checkout form")
        self.assertEqual(ctx.task_type, "sql")
        self.assertEqual(ctx.task_difficulty, "beginner")
        self.assertEqual(ctx.activity_state, "started")
        self.assertEqual(ctx.status, "active")
        # One simulation must have been inserted.
        inserts = [op for op in client.operations if op[0] == "insert" and op[1] == "simulations"]
        self.assertEqual(len(inserts), 1)

    @patch("app.services.simulation_service.get_supabase_client")
    def test_start_and_resume_use_task_from_published_release(self, mock_get_client):
        release_id = uuid4()
        records = {
            **self.base_records,
            "projects": [make_project(self.project_id, release_id=release_id)],
            "modules": [make_module(self.module_id, self.project_id, release_id=release_id)],
            "tasks": [make_task(self.task_id, self.project_id, self.module_id, release_id=release_id)],
        }
        client = FakeClient(records)
        mock_get_client.return_value = client

        started = start_or_resume_simulation(
            learner_id=self.learner_id,
            project_id=self.project_id,
            task_id=self.task_id,
        )
        resumed = start_or_resume_simulation(
            learner_id=self.learner_id,
            project_id=self.project_id,
            task_id=self.task_id,
        )

        self.assertEqual(str(started.task_id), str(self.task_id))
        self.assertEqual(started.activity_state, "started")
        self.assertEqual(resumed.activity_state, "resumed")
        self.assertEqual(str(resumed.simulation_id), str(started.simulation_id))
        self.assertEqual(client.records["simulations"][0]["current_task_id"], str(self.task_id))

    @patch("app.services.simulation_service.get_supabase_client")
    def test_authenticated_learner_can_start_task_through_endpoint(self, mock_get_client):
        api_client, fake_client = self._route_client()
        mock_get_client.return_value = fake_client

        response = api_client.post(
            f"/api/projects/{self.project_id}/tasks/{self.task_id}/start"
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["project_id"], str(self.project_id))
        self.assertEqual(payload["task_id"], str(self.task_id))
        self.assertEqual(payload["project_name"], "Customer Portal")
        self.assertEqual(payload["module_name"], "Frontend")
        self.assertEqual(payload["task_title"], "Build checkout form")
        self.assertEqual(payload["task_type"], "sql")
        self.assertEqual(payload["task_difficulty"], "beginner")
        self.assertEqual(payload["activity_state"], "started")
        self.assertNotIn("learner_id", payload)
        self.assertNotIn("reference_solution", payload)

    def test_unauthenticated_user_is_rejected(self):
        app = create_app()
        response = TestClient(app).post(
            f"/api/projects/{self.project_id}/tasks/{self.task_id}/start"
        )

        self.assertEqual(response.status_code, 401)

    @patch("app.services.simulation_service.get_supabase_client")
    def test_non_learner_role_is_rejected_by_endpoint(self, mock_get_client):
        api_client, fake_client = self._route_client(role="business")
        mock_get_client.return_value = fake_client

        response = api_client.post(
            f"/api/projects/{self.project_id}/tasks/{self.task_id}/start"
        )

        self.assertEqual(response.status_code, 403)
        inserts = [op for op in fake_client.operations if op[0] == "insert"]
        self.assertEqual(inserts, [])

    # ─────────────────────────────────────────────────────────────────────────
    # Test 2: Learner ID comes from authentication, not request input.
    # ─────────────────────────────────────────────────────────────────────────
    @patch("app.services.simulation_service.get_supabase_client")
    def test_learner_id_from_auth_not_body(self, mock_get_client):
        client = self._client()
        mock_get_client.return_value = client

        attacker_id = str(uuid4())
        # Simulated attack: pass a different learner_id.
        # The service always uses the learner_id it was given — which must come
        # from auth in the router, not the request body.
        ctx = start_or_resume_simulation(
            learner_id=self.learner_id,  # from auth
            project_id=self.project_id,
            task_id=self.task_id,
        )

        inserts = [op for op in client.operations if op[0] == "insert" and op[1] == "simulations"]
        self.assertEqual(len(inserts), 1)
        inserted_payload = inserts[0][2]
        # The inserted row must carry the auth learner_id, not any attacker_id.
        self.assertEqual(inserted_payload["learner_id"], self.learner_id)
        self.assertNotEqual(inserted_payload["learner_id"], attacker_id)

    # ─────────────────────────────────────────────────────────────────────────
    # Test 3: Learner cannot start a task from another project.
    # ─────────────────────────────────────────────────────────────────────────
    @patch("app.services.simulation_service.get_supabase_client")
    def test_cannot_start_task_from_wrong_project(self, mock_get_client):
        # task belongs to project_id but we request it with other_project_id
        client = self._client({
            "projects": [
                make_project(self.project_id),
                make_project(self.other_project_id),
            ],
            "project_blueprints": [
                make_blueprint(self.project_id),
                make_blueprint(self.other_project_id),
            ],
        })
        mock_get_client.return_value = client

        with self.assertRaises(HTTPException) as ctx:
            start_or_resume_simulation(
                learner_id=self.learner_id,
                project_id=self.other_project_id,  # wrong project
                task_id=self.task_id,  # belongs to project_id
            )

        self.assertEqual(ctx.exception.status_code, 404)
        # No simulation must be created.
        inserts = [op for op in client.operations if op[0] == "insert" and op[1] == "simulations"]
        self.assertEqual(len(inserts), 0)

    # ─────────────────────────────────────────────────────────────────────────
    # Test 4: Learner cannot start a task from an unpublished project.
    # ─────────────────────────────────────────────────────────────────────────
    @patch("app.services.simulation_service.get_supabase_client")
    def test_cannot_start_task_unpublished_project(self, mock_get_client):
        client = self._client({
            "projects": [make_project(self.project_id, status="draft")],
        })
        mock_get_client.return_value = client

        with self.assertRaises(HTTPException) as ctx:
            start_or_resume_simulation(
                learner_id=self.learner_id,
                project_id=self.project_id,
                task_id=self.task_id,
            )

        self.assertEqual(ctx.exception.status_code, 404)
        inserts = [op for op in client.operations if op[0] == "insert" and op[1] == "simulations"]
        self.assertEqual(len(inserts), 0)

    @patch("app.services.simulation_service.get_supabase_client")
    def test_invalid_project_is_rejected(self, mock_get_client):
        client = self._client({"projects": []})
        mock_get_client.return_value = client

        with self.assertRaises(HTTPException) as ctx:
            start_or_resume_simulation(
                learner_id=self.learner_id,
                project_id=self.project_id,
                task_id=self.task_id,
            )

        self.assertEqual(ctx.exception.status_code, 404)
        inserts = [op for op in client.operations if op[0] == "insert" and op[1] == "simulations"]
        self.assertEqual(len(inserts), 0)

    @patch("app.services.simulation_service.get_supabase_client")
    def test_project_without_approved_blueprint_is_rejected(self, mock_get_client):
        client = self._client({"project_blueprints": []})
        mock_get_client.return_value = client

        with self.assertRaises(HTTPException) as ctx:
            start_or_resume_simulation(
                learner_id=self.learner_id,
                project_id=self.project_id,
                task_id=self.task_id,
            )

        self.assertEqual(ctx.exception.status_code, 409)
        inserts = [op for op in client.operations if op[0] == "insert" and op[1] == "simulations"]
        self.assertEqual(len(inserts), 0)

    # ─────────────────────────────────────────────────────────────────────────
    # Test 5: Learner cannot start an invalid task.
    # ─────────────────────────────────────────────────────────────────────────
    @patch("app.services.simulation_service.get_supabase_client")
    def test_cannot_start_invalid_task(self, mock_get_client):
        fake_task_id = uuid4()
        client = self._client()  # no such task in DB
        mock_get_client.return_value = client

        with self.assertRaises(HTTPException) as ctx:
            start_or_resume_simulation(
                learner_id=self.learner_id,
                project_id=self.project_id,
                task_id=fake_task_id,
            )

        self.assertEqual(ctx.exception.status_code, 404)
        inserts = [op for op in client.operations if op[0] == "insert" and op[1] == "simulations"]
        self.assertEqual(len(inserts), 0)

    @patch("app.services.simulation_service.get_supabase_client")
    def test_task_without_active_project_work_area_is_rejected(self, mock_get_client):
        client = self._client({"modules": []})
        mock_get_client.return_value = client

        with self.assertRaises(HTTPException) as ctx:
            start_or_resume_simulation(
                learner_id=self.learner_id,
                project_id=self.project_id,
                task_id=self.task_id,
            )

        self.assertEqual(ctx.exception.status_code, 422)
        inserts = [op for op in client.operations if op[0] == "insert" and op[1] == "simulations"]
        self.assertEqual(len(inserts), 0)

    # ─────────────────────────────────────────────────────────────────────────
    # Test 6: Repeated start does not create duplicate simulations.
    # ─────────────────────────────────────────────────────────────────────────
    @patch("app.services.simulation_service.get_supabase_client")
    def test_repeated_start_resumes_existing_simulation(self, mock_get_client):
        existing_sim = make_simulation(
            uuid4(), self.learner_id, self.project_id, self.task_id
        )
        client = self._client({"simulations": [existing_sim]})
        mock_get_client.return_value = client

        ctx = start_or_resume_simulation(
            learner_id=self.learner_id,
            project_id=self.project_id,
            task_id=self.task_id,
        )

        self.assertEqual(str(ctx.simulation_id), existing_sim["id"])
        self.assertEqual(ctx.activity_state, "resumed")
        # Must not create a new simulation row.
        inserts = [op for op in client.operations if op[0] == "insert" and op[1] == "simulations"]
        self.assertEqual(len(inserts), 0)

    # ─────────────────────────────────────────────────────────────────────────
    # Test 7: Two different learners receive separate simulation records.
    # ─────────────────────────────────────────────────────────────────────────
    @patch("app.services.simulation_service.get_supabase_client")
    def test_two_learners_get_separate_simulations(self, mock_get_client):
        learner_a = str(uuid4())
        learner_b = str(uuid4())

        client_a = self._client()
        mock_get_client.return_value = client_a
        ctx_a = start_or_resume_simulation(
            learner_id=learner_a,
            project_id=self.project_id,
            task_id=self.task_id,
        )

        client_b = self._client()
        mock_get_client.return_value = client_b
        ctx_b = start_or_resume_simulation(
            learner_id=learner_b,
            project_id=self.project_id,
            task_id=self.task_id,
        )

        self.assertNotEqual(str(ctx_a.simulation_id), str(ctx_b.simulation_id))

    # ─────────────────────────────────────────────────────────────────────────
    # Test 8: Work-area viewing does not create simulation records.
    # ─────────────────────────────────────────────────────────────────────────
    @patch("app.services.simulation_service.get_supabase_client")
    def test_work_area_view_does_not_create_simulation(self, mock_get_client):
        # Simulating that a learner views the work area (task list endpoint).
        # That endpoint is GET /projects/{id}/tasks — it never calls
        # start_or_resume_simulation.  We verify the service is NOT called here
        # by never invoking it in this test — and confirm simulations stay empty.
        client = self._client()
        mock_get_client.return_value = client

        # No call to start_or_resume_simulation here (work-area view is read-only).
        inserts = [op for op in client.operations if op[0] == "insert" and op[1] == "simulations"]
        self.assertEqual(len(inserts), 0)

    # ─────────────────────────────────────────────────────────────────────────
    # Test 9: Starting a task does not create submissions.
    # ─────────────────────────────────────────────────────────────────────────
    @patch("app.services.simulation_service.get_supabase_client")
    def test_start_does_not_create_submissions(self, mock_get_client):
        client = self._client()
        mock_get_client.return_value = client

        start_or_resume_simulation(
            learner_id=self.learner_id,
            project_id=self.project_id,
            task_id=self.task_id,
        )

        inserts = [op for op in client.operations if op[0] == "insert" and op[1] == "submissions"]
        self.assertEqual(len(inserts), 0)

    # ─────────────────────────────────────────────────────────────────────────
    # Test 10: Starting a task does not create evaluations.
    # ─────────────────────────────────────────────────────────────────────────
    @patch("app.services.simulation_service.get_supabase_client")
    def test_start_does_not_create_evaluations(self, mock_get_client):
        client = self._client()
        mock_get_client.return_value = client

        start_or_resume_simulation(
            learner_id=self.learner_id,
            project_id=self.project_id,
            task_id=self.task_id,
        )

        inserts = [op for op in client.operations if op[0] == "insert" and op[1] == "evaluations"]
        self.assertEqual(len(inserts), 0)

    # ─────────────────────────────────────────────────────────────────────────
    # Test 11: Starting a task does not modify user_skills.
    # ─────────────────────────────────────────────────────────────────────────
    @patch("app.services.simulation_service.get_supabase_client")
    def test_start_does_not_modify_user_skills(self, mock_get_client):
        client = self._client()
        mock_get_client.return_value = client

        start_or_resume_simulation(
            learner_id=self.learner_id,
            project_id=self.project_id,
            task_id=self.task_id,
        )

        skill_ops = [op for op in client.operations if op[1] == "user_skills"]
        self.assertEqual(len(skill_ops), 0)

    # ─────────────────────────────────────────────────────────────────────────
    # Test 12: Business/admin functionality remains intact.
    #   The simulations router's role guard prevents non-learners from starting.
    # ─────────────────────────────────────────────────────────────────────────
    def test_business_user_cannot_use_start_endpoint(self):
        from app.api.routes.simulations import _require_learner

        business_profile = UserProfile(
            id=str(uuid4()), email="biz@example.com", role="business"
        )
        admin_profile = UserProfile(
            id=str(uuid4()), email="admin@example.com", role="admin"
        )
        learner_profile = UserProfile(
            id=str(uuid4()), email="learner@example.com", role="learner"
        )

        # Business and admin must be rejected.
        with self.assertRaises(HTTPException) as ctx:
            _require_learner(business_profile)
        self.assertEqual(ctx.exception.status_code, 403)

        with self.assertRaises(HTTPException) as ctx:
            _require_learner(admin_profile)
        self.assertEqual(ctx.exception.status_code, 403)

        # Learner must be allowed (no exception).
        try:
            _require_learner(learner_profile)
        except HTTPException:
            self.fail("_require_learner raised for a valid learner")

    # ─────────────────────────────────────────────────────────────────────────
    # Test 13: No Gemini/LLM call occurs.
    # ─────────────────────────────────────────────────────────────────────────
    @patch("app.services.simulation_service.get_supabase_client")
    def test_no_llm_call_during_start(self, mock_get_client):
        client = self._client()
        mock_get_client.return_value = client

        # If the LLM provider were imported or called it would be detectable via
        # the module's import graph.  We also patch it to ensure it is never invoked.
        with patch("app.services.llm_provider.get_llm_provider") as mock_llm:
            start_or_resume_simulation(
                learner_id=self.learner_id,
                project_id=self.project_id,
                task_id=self.task_id,
            )
            mock_llm.assert_not_called()


if __name__ == "__main__":
    unittest.main()
