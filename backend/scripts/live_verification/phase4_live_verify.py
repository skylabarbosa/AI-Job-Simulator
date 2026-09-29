"""Temporary real HTTP/database verification for the Phase 4 decision endpoint."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from uuid import uuid4

from supabase import create_client

from phase3_live_verify import (
    BASE_URL,
    STAMP,
    blueprint,
    cleanup,
    create_auth_user,
    headers,
    request,
    require_env,
    wait_for_server,
)


ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    client = create_client(require_env("SUPABASE_URL"), require_env("SUPABASE_SERVICE_ROLE_KEY"))
    ids = {"submission_ids": [], "evaluation_ids": []}
    server = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8766"],
        cwd=ROOT,
    )
    try:
        wait_for_server()
        business = create_auth_user(client, f"{STAMP}.phase4.business@example.com", "business")
        strong = create_auth_user(client, f"{STAMP}.phase4.strong@example.com", "learner")
        struggling = create_auth_user(client, f"{STAMP}.phase4.struggling@example.com", "learner")
        ids.update({"business_id": business.user_id, "learner_a_id": strong.user_id, "learner_b_id": struggling.user_id})
        project = request("POST", "/projects", session=business, json={
            "name": f"Phase 4 Verification {STAMP}",
            "business_problem": "Verify adaptive presentation decisions.",
            "work_requirements": "One required generic analysis task.",
            "desired_outcome": "Keep task path fixed while adapting support.",
        }).json()
        project_id = project["id"]
        ids["project_id"] = project_id
        inserted = client.table("project_blueprints").insert({
            "project_id": project_id, "version": 1, "status": "draft", "source_dataset_ids": [],
            "blueprint_json": blueprint(), "provider": "phase4_verification", "generated_by": business.user_id,
        }).execute().data[0]
        request("POST", f"/projects/{project_id}/blueprint/approve", session=business, json={"blueprint_id": inserted["id"]})
        request("POST", f"/projects/{project_id}/blueprint/materialize", session=business)
        task = client.table("tasks").select("*").eq("project_id", project_id).order("position").limit(1).execute().data[0]
        request("POST", f"/projects/{project_id}/publish", session=business)
        links = client.table("task_concepts").select("concept_id").eq("task_id", task["id"]).execute().data
        competency_links = client.table("task_competencies").select("competency_id").eq("task_id", task["id"]).execute().data
        assert links, "materialized task has no concept evidence"
        client.table("user_skills").insert({"learner_id": strong.user_id, "concept_id": links[0]["concept_id"], "current_score": 90, "level": "proficient"}).execute()
        for link in competency_links:
            client.table("user_skills").insert({"learner_id": strong.user_id, "competency_id": link["competency_id"], "current_score": 90, "level": "proficient"}).execute()

        strong_decision = request("GET", f"/projects/{project_id}/tasks/{task['id']}/adaptive-decision", session=strong).json()
        assert strong_decision["target_task_id"] == task["id"]
        assert strong_decision["support_level"] == "independent"
        print("[PASS] strong learner gets independent presentation on required task")

        request("POST", f"/projects/{project_id}/tasks/{task['id']}/start", session=struggling)
        for _ in range(2):
            result = request("POST", f"/projects/{project_id}/tasks/{task['id']}/submissions", session=struggling, json={"response": "bad"}).json()
            ids["submission_ids"].append(result["submission_id"])
            if result.get("evaluation_id"):
                ids["evaluation_ids"].append(result["evaluation_id"])
        weak_decision = request("GET", f"/projects/{project_id}/tasks/{task['id']}/adaptive-decision", session=struggling).json()
        assert weak_decision["target_task_id"] == task["id"]
        assert weak_decision["support_level"] == "guided"
        print("[PASS] struggling learner gets guided presentation on same required task")

        before = client.table("simulations").select("status, progress").eq("learner_id", strong.user_id).eq("project_id", project_id).execute().data
        assert before == []
        assert request("GET", f"/projects/{project_id}/tasks/{task['id']}/adaptive-decision", session=strong).status_code == 200
        print("[PASS] decision is read-only and does not create completion state")
        print(json.dumps({"project_id": project_id, "task_id": task["id"], "strong": strong_decision, "struggling": weak_decision}, default=str))
    finally:
        print("Cleanup:", json.dumps(cleanup(client, ids), default=str))
        server.terminate()
        server.wait(timeout=10)


if __name__ == "__main__":
    if os.getenv("SKILLUP_RUN_LIVE_VERIFICATION") != "yes":
        raise SystemExit("Refusing hosted verification. Set SKILLUP_RUN_LIVE_VERIFICATION=yes after selecting an isolated Supabase project.")
    main()
