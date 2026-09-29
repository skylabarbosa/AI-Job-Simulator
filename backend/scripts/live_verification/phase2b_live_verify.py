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

BASE_URL = "http://127.0.0.1:8765/api"
STAMP = f"phase2b-live-{int(time.time())}-{uuid4().hex[:6]}"
PASSWORD = f"Phase2b!{uuid4().hex[:12]}"


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
        "project_summary": "Temporary internal verification project for generic evaluator routing.",
        "workplace_goal": "Verify data cleaning and data analysis learner submissions through the live pipeline.",
        "modules": [
            {
                "name": "Data Cleaning",
                "description": "Prepare a small dataset by describing cleaning, validation, and transformation actions.",
                "rationale": "Use validation notes to identify missing values, invalid values, and cleaning actions.",
                "competencies": [
                    {
                        "name": "Cleaning Quality",
                        "description": "Recognize and explain data quality remediation steps.",
                        "concepts": [
                            {"name": "Missing Values", "description": "Identify and handle missing or blank values."},
                            {"name": "Validation Checks", "description": "Verify cleaned data against quality rules."},
                        ],
                    }
                ],
            },
            {
                "name": "Data Analysis",
                "description": "Interpret a small result set using evidence and conclusions.",
                "rationale": "Analyze metrics, cite evidence, and produce a decision-ready conclusion.",
                "competencies": [
                    {
                        "name": "Evidence Based Analysis",
                        "description": "Use evidence and reasoning to explain findings.",
                        "concepts": [
                            {"name": "Findings", "description": "State patterns or trends from the data."},
                            {"name": "Conclusions", "description": "Connect evidence to a decision or recommendation."},
                        ],
                    }
                ],
            },
        ],
        "tasks": [
            {
                "title": "Temporary Cleaning Verification Task",
                "workplace_context": "A small imported customer list has missing values, duplicate rows, and invalid category entries.",
                "instruction": "Describe the cleaning actions you would take: handle missing values, remove or flag duplicates, standardize invalid values, and validate the cleaned output.",
                "expected_outcome": "A concise cleaning note that covers missing value handling, invalid or duplicate values, transformation or standardization, and validation checks.",
                "difficulty": "easy",
                "task_kind": "analysis",
                "related_module": "Data Cleaning",
                "related_competencies": ["Cleaning Quality"],
                "related_concepts": ["Missing Values", "Validation Checks"],
                "dataset_fields": ["customer_id", "segment", "signup_date"],
                "sql_tables": [],
                "sql_concepts": [],
                "evaluation_criteria": [
                    {
                        "name": "Cleaning operations",
                        "description": "The answer explains concrete data cleaning operations.",
                        "what_should_be_checked": "missing values invalid duplicate standardize validate clean transform",
                        "evaluation_type": "deterministic",
                    }
                ],
            },
            {
                "title": "Temporary Analysis Verification Task",
                "workplace_context": "A short weekly metrics summary shows conversion rate increased while support tickets also increased.",
                "instruction": "Write an analysis that states a finding, cites data evidence or metrics, explains reasoning, and gives a conclusion or recommendation.",
                "expected_outcome": "A concise analysis with interpretation, evidence, reasoning, and a conclusion.",
                "difficulty": "easy",
                "task_kind": "analysis",
                "related_module": "Data Analysis",
                "related_competencies": ["Evidence Based Analysis"],
                "related_concepts": ["Findings", "Conclusions"],
                "dataset_fields": ["week", "conversion_rate", "support_tickets"],
                "sql_tables": [],
                "sql_concepts": [],
                "evaluation_criteria": [
                    {
                        "name": "Findings with evidence",
                        "description": "The answer explains findings using data evidence and a conclusion.",
                        "what_should_be_checked": "finding trend data evidence metric because conclusion recommendation",
                        "evaluation_type": "deterministic",
                    }
                ],
            },
        ],
    }


