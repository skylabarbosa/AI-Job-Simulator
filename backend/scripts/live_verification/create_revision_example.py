"""
Script to create the safe Version 3 DRAFT blueprint revision for Employee Performance Analysis.
Zero LLM calls.
Preserves Version 2 unchanged and approved.
Sets Version 3 to draft with the 3 learner-facing work areas:
1. Data Cleaning
2. SQL
3. Data Analysis
"""

import json
import os
from datetime import datetime, timezone
from uuid import UUID

from app.core.auth import AuthenticatedUser
from app.db.client import get_supabase_client
from app.schemas.auth import UserProfile
from app.schemas.blueprints import BlueprintUpdateRequest, ProjectBlueprint
from app.services.blueprint_service import revise_blueprint, update_blueprint_draft


TARGET_PROJECT_ID = UUID(os.environ["SKILLUP_VERIFICATION_PROJECT_ID"])

V3_THREE_WORK_AREAS_BLUEPRINT = {
    "project_summary": "Employee Performance Analysis project to evaluate workforce metrics across departments, compensation, tenure, and performance attributes using the employee_clean_readable dataset.",
    "workplace_goal": "Provide actionable insights into employee performance and identify patterns that help management make informed workforce decisions.",
    "modules": [
        {
            "name": "Data Cleaning",
            "description": "Prepare and validate the employee dataset before analysis.",
            "rationale": "Inspect table schema, column completeness, and data integrity to ensure dependable records prior to analysis.",
            "competencies": [
                {
                    "name": "Dataset Validation",
                    "description": "Validate schema structure, record counts, and column consistency.",
                    "concepts": [
                        {
                            "name": "Schema and Record Inspection",
                            "description": "Verify table columns, inferred types, and row completeness.",
                        }
                    ],
                }
            ],
        },
        {
            "name": "SQL",
            "description": "Use SQL queries to answer workforce and compensation questions.",
            "rationale": "Apply structured SQL queries, filtering conditions, and aggregations to answer workforce questions.",
            "competencies": [
                {
                    "name": "Workforce Querying and Aggregation",
                    "description": "Execute aggregation and conditional filtering on employee records.",
                    "concepts": [
                        {
                            "name": "Aggregation and Grouping",
                            "description": "Summarize compensation metrics by departmental groups.",
                        },
                        {
                            "name": "Conditional Filtering",
                            "description": "Filter workforce records using conditional criteria.",
                        },
                    ],
                }
            ],
        },
        {
            "name": "Data Analysis",
            "description": "Analyze employee performance and identify meaningful patterns.",
            "rationale": "Evaluate performance distribution and tenure metrics to produce actionable workforce insights.",
            "competencies": [
                {
                    "name": "Performance and Workforce Insights",
                    "description": "Analyze relationships between tenure, ratings, and performance.",
                    "concepts": [
                        {
                            "name": "Workforce Trend Analysis",
                            "description": "Interpret workforce metrics to support leadership decisions.",
                        }
                    ],
                }
            ],
        },
    ],
    "tasks": [
        {
            "title": "List All Employee Records",
            "workplace_context": "Management requires a complete inspection of the employee dataset to verify available records and field integrity before downstream analysis.",
            "instruction": "Write a SQL query to inspect and validate all employee records and fields to confirm dataset completeness prior to analysis.",
            "expected_outcome": "A complete record verification confirming all 1000 rows and 8 attributes from the employee dataset.",
            "difficulty": "easy",
            "task_kind": "sql",
            "related_module": "Data Cleaning",
            "related_competencies": ["Dataset Validation"],
            "related_concepts": ["Schema and Record Inspection"],
            "dataset_fields": [
                "Department",
                "Company Origin",
                "Tenure with the Company",
                "Salary",
                "PerformanceScore",
                "Work Ratings",
                "Hire_Year",
                "Hire_Month",
            ],
            "sql_tables": ["employee_clean_readable"],
            "sql_concepts": ["SELECT"],
            "evaluation_criteria": [
                {
                    "name": "Syntax Check",
                    "description": "Verify the SQL query syntax is correct.",
                    "what_should_be_checked": "The query uses SELECT * from employee_clean_readable.",
                    "evaluation_type": "deterministic",
                }
            ],
        },
        {
            "title": "Departmental Average Salary Analysis",
            "workplace_context": "Human Resources needs to understand compensation distribution across different departments.",
            "instruction": "Write a SQL query to calculate the average salary for each Department.",
            "expected_outcome": "A result set showing each department and its corresponding average salary.",
            "difficulty": "medium",
            "task_kind": "sql",
            "related_module": "SQL",
            "related_competencies": ["Workforce Querying and Aggregation"],
            "related_concepts": ["Aggregation and Grouping"],
            "dataset_fields": ["Department", "Salary"],
            "sql_tables": ["employee_clean_readable"],
            "sql_concepts": ["SELECT", "GROUP BY", "Aggregates"],
            "evaluation_criteria": [
                {
                    "name": "Grouping Check",
                    "description": "Verify the query groups by Department.",
                    "what_should_be_checked": "GROUP BY Department is present.",
                    "evaluation_type": "deterministic",
                },
                {
                    "name": "Aggregation Check",
                    "description": "Verify the average salary calculation.",
                    "what_should_be_checked": "AVG(Salary) is used in the SELECT clause.",
                    "evaluation_type": "deterministic",
                },
            ],
        },
        {
            "title": "Performance Score Filtering",
            "workplace_context": "Leadership wants to isolate high-performing employee records based on their PerformanceScore.",
            "instruction": "Write a SQL query to retrieve records where PerformanceScore is greater than a threshold.",
            "expected_outcome": "Filtered list of employee records meeting the performance threshold.",
            "difficulty": "medium",
            "task_kind": "sql",
            "related_module": "SQL",
            "related_competencies": ["Workforce Querying and Aggregation"],
            "related_concepts": ["Conditional Filtering"],
            "dataset_fields": [
                "Department",
                "Company Origin",
                "Tenure with the Company",
                "Salary",
                "PerformanceScore",
                "Work Ratings",
                "Hire_Year",
                "Hire_Month",
            ],
            "sql_tables": ["employee_clean_readable"],
            "sql_concepts": ["SELECT", "WHERE"],
            "evaluation_criteria": [
                {
                    "name": "Filter Check",
                    "description": "Verify the WHERE clause filters by PerformanceScore.",
                    "what_should_be_checked": "WHERE PerformanceScore condition is correctly applied.",
                    "evaluation_type": "deterministic",
                }
            ],
        },
        {
            "title": "Workforce Performance Pattern Analysis",
            "workplace_context": "Executive leadership needs an analytical assessment of performance score distributions across departments and tenure bands.",
            "instruction": "Analyze employee performance distributions and tenure metrics across departments to identify actionable workforce trends and compensation insights.",
            "expected_outcome": "An analytical breakdown highlighting high-performance departments and tenure patterns with recommendations for workforce planning.",
            "difficulty": "medium",
            "task_kind": "analysis",
            "related_module": "Data Analysis",
            "related_competencies": ["Performance and Workforce Insights"],
            "related_concepts": ["Workforce Trend Analysis"],
            "dataset_fields": [
                "Department",
                "PerformanceScore",
                "Salary",
                "Tenure with the Company",
                "Work Ratings",
            ],
            "sql_tables": [],
            "sql_concepts": [],
            "evaluation_criteria": [
                {
                    "name": "Pattern Identification",
                    "description": "Verify the analysis identifies meaningful performance and tenure patterns across departments.",
                    "what_should_be_checked": "The analysis evaluates performance scores and tenure distributions across departments.",
                    "evaluation_type": "qualitative",
                }
            ],
        },
    ],
}


