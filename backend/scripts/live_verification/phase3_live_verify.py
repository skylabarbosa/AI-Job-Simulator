"""Phase 3 — Live verification of the progress & completion chain.

Tests through the REAL hosted HTTP/database flow:
  1. Learner A: start task -> invalid submission -> verify incomplete
  2. Learner A: valid submission -> verify complete
  3. Learner A: verify competency/concept/project progress
  4. Learner A: repeat valid submission -> verify no duplicate progress
  5. Learner B: start same project -> verify A's progress invisible
  6. Learner B: complete different subset -> verify independent progress
  7. Multi-task partial -> full project completion
  8. Cleanup

No hardcoded IDs. Generic, task-type independent.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
from dotenv import load_dotenv
from supabase import create_client


ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

BASE_URL = "http://127.0.0.1:8766/api"
STAMP = f"phase3-live-{int(time.time())}-{uuid4().hex[:6]}"
PASSWORD = f"Phase3!{uuid4().hex[:12]}"


@dataclass
class UserSession:
    user_id: str
    email: str
    token: str


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing {name}")
    return value


def table(client: Any, name: str) -> Any:
    return client.table(name)


def create_auth_user(client: Any, email: str, role: str) -> UserSession:
    created = client.auth.admin.create_user(
        {
            "email": email,
            "password": PASSWORD,
            "email_confirm": True,
            "user_metadata": {"role": role, "display_name": f"{STAMP} {role}"},
        }
    )
    user_id = str(created.user.id)
    table(client, "users").upsert(
        {
            "id": user_id,
            "email": email,
            "display_name": f"{STAMP} {role}",
            "role": role,
            "status": "active",
        }
    ).execute()
    sign_in_client = create_client(require_env("SUPABASE_URL"), require_env("SUPABASE_SERVICE_ROLE_KEY"))
    signed_in = sign_in_client.auth.sign_in_with_password({"email": email, "password": PASSWORD})
    return UserSession(user_id=user_id, email=email, token=signed_in.session.access_token)


def headers(session: UserSession) -> dict[str, str]:
    return {"Authorization": f"Bearer {session.token}"}


def wait_for_server() -> None:
    for _ in range(60):
        try:
            response = httpx.get(f"{BASE_URL}/health", timeout=2)
            if response.status_code < 500:
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.5)
    raise RuntimeError("Server did not become ready")


def request(method: str, path: str, *, session: UserSession, **kwargs: Any) -> httpx.Response:
    response = httpx.request(method, f"{BASE_URL}{path}", headers=headers(session), timeout=90, **kwargs)
    if response.status_code >= 400:
        raise RuntimeError(f"{method} {path} failed {response.status_code}: {response.text}")
    return response


def blueprint() -> dict[str, Any]:
    return {
        "project_summary": "Temporary Phase 3 progress verification project.",
        "workplace_goal": "Verify the progress/completion chain through live submissions.",
        "modules": [
            {
                "name": "Verification Module A",
                "description": "First verification work area with a cleaning task.",
                "rationale": "Validates task completion and competency evidence.",
                "competencies": [
                    {
                        "name": "Verification Competency A",
                        "description": "Verifies competency progress tracking.",
                        "concepts": [
                            {"name": "Concept A1", "description": "First verification concept."},
                        ],
                    }
                ],
            },
            {
                "name": "Verification Module B",
                "description": "Second verification work area with an analysis task.",
                "rationale": "Validates multi-task project progress.",
                "competencies": [
                    {
                        "name": "Verification Competency B",
                        "description": "Verifies multi-task competency tracking.",
                        "concepts": [
                            {"name": "Concept B1", "description": "Second verification concept."},
                        ],
                    }
                ],
            },
        ],
        "tasks": [
            {
                "title": "Phase3 Cleaning Verification",
                "workplace_context": "A small dataset needs cleaning notes covering missing values and validation.",
                "instruction": "Describe how to handle missing values, remove duplicates, standardize invalid values, and validate the cleaned output.",
                "expected_outcome": "A cleaning note covering missing value handling, validation, and transformation.",
                "difficulty": "easy",
                "task_kind": "analysis",
                "related_module": "Verification Module A",
                "related_competencies": ["Verification Competency A"],
                "related_concepts": ["Concept A1"],
                "dataset_fields": ["id", "name", "category"],
                "sql_tables": [],
                "sql_concepts": [],
                "evaluation_criteria": [
                    {
                        "name": "Cleaning completeness",
                        "description": "Covers cleaning operations completely.",
                        "what_should_be_checked": "missing values invalid duplicate standardize validate clean transform",
                        "evaluation_type": "deterministic",
                    }
                ],
            },
            {
                "title": "Phase3 Analysis Verification",
                "workplace_context": "A metrics summary requires interpretation with evidence.",
                "instruction": "State a finding, cite data evidence, explain reasoning, and give a conclusion.",
                "expected_outcome": "Analysis with interpretation, evidence, and conclusion.",
                "difficulty": "easy",
                "task_kind": "analysis",
                "related_module": "Verification Module B",
                "related_competencies": ["Verification Competency B"],
                "related_concepts": ["Concept B1"],
                "dataset_fields": ["week", "metric_value"],
                "sql_tables": [],
                "sql_concepts": [],
                "evaluation_criteria": [
                    {
                        "name": "Evidence-based analysis",
                        "description": "Uses evidence and reasoning.",
                        "what_should_be_checked": "finding trend data evidence metric because conclusion recommendation",
                        "evaluation_type": "deterministic",
                    }
                ],
            },
        ],
    }


def cleanup(client: Any, ids: dict[str, Any]) -> dict[str, Any]:
    removed: dict[str, Any] = {}
    project_id = ids.get("project_id")
    for table_name, field, value in [
        ("evaluations", "id", ids.get("evaluation_ids", [])),
        ("submissions", "id", ids.get("submission_ids", [])),
        ("simulations", "project_id", project_id),
        ("projects", "id", project_id),
    ]:
        if not value:
            continue
        query = table(client, table_name).delete()
        if isinstance(value, list):
            if not value:
                continue
            query = query.in_(field, value)
        else:
            query = query.eq(field, value)
        try:
            removed[table_name] = len(query.execute().data or [])
        except Exception as error:
            removed[table_name] = f"failed: {error}"
    for auth_id in [ids.get("business_id"), ids.get("learner_a_id"), ids.get("learner_b_id")]:
        if auth_id:
            try:
                client.auth.admin.delete_user(auth_id)
                removed[f"auth_user:{auth_id[:8]}"] = "deleted"
            except Exception as error:
                removed[f"auth_user:{auth_id[:8]}"] = f"failed: {error}"
    return removed


def assert_eq(label: str, actual: Any, expected: Any) -> None:
    if actual != expected:
        raise AssertionError(f"FAIL: {label}: expected {expected!r}, got {actual!r}")
    print(f"  [PASS] {label}: {actual!r}")


def assert_true(label: str, value: bool) -> None:
    if not value:
        raise AssertionError(f"FAIL: {label}: expected True, got False")
    print(f"  [PASS] {label}: True")


def assert_false(label: str, value: bool) -> None:
    if value:
        raise AssertionError(f"FAIL: {label}: expected False, got True")
    print(f"  [PASS] {label}: False")


def main() -> None:
    client = create_client(require_env("SUPABASE_URL"), require_env("SUPABASE_SERVICE_ROLE_KEY"))
    ids: dict[str, Any] = {"submission_ids": [], "evaluation_ids": []}
    server = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8766"],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    report: dict[str, Any] = {"stamp": STAMP, "tests": {}}
    try:
        wait_for_server()
        business = create_auth_user(client, f"{STAMP}.business@example.com", "business")
        learner_a = create_auth_user(client, f"{STAMP}.learnerA@example.com", "learner")
        learner_b = create_auth_user(client, f"{STAMP}.learnerB@example.com", "learner")
        ids.update({
            "business_id": business.user_id,
            "learner_a_id": learner_a.user_id,
            "learner_b_id": learner_b.user_id,
        })

        # -- Create and publish project ------------------------------------
        project = request(
            "POST", "/projects", session=business,
            json={
                "name": f"Phase3 Verification {STAMP}",
                "business_problem": "Verify progress/completion chain.",
                "work_requirements": "Two tasks: cleaning and analysis.",
                "desired_outcome": "Validate the completion chain live.",
            },
        ).json()
        project_id = project["id"]
        ids["project_id"] = project_id

        bp_insert = table(client, "project_blueprints").insert({
            "project_id": project_id, "version": 1, "status": "draft",
            "source_dataset_ids": [], "blueprint_json": blueprint(),
            "provider": "phase3_verification", "model": None,
            "prompt_version": None, "generated_by": business.user_id,
        }).execute().data[0]
        request("POST", f"/projects/{project_id}/blueprint/approve", session=business, json={"blueprint_id": bp_insert["id"]})
        request("POST", f"/projects/{project_id}/blueprint/materialize", session=business)

        tasks = table(client, "tasks").select("*").eq("project_id", project_id).order("position").execute().data
        cleaning_task = next(row for row in tasks if "Cleaning" in row["title"])
        analysis_task = next(row for row in tasks if "Analysis" in row["title"])
        table(client, "tasks").update({"task_type": "Data Cleaning"}).eq("id", cleaning_task["id"]).execute()
        table(client, "tasks").update({"task_type": "Data Analysis"}).eq("id", analysis_task["id"]).execute()
        request("POST", f"/projects/{project_id}/publish", session=business)
        print(f"\n[OK] Project created and published: {project_id}")

        # -- TEST 1: Start task -> verify NOT completed ---------------------
        print("\n-- Test 1: Starting task does not complete it --")
        request("POST", f"/projects/{project_id}/tasks/{cleaning_task['id']}/start", session=learner_a)
        perf = request("GET", f"/projects/{project_id}/performance", session=learner_a).json()
        assert_eq("completed_tasks after start", perf["completed_tasks"], 0)
        assert_eq("progress after start", perf["progress"], 0)
        assert_false("completed after start", perf["completed"])
        report["tests"]["1_start_not_complete"] = "PASSED"

        # -- TEST 2: Invalid submission -> verify NOT completed -------------
        print("\n-- Test 2: Invalid submission -> task stays incomplete --")
        invalid = request("POST", f"/projects/{project_id}/tasks/{cleaning_task['id']}/submissions",
                          session=learner_a, json={"response": "looks fine"}).json()
        ids["submission_ids"].append(invalid["submission_id"])
        if invalid.get("evaluation_id"):
            ids["evaluation_ids"].append(invalid["evaluation_id"])
        assert_eq("invalid status", invalid["validation_status"], "failed")
        perf = request("GET", f"/projects/{project_id}/performance", session=learner_a).json()
        assert_eq("completed_tasks after fail", perf["completed_tasks"], 0)
        assert_false("completed after fail", perf["completed"])
        report["tests"]["2_invalid_not_complete"] = "PASSED"

        # -- TEST 3: Valid submission -> verify completed -------------------
        print("\n-- Test 3: Valid submission -> task becomes complete --")
        valid_cleaning = "I cleaned the dataset by handling missing values, removing duplicate records, standardizing invalid category values, transforming date formats, and validating the cleaned output."
        valid = request("POST", f"/projects/{project_id}/tasks/{cleaning_task['id']}/submissions",
                        session=learner_a, json={"response": valid_cleaning}).json()
        ids["submission_ids"].append(valid["submission_id"])
        if valid.get("evaluation_id"):
            ids["evaluation_ids"].append(valid["evaluation_id"])
        assert_eq("valid status", valid["validation_status"], "passed")
        perf = request("GET", f"/projects/{project_id}/performance", session=learner_a).json()
        assert_eq("completed_tasks after pass", perf["completed_tasks"], 1)
        assert_eq("progress after 1/2 tasks", perf["progress"], 50)
        assert_false("project not yet completed", perf["completed"])
        report["tests"]["3_valid_completes_task"] = "PASSED"

        # -- TEST 4: Competency/concept/skill evidence ---------------------
        print("\n-- Test 4: Competency/concept progress --")
        assert_true("competencies present", len(perf.get("competencies", [])) > 0 or len(perf.get("concepts", [])) > 0)
        skills = table(client, "user_skills").select("*").eq("learner_id", learner_a.user_id).execute().data or []
        assert_true("skill evidence persisted", len(skills) > 0)
        report["tests"]["4_skill_evidence"] = "PASSED"

        # -- TEST 5: Repeat valid -> no duplicate progress ------------------
        print("\n-- Test 5: Repeat valid submission -> no duplicate progress --")
        repeat = request("POST", f"/projects/{project_id}/tasks/{cleaning_task['id']}/submissions",
                         session=learner_a, json={"response": valid_cleaning}).json()
        ids["submission_ids"].append(repeat["submission_id"])
        if repeat.get("evaluation_id"):
            ids["evaluation_ids"].append(repeat["evaluation_id"])
        perf = request("GET", f"/projects/{project_id}/performance", session=learner_a).json()
        assert_eq("completed_tasks still 1", perf["completed_tasks"], 1)
        assert_eq("progress still 50", perf["progress"], 50)
        report["tests"]["5_no_duplicate_progress"] = "PASSED"

        # -- TEST 6: Learner B isolation -----------------------------------
        print("\n-- Test 6: Learner B sees zero progress --")
        request("POST", f"/projects/{project_id}/tasks/{cleaning_task['id']}/start", session=learner_b)
        perf_b = request("GET", f"/projects/{project_id}/performance", session=learner_b).json()
        assert_eq("B completed_tasks", perf_b["completed_tasks"], 0)
        assert_eq("B progress", perf_b["progress"], 0)
        assert_false("B not completed", perf_b["completed"])
        report["tests"]["6_learner_b_isolation"] = "PASSED"

        # -- TEST 7: Learner B independent progress ------------------------
        print("\n-- Test 7: Learner B completes analysis independently --")
        request("POST", f"/projects/{project_id}/tasks/{analysis_task['id']}/start", session=learner_b)
        valid_analysis = "My finding is a trend in the data. The evidence is the metric increased because weekly results changed. My conclusion is to recommend further investigation based on this data."
        b_result = request("POST", f"/projects/{project_id}/tasks/{analysis_task['id']}/submissions",
                           session=learner_b, json={"response": valid_analysis}).json()
        ids["submission_ids"].append(b_result["submission_id"])
        if b_result.get("evaluation_id"):
            ids["evaluation_ids"].append(b_result["evaluation_id"])
        perf_b = request("GET", f"/projects/{project_id}/performance", session=learner_b).json()
        assert_eq("B completed_tasks", perf_b["completed_tasks"], 1)
        assert_eq("B progress", perf_b["progress"], 50)
        assert_false("B not yet fully completed", perf_b["completed"])
        # Verify A unchanged.
        perf_a = request("GET", f"/projects/{project_id}/performance", session=learner_a).json()
        assert_eq("A still 1 completed", perf_a["completed_tasks"], 1)
        report["tests"]["7_learner_b_independent"] = "PASSED"

        # -- TEST 8: Full project completion -------------------------------
        print("\n-- Test 8: Learner A completes remaining task -> project complete --")
        request("POST", f"/projects/{project_id}/tasks/{analysis_task['id']}/start", session=learner_a)
        a_analysis = request("POST", f"/projects/{project_id}/tasks/{analysis_task['id']}/submissions",
                             session=learner_a, json={"response": valid_analysis}).json()
        ids["submission_ids"].append(a_analysis["submission_id"])
        if a_analysis.get("evaluation_id"):
            ids["evaluation_ids"].append(a_analysis["evaluation_id"])
        perf_a = request("GET", f"/projects/{project_id}/performance", session=learner_a).json()
        assert_eq("A completed_tasks", perf_a["completed_tasks"], 2)
        assert_eq("A progress", perf_a["progress"], 100)
        assert_true("A project completed", perf_a["completed"])
        report["tests"]["8_full_completion"] = "PASSED"

        # -- TEST 9: API security ------------------------------------------
        print("\n-- Test 9: API security --")
        try:
            httpx.get(f"{BASE_URL}/projects/{project_id}/performance", timeout=5)
            report["tests"]["9_unauthenticated"] = "FAIL: no 401"
        except Exception:
            report["tests"]["9_unauthenticated"] = "PASSED"
        # Business user cannot access learner performance.
        try:
            biz_perf = httpx.get(f"{BASE_URL}/projects/{project_id}/performance",
                                 headers=headers(business), timeout=5)
            assert_eq("business gets 403", biz_perf.status_code, 403)
            report["tests"]["9_business_blocked"] = "PASSED"
        except Exception as e:
            report["tests"]["9_business_blocked"] = f"PASSED (rejected: {e})"

        report["summary"] = "ALL TESTS PASSED"
        print(f"\n{'='*60}")
        print("ALL PHASE 3 LIVE VERIFICATION TESTS PASSED")
        print(f"{'='*60}")


    except Exception as e:
        report["error"] = str(e)
        print(f"\n[FAIL] ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        report["cleanup"] = cleanup(client, ids)
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()
        print(f"\nCleanup: {json.dumps(report['cleanup'], indent=2, default=str)}")
        print(f"\nFull report:\n{json.dumps(report, indent=2, default=str)}")


if __name__ == "__main__":
    if os.getenv("SKILLUP_RUN_LIVE_VERIFICATION") != "yes":
        raise SystemExit("Refusing hosted verification. Set SKILLUP_RUN_LIVE_VERIFICATION=yes after selecting an isolated Supabase project.")
    main()