def newest_evaluation(client: Any, submission_id: str) -> dict[str, Any]:
    rows = table(client, "evaluations").select("*").eq("submission_id", submission_id).order("created_at", desc=True).limit(1).execute().data
    return rows[0]


def cleanup(client: Any, ids: dict[str, Any]) -> dict[str, Any]:
    removed: dict[str, Any] = {}
    project_id = ids.get("project_id")
    learner_id = ids.get("learner_id")
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
            query = query.in_(field, value)
        else:
            query = query.eq(field, value)
        try:
            removed[table_name] = len(query.execute().data or [])
        except Exception as error:
            removed[table_name] = f"failed: {error}"
    if learner_id:
        try:
            removed["learner_user_skills_after_project_delete"] = len(
                table(client, "user_skills").select("id").eq("learner_id", learner_id).execute().data or []
            )
        except Exception as error:
            removed["learner_user_skills_after_project_delete"] = f"check failed: {error}"
    for auth_id in [ids.get("business_id"), ids.get("learner_id")]:
        if auth_id:
            try:
                client.auth.admin.delete_user(auth_id)
                removed[f"auth_user:{auth_id}"] = "deleted"
            except Exception as error:
                removed[f"auth_user:{auth_id}"] = f"failed: {error}"
    return removed


def main() -> None:
    client = create_client(require_env("SUPABASE_URL"), require_env("SUPABASE_SERVICE_ROLE_KEY"))
    ids: dict[str, Any] = {"submission_ids": [], "evaluation_ids": []}
    server = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8765"],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    report: dict[str, Any] = {"stamp": STAMP}
    try:
        wait_for_server()
        business = create_auth_user(client, f"{STAMP}.business@example.com", "business")
        learner = create_auth_user(client, f"{STAMP}.learner@example.com", "learner")
        ids.update({"business_id": business.user_id, "learner_id": learner.user_id})

        project = request(
            "POST",
            "/projects",
            session=business,
            json={
                "name": f"Temporary Phase 2B Verification {STAMP}",
                "business_problem": "Need a temporary generic live-path evaluator verification project.",
                "work_requirements": "Include data cleaning and data analysis tasks with real metadata.",
                "desired_outcome": "Verify live learner submissions persist and route to the correct evaluators.",
            },
        ).json()
        project_id = project["id"]
        ids["project_id"] = project_id

        bp_insert = table(client, "project_blueprints").insert(
            {
                "project_id": project_id,
                "version": 1,
                "status": "draft",
                "source_dataset_ids": [],
                "blueprint_json": blueprint(),
                "provider": "phase2b_live_verification",
                "model": None,
                "prompt_version": None,
                "generated_by": business.user_id,
            }
        ).execute().data[0]
        approved = request("POST", f"/projects/{project_id}/blueprint/approve", session=business, json={"blueprint_id": bp_insert["id"]}).json()
        materialized = request("POST", f"/projects/{project_id}/blueprint/materialize", session=business).json()

        tasks = table(client, "tasks").select("*").eq("project_id", project_id).order("position").execute().data
        cleaning_task = next(row for row in tasks if "Cleaning" in row["title"])
        analysis_task = next(row for row in tasks if "Analysis" in row["title"])
        table(client, "tasks").update({"task_type": "Data Cleaning"}).eq("id", cleaning_task["id"]).execute()
        table(client, "tasks").update({"task_type": "Data Analysis"}).eq("id", analysis_task["id"]).execute()
        published = request("POST", f"/projects/{project_id}/publish", session=business).json()

        available = request("GET", "/projects/available", session=learner).json()
        learner_tasks = request("GET", f"/projects/{project_id}/tasks", session=learner).json()
        report["project"] = {
            "id": project_id,
            "name": project["name"],
            "approved_blueprint": approved["id"],
            "materialized": materialized,
            "published_status": published["status"],
            "learner_discoverable": any(item["id"] == project_id for item in available),
            "learner_task_types": {item["title"]: item["task_type"] for item in learner_tasks},
        }

        def exercise(task: dict[str, Any], invalid: str, valid: str) -> dict[str, Any]:
            started = request("POST", f"/projects/{project_id}/tasks/{task['id']}/start", session=learner).json()
            invalid_result = request("POST", f"/projects/{project_id}/tasks/{task['id']}/submissions", session=learner, json={"response": invalid}).json()
            valid_result = request("POST", f"/projects/{project_id}/tasks/{task['id']}/submissions", session=learner, json={"response": valid}).json()
            ids["submission_ids"].extend([invalid_result["submission_id"], valid_result["submission_id"]])
            ids["evaluation_ids"].extend([invalid_result["evaluation_id"], valid_result["evaluation_id"]])
            invalid_eval = newest_evaluation(client, invalid_result["submission_id"])
            valid_eval = newest_evaluation(client, valid_result["submission_id"])
            return {
                "started_task_type": started["task_type"],
                "invalid_result": invalid_result,
                "valid_result": valid_result,
                "invalid_evaluation": invalid_eval,
                "valid_evaluation": valid_eval,
            }

        report["data_cleaning"] = exercise(
            {"id": cleaning_task["id"]},
            "looks fine",
            "I cleaned the dataset by handling missing values, removing duplicate records, standardizing invalid segment values, transforming date formats, and validating the cleaned output with quality checks.",
        )
        report["data_analysis"] = exercise(
            {"id": analysis_task["id"]},
            "looks fine",
            "My finding is that the conversion trend improved while support tickets also rose. The data evidence is the conversion_rate metric increasing because weekly results changed alongside higher support_tickets. My conclusion is to recommend checking onboarding friction before expanding the campaign.",
        )

        # Semantic probe on the temporary analysis task only.
        table(client, "rubrics").update(
            {
                "criteria": [
                    {
                        "name": "Reasoned interpretation",
                        "description": "Evaluate reasoning quality semantically.",
                        "what_should_be_checked": "reasoning quality and interpretation",
                        "evaluation_type": "qualitative",
                    }
                ]
            }
        ).eq("task_id", analysis_task["id"]).execute()
        request("POST", f"/projects/{project_id}/tasks/{analysis_task['id']}/start", session=learner)
        semantic_result = request(
            "POST",
            f"/projects/{project_id}/tasks/{analysis_task['id']}/submissions",
            session=learner,
            json={"response": "I interpret the pattern using evidence and explain my conclusion with reasoning."},
        ).json()
        ids["submission_ids"].append(semantic_result["submission_id"])
        ids["evaluation_ids"].append(semantic_result["evaluation_id"])
        report["semantic_probe"] = {
            "result": semantic_result,
            "evaluation": newest_evaluation(client, semantic_result["submission_id"]),
        }

        submissions = table(client, "submissions").select("*").in_("id", ids["submission_ids"]).execute().data or []
        skills = table(client, "user_skills").select("*").eq("learner_id", learner.user_id).execute().data or []
        report["persistence"] = {
            "submission_count": len(submissions),
            "evaluation_count": len(table(client, "evaluations").select("id").in_("id", ids["evaluation_ids"]).execute().data or []),
            "learner_skill_count": len(skills),
            "duplicate_skill_identities": len(skills) - len({(row.get("competency_id"), row.get("concept_id")) for row in skills}),
        }
        report["routing"] = {"SQL": "SQLEvaluator", "Data Cleaning": "DataCleaningEvaluator", "Data Analysis": "DataAnalysisEvaluator"}
    finally:
        report["cleanup"] = cleanup(client, ids)
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()
        print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    if os.getenv("SKILLUP_RUN_LIVE_VERIFICATION") != "yes":
        raise SystemExit("Refusing hosted verification. Set SKILLUP_RUN_LIVE_VERIFICATION=yes after selecting an isolated Supabase project.")
    main()