def main():
    client = get_supabase_client()
    project = client.table("projects").select("*").eq("id", str(TARGET_PROJECT_ID)).single().execute().data
    print("Project found:", project["name"], f"({project['id']})")

    # Verify Version 2 exists and is approved
    v2_row = (
        client.table("project_blueprints")
        .select("id, version, status, blueprint_json")
        .eq("project_id", str(TARGET_PROJECT_ID))
        .eq("version", 2)
        .single()
        .execute()
        .data
    )
    print("Approved Version 2 found:", v2_row["id"], "status:", v2_row["status"])
    assert v2_row["status"] == "approved", "Version 2 must be approved!"

    user_id = project.get("created_by") or "00000000-0000-0000-0000-000000000000"
    user = AuthenticatedUser(id=user_id, email="business@skillup.local")
    profile = UserProfile(id=user_id, email="business@skillup.local", role="business")

    # Call revise_blueprint to create next version draft
    print("Creating draft revision...")
    revised = revise_blueprint(TARGET_PROJECT_ID, user, profile)
    print(f"Revision created: Version {revised.version}, Status: {revised.status}, ID: {revised.id}")
    assert revised.version == 3, f"Expected Version 3, got {revised.version}"
    assert revised.status == "draft", f"Expected draft, got {revised.status}"

    # Update draft with the 3 work areas
    print("Updating draft with the 3 Data Analyst work areas...")
    v3_validated = ProjectBlueprint.model_validate(V3_THREE_WORK_AREAS_BLUEPRINT)
    updated = update_blueprint_draft(
        TARGET_PROJECT_ID,
        revised.id,
        BlueprintUpdateRequest(blueprint_json=v3_validated),
        user,
        profile,
    )
    print("Draft updated successfully!")
    print("Modules in Version 3:", [m.name for m in updated.blueprint_json.modules])
    print("Tasks in Version 3:", [f"{t.title} -> {t.related_module}" for t in updated.blueprint_json.tasks])

    # Re-verify Version 2 in database is untouched
    v2_check = (
        client.table("project_blueprints")
        .select("id, version, status, blueprint_json")
        .eq("id", v2_row["id"])
        .single()
        .execute()
        .data
    )
    assert v2_check["status"] == "approved"
    assert v2_check["version"] == 2
    assert v2_check["blueprint_json"] == v2_row["blueprint_json"]
    print("VERIFICATION CONFIRMED: Version 2 remains approved and completely unchanged!")
    print("Draft Version 3 is ready for Business review/approval.")


if __name__ == "__main__":
    if os.getenv("SKILLUP_RUN_LIVE_VERIFICATION") != "yes":
        raise SystemExit("Refusing mutation. Set SKILLUP_RUN_LIVE_VERIFICATION=yes and SKILLUP_VERIFICATION_PROJECT_ID to an isolated draft project.")
    main()
