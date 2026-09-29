import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import UUID, uuid4

from fastapi import HTTPException

from app.api.routes.projects import list_available_projects
from app.core.auth import AuthenticatedUser
from app.schemas.auth import UserProfile
from app.schemas.blueprints import (
    BlueprintReviseRequest,
    BlueprintUpdateRequest,
    ProjectBlueprint,
)
from app.services.blueprint_service import (
    approve_blueprint,
    get_approved_overview,
    get_latest_blueprint,
    revise_blueprint,
    update_blueprint_draft,
)


def sample_v2_blueprint_json() -> dict:
    return {
        "project_summary": "Employee Performance Analysis v2.",
        "workplace_goal": "Evaluate workforce metrics across departments.",
        "modules": [
            {
                "name": "Dataset Preparation and Inspection",
                "description": "Examine schema and basic attributes.",
                "rationale": "Inspect records before aggregations.",
                "competencies": [{
                    "name": "Data Schema Review",
                    "description": "Understand columns.",
                    "concepts": [{"name": "Column Identification", "description": "Identify columns."}],
                }],
            },
            {
                "name": "Workforce Performance Querying",
                "description": "Use SQL queries to analyze performance.",
                "rationale": "Apply SQL queries for business metrics.",
                "competencies": [{
                    "name": "Data Filtering and Grouping",
                    "description": "Aggregate and filter.",
                    "concepts": [
                        {"name": "SELECT and WHERE", "description": "Row filtering."},
                        {"name": "GROUP BY and Aggregates", "description": "Summaries."},
                    ],
                }],
            },
        ],
        "tasks": [
            {
                "title": "List All Employee Records",
                "workplace_context": "Management needs all records.",
                "instruction": "Write SQL query to list all employee records.",
                "expected_outcome": "Complete listing of records.",
                "difficulty": "easy",
                "task_kind": "sql",
                "related_module": "Dataset Preparation and Inspection",
                "related_competencies": ["Data Schema Review"],
                "related_concepts": ["Column Identification"],
                "dataset_fields": ["Department", "Salary"],
                "sql_tables": ["employee_clean_readable"],
                "sql_concepts": ["SELECT"],
                "evaluation_criteria": [{
                    "name": "Syntax Check",
                    "description": "Check query syntax.",
                    "what_should_be_checked": "Uses SELECT *.",
                    "evaluation_type": "deterministic",
                }],
            },
            {
                "title": "Departmental Average Salary Analysis",
                "workplace_context": "HR compensation study.",
                "instruction": "Calculate average salary by department.",
                "expected_outcome": "Average salary per department.",
                "difficulty": "medium",
                "task_kind": "sql",
                "related_module": "Workforce Performance Querying",
                "related_competencies": ["Data Filtering and Grouping"],
                "related_concepts": ["GROUP BY and Aggregates"],
                "dataset_fields": ["Department", "Salary"],
                "sql_tables": ["employee_clean_readable"],
                "sql_concepts": ["SELECT", "GROUP BY", "Aggregates"],
                "evaluation_criteria": [{
                    "name": "Grouping Check",
                    "description": "Check group by.",
                    "what_should_be_checked": "GROUP BY Department.",
                    "evaluation_type": "deterministic",
                }],
            },
            {
                "title": "Performance Score Filtering",
                "workplace_context": "Leadership wants high performers.",
                "instruction": "Filter by performance score.",
                "expected_outcome": "Filtered records.",
                "difficulty": "medium",
                "task_kind": "sql",
                "related_module": "Workforce Performance Querying",
                "related_competencies": ["Data Filtering and Grouping"],
                "related_concepts": ["SELECT and WHERE"],
                "dataset_fields": ["Department", "Salary"],
                "sql_tables": ["employee_clean_readable"],
                "sql_concepts": ["SELECT", "WHERE"],
                "evaluation_criteria": [{
                    "name": "Filter Check",
                    "description": "Check WHERE condition.",
                    "what_should_be_checked": "WHERE PerformanceScore > threshold.",
                    "evaluation_type": "deterministic",
                }],
            },
        ],
    }


def sample_v3_three_work_areas_json() -> dict:
    return {
        "project_summary": "Employee Performance Analysis v3.",
        "workplace_goal": "Evaluate workforce metrics with three work areas.",
        "modules": [
            {
                "name": "Data Cleaning",
                "description": "Prepare and validate the employee dataset before analysis.",
                "rationale": "Inspect schema and validate records before analysis.",
                "competencies": [{
                    "name": "Dataset Validation",
                    "description": "Validate data schema and completeness.",
                    "concepts": [{"name": "Schema and Record Inspection", "description": "Check columns and rows."}],
                }],
            },
            {
                "name": "SQL",
                "description": "Use SQL queries to answer workforce and compensation questions.",
                "rationale": "Apply SQL queries, grouping, and filters to evaluate workforce data.",
                "competencies": [{
                    "name": "Workforce Querying and Aggregation",
                    "description": "Aggregate and filter employee records.",
                    "concepts": [
                        {"name": "Aggregation and Grouping", "description": "Group by departments."},
                        {"name": "Conditional Filtering", "description": "Filter by criteria."},
                    ],
                }],
            },
            {
                "name": "Data Analysis",
                "description": "Analyze employee performance and identify meaningful patterns.",
                "rationale": "Evaluate workforce trends and tenure patterns to produce insights.",
                "competencies": [{
                    "name": "Performance and Workforce Insights",
                    "description": "Interpret performance metrics.",
                    "concepts": [{"name": "Workforce Trend Analysis", "description": "Identify trends."}],
                }],
            },
        ],
        "tasks": [
            {
                "title": "List All Employee Records",
                "workplace_context": "Management needs to verify record completeness.",
                "instruction": "Inspect and validate all employee records and fields to confirm dataset completeness prior to analysis.",
                "expected_outcome": "Complete record verification confirming all rows and attributes.",
                "difficulty": "easy",
                "task_kind": "sql",
                "related_module": "Data Cleaning",
                "related_competencies": ["Dataset Validation"],
                "related_concepts": ["Schema and Record Inspection"],
                "dataset_fields": ["Department", "Salary"],
                "sql_tables": ["employee_clean_readable"],
                "sql_concepts": ["SELECT"],
                "evaluation_criteria": [{
                    "name": "Syntax Check",
                    "description": "Verify SQL syntax.",
                    "what_should_be_checked": "SELECT * from employee_clean_readable.",
                    "evaluation_type": "deterministic",
                }],
            },
            {
                "title": "Departmental Average Salary Analysis",
                "workplace_context": "HR compensation study across departments.",
                "instruction": "Write a SQL query to calculate the average salary for each Department.",
                "expected_outcome": "Average salary per department.",
                "difficulty": "medium",
                "task_kind": "sql",
                "related_module": "SQL",
                "related_competencies": ["Workforce Querying and Aggregation"],
                "related_concepts": ["Aggregation and Grouping"],
                "dataset_fields": ["Department", "Salary"],
                "sql_tables": ["employee_clean_readable"],
                "sql_concepts": ["SELECT", "GROUP BY", "Aggregates"],
                "evaluation_criteria": [{
                    "name": "Grouping Check",
                    "description": "Verify GROUP BY Department.",
                    "what_should_be_checked": "GROUP BY Department is present.",
                    "evaluation_type": "deterministic",
                }],
            },
            {
                "title": "Performance Score Filtering",
                "workplace_context": "Leadership wants to isolate high-performing records.",
                "instruction": "Write a SQL query to retrieve records where PerformanceScore is greater than a threshold.",
                "expected_outcome": "Filtered list of employee records.",
                "difficulty": "medium",
                "task_kind": "sql",
                "related_module": "SQL",
                "related_competencies": ["Workforce Querying and Aggregation"],
                "related_concepts": ["Conditional Filtering"],
                "dataset_fields": ["Department", "Salary"],
                "sql_tables": ["employee_clean_readable"],
                "sql_concepts": ["SELECT", "WHERE"],
                "evaluation_criteria": [{
                    "name": "Filter Check",
                    "description": "Verify WHERE filter.",
                    "what_should_be_checked": "WHERE PerformanceScore condition applied.",
                    "evaluation_type": "deterministic",
                }],
            },
            {
                "title": "Workforce Performance Pattern Analysis",
                "workplace_context": "Executive leadership needs an analytical assessment of performance distributions.",
                "instruction": "Analyze employee performance distributions and tenure metrics across departments to identify actionable workforce trends and compensation insights.",
                "expected_outcome": "An analytical breakdown highlighting high-performance departments and tenure patterns with recommendations for workforce planning.",
                "difficulty": "medium",
                "task_kind": "analysis",
                "related_module": "Data Analysis",
                "related_competencies": ["Performance and Workforce Insights"],
                "related_concepts": ["Workforce Trend Analysis"],
                "dataset_fields": ["Department", "Salary"],
                "sql_tables": [],
                "sql_concepts": [],
                "evaluation_criteria": [{
                    "name": "Pattern Identification",
                    "description": "Verify the analysis identifies meaningful patterns.",
                    "what_should_be_checked": "Evaluates performance scores and tenure distributions.",
                    "evaluation_type": "qualitative",
                }],
            },
        ],
    }


class FakeQuery:
    def __init__(self, client, table_name):
        self.client = client
        self.table_name = table_name
        self.data = list(client.records.get(table_name, []))

    def select(self, *_args):
        return self

    def eq(self, field, value):
        self.data = [record for record in self.data if str(record.get(field)) == str(value)]
        return self

    def in_(self, field, values):
        str_values = {str(v) for v in values}
        self.data = [record for record in self.data if str(record.get(field)) in str_values]
        return self

    def order(self, field, desc=False):
        self.data.sort(key=lambda r: r.get(field, 0), reverse=desc)
        return self

    def limit(self, count):
        self.data = self.data[:count]
        return self

    def gt(self, field, value):
        self.data = [record for record in self.data if record.get(field, 0) > value]
        return self

    def maybe_single(self):
        return self

    def insert(self, payload):
        self.client.operations.append(("insert", self.table_name, payload))
        record = {
            "id": str(uuid4()),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            **payload,
        }
        self.client.records.setdefault(self.table_name, []).append(record)
        self.data = [record]
        return self

    def update(self, changes):
        self.client.operations.append(("update", self.table_name, changes))
        for r in self.client.records.get(self.table_name, []):
            if any(str(r.get("id")) == str(item.get("id")) for item in self.data):
                r.update(changes)
        self.data = [{**item, **changes} for item in self.data]
        return self

    def execute(self):
        return SimpleNamespace(data=self.data)


class FakeSupabaseClient:
    def __init__(self, records):
        self.records = {k: list(v) for k, v in records.items()}
        self.operations = []

    def table(self, table_name):
        return FakeQuery(self, table_name)


class BlueprintRevisionTests(unittest.TestCase):
    def setUp(self):
        self.project_id = uuid4()
        self.owner_id = str(uuid4())
        self.business_user = AuthenticatedUser(id=self.owner_id, email="business@example.com")
        self.business_profile = UserProfile(id=self.owner_id, email="business@example.com", role="business")
        self.admin_user = AuthenticatedUser(id=str(uuid4()), email="admin@example.com")
        self.admin_profile = UserProfile(id=self.admin_user.id, email="admin@example.com", role="admin")
        self.learner_user = AuthenticatedUser(id=str(uuid4()), email="learner@example.com")
        self.learner_profile = UserProfile(id=self.learner_user.id, email="learner@example.com", role="learner")

        self.project = {
            "id": str(self.project_id),
            "name": "Employee Performance Analysis",
            "slug": "employee-performance-analysis",
            "business_problem": "Analyze employee metrics.",
            "work_requirements": "SQL and data analysis.",
            "desired_outcome": "Actionable workforce insights.",
            "status": "active",
            "created_by": self.owner_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        self.v2_blueprint_id = str(uuid4())
        self.v2_blueprint = {
            "id": self.v2_blueprint_id,
            "project_id": str(self.project_id),
            "version": 2,
            "status": "approved",
            "source_dataset_ids": [str(uuid4())],
            "blueprint_json": sample_v2_blueprint_json(),
            "provider": "gemini",
            "model": "gemini-3.5-flash-lite",
            "prompt_version": "phase4a3-v2",
            "generated_by": self.owner_id,
            "approved_by": self.owner_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "approved_at": datetime.now(timezone.utc).isoformat(),
        }

        self.dataset = {
            "id": str(uuid4()),
            "project_id": str(self.project_id),
            "file_name": "employee_clean_readable.csv",
            "status": "ready",
            "row_count": 1000,
            "column_count": 2,
            "schema_metadata": {
                "table_name": "employee_clean_readable",
                "columns": [
                    {"name": "Department", "missing_count": 0},
                    {"name": "Salary", "missing_count": 0},
                ],
            },
        }

    def client(self, *, blueprints=None):
        return FakeSupabaseClient({
            "projects": [dict(self.project)],
            "project_blueprints": [dict(bp) for bp in (blueprints or [self.v2_blueprint])],
            "datasets": [dict(self.dataset)],
        })

    # Test 1: Version 2 remains unchanged after revision
    @patch("app.services.blueprint_service.get_supabase_client")
    @patch("app.services.blueprint_service._get_project")
    def test_1_version_2_remains_unchanged(self, get_project, get_client):
        db = self.client()
        get_project.return_value = self.project
        get_client.return_value = db

        v2_copy_before = dict(self.v2_blueprint)

        revised = revise_blueprint(self.project_id, self.business_user, self.business_profile)

        # Version 2 in database is untouched
        v2_in_db = next(bp for bp in db.records["project_blueprints"] if bp["version"] == 2)
        self.assertEqual(v2_in_db["id"], self.v2_blueprint_id)
        self.assertEqual(v2_in_db["status"], "approved")
        self.assertEqual(v2_in_db["version"], 2)
        self.assertEqual(v2_in_db["blueprint_json"], v2_copy_before["blueprint_json"])
        draft = next(bp for bp in db.records["project_blueprints"] if bp["version"] == 3)
        persisted_keys = [task["task_key"] for task in draft["blueprint_json"]["tasks"]]
        self.assertEqual(len(persisted_keys), len(set(persisted_keys)))
        self.assertTrue(all(persisted_keys))

    # Test 2: Revision creates Version 3 as draft
    @patch("app.services.blueprint_service.get_supabase_client")
    @patch("app.services.blueprint_service._get_project")
    def test_2_revision_creates_version_3_as_draft(self, get_project, get_client):
        db = self.client()
        get_project.return_value = self.project
        get_client.return_value = db

        revised = revise_blueprint(self.project_id, self.business_user, self.business_profile)

        self.assertEqual(revised.version, 3)
        self.assertEqual(revised.status, "draft")
        self.assertEqual(revised.provider, "business_revision")
        self.assertIsNone(revised.approved_at)
        self.assertIsNone(revised.approved_by)

    # Test 3: Only Business owner/admin can revise
    @patch("app.services.blueprint_service.get_supabase_client")
    @patch("app.services.blueprint_service._get_project")
    def test_3_only_business_owner_or_admin_can_revise(self, get_project, get_client):
        db = self.client()
        get_project.return_value = self.project
        get_client.return_value = db

        # Business owner succeeds
        owner_result = revise_blueprint(self.project_id, self.business_user, self.business_profile)
        self.assertEqual(owner_result.version, 3)

        # Admin also succeeds (creates or returns draft)
        admin_result = revise_blueprint(self.project_id, self.admin_user, self.admin_profile)
        self.assertEqual(admin_result.version, 3)

        # Another business user who is not owner fails with 404
        other_user = AuthenticatedUser(id=str(uuid4()), email="other@example.com")
        other_profile = UserProfile(id=other_user.id, email="other@example.com", role="business")
        with self.assertRaises(HTTPException) as error:
            revise_blueprint(self.project_id, other_user, other_profile)
        self.assertEqual(error.exception.status_code, 404)

    # Test 4: Learner cannot revise
    @patch("app.services.blueprint_service.get_supabase_client")
    @patch("app.services.blueprint_service._get_project")
    def test_4_learner_cannot_revise(self, get_project, get_client):
        get_project.return_value = self.project

        with self.assertRaises(HTTPException) as error:
            revise_blueprint(self.project_id, self.learner_user, self.learner_profile)
        self.assertEqual(error.exception.status_code, 403)

        with self.assertRaises(HTTPException) as error:
            update_blueprint_draft(
                self.project_id,
                uuid4(),
                BlueprintUpdateRequest(blueprint_json=ProjectBlueprint.model_validate(sample_v3_three_work_areas_json())),
                self.learner_user,
                self.learner_profile,
            )
        self.assertEqual(error.exception.status_code, 403)

    # Test 5: Draft V3 is not learner-visible
    @patch("app.services.blueprint_service.get_supabase_client")
    @patch("app.services.blueprint_service._get_project")
    @patch("app.api.routes.projects.get_supabase_client")
    def test_5_draft_v3_not_learner_visible(self, route_client, service_project, service_client):
        v3_draft = {
            "id": str(uuid4()),
            "project_id": str(self.project_id),
            "version": 3,
            "status": "draft",
            "source_dataset_ids": [str(uuid4())],
            "blueprint_json": sample_v3_three_work_areas_json(),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        db = self.client(blueprints=[self.v2_blueprint, v3_draft])
        service_project.return_value = self.project
        service_client.return_value = db
        route_client.return_value = db

        # Learner overview sees approved Version 2, NOT draft Version 3
        overview = get_approved_overview(self.project_id, self.learner_user, self.learner_profile)
        self.assertEqual(overview.version, 2)
        self.assertEqual([wa.name for wa in overview.work_areas], [
            "Dataset Preparation and Inspection",
            "Workforce Performance Querying",
        ])

        # Learner available projects list also only projects approved version 2
        available = list_available_projects(self.learner_profile)
        self.assertEqual(len(available), 1)
        self.assertEqual([wa.name for wa in available[0].work_areas], [
            "Dataset Preparation and Inspection",
            "Workforce Performance Querying",
        ])

    # Test 6: V3 can contain three work areas
    @patch("app.services.blueprint_service.get_supabase_client")
    @patch("app.services.blueprint_service._get_project")
    def test_6_v3_can_contain_three_work_areas(self, get_project, get_client):
        v3_id = str(uuid4())
        v3_draft = {
            "id": v3_id,
            "project_id": str(self.project_id),
            "version": 3,
            "status": "draft",
            "source_dataset_ids": [str(uuid4())],
            "blueprint_json": sample_v2_blueprint_json(),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        db = self.client(blueprints=[self.v2_blueprint, v3_draft])
        get_project.return_value = self.project
        get_client.return_value = db

        v3_content = ProjectBlueprint.model_validate(sample_v3_three_work_areas_json())
        updated = update_blueprint_draft(
            self.project_id,
            UUID(v3_id),
            BlueprintUpdateRequest(blueprint_json=v3_content),
            self.business_user,
            self.business_profile,
        )

        self.assertEqual(len(updated.blueprint_json.modules), 3)
        module_names = [m.name for m in updated.blueprint_json.modules]
        self.assertEqual(module_names, ["Data Cleaning", "SQL", "Data Analysis"])

    # Test 7: Internal competencies/concepts/rubrics remain hidden from learner projection
    @patch("app.services.blueprint_service.get_supabase_client")
    @patch("app.services.blueprint_service._get_project")
    def test_7_internal_hierarchy_hidden_from_learner_projection(self, get_project, get_client):
        v3_approved = {
            "id": str(uuid4()),
            "project_id": str(self.project_id),
            "version": 3,
            "status": "approved",
            "source_dataset_ids": [str(uuid4())],
            "blueprint_json": sample_v3_three_work_areas_json(),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "approved_at": datetime.now(timezone.utc).isoformat(),
        }
        db = self.client(blueprints=[self.v2_blueprint, v3_approved])
        get_project.return_value = self.project
        get_client.return_value = db

        overview = get_approved_overview(self.project_id, self.learner_user, self.learner_profile)
        overview_dict = overview.model_dump()

        # Learner projection must NOT include internal competencies, concepts, rubrics, or criteria
        for work_area in overview_dict["work_areas"]:
            self.assertNotIn("competencies", work_area)
            self.assertNotIn("concepts", work_area)
        for assignment in overview_dict["assignments"]:
            self.assertNotIn("rubrics", assignment)
            self.assertNotIn("evaluation_criteria", assignment)

    # Test 8: Approved V2 remains immutable
    @patch("app.services.blueprint_service.get_supabase_client")
    @patch("app.services.blueprint_service._get_project")
    def test_8_approved_v2_remains_immutable(self, get_project, get_client):
        db = self.client()
        get_project.return_value = self.project
        get_client.return_value = db

        v3_content = ProjectBlueprint.model_validate(sample_v3_three_work_areas_json())
        with self.assertRaises(HTTPException) as error:
            update_blueprint_draft(
                self.project_id,
                UUID(self.v2_blueprint_id),
                BlueprintUpdateRequest(blueprint_json=v3_content),
                self.business_user,
                self.business_profile,
            )
        self.assertEqual(error.exception.status_code, 409)
        self.assertIn("Approved versions are immutable", error.exception.detail)

    # Test 9: Materialization is not automatically triggered by revision
    @patch("app.services.blueprint_service.get_supabase_client")
    @patch("app.services.blueprint_service._get_project")
    def test_9_materialization_not_triggered_by_revision(self, get_project, get_client):
        db = self.client()
        get_project.return_value = self.project
        get_client.return_value = db

        revise_blueprint(self.project_id, self.business_user, self.business_profile)

        # No RPC or runtime tables (modules, tasks) modified
        self.assertFalse(any(op[0] == "rpc" for op in db.operations))
        self.assertFalse(any(op[1] in {"modules", "tasks", "competencies", "concepts", "rubrics"} for op in db.operations))

    # Test 10: Publishing is not automatically triggered
    @patch("app.services.blueprint_service.get_supabase_client")
    @patch("app.services.blueprint_service._get_project")
    def test_10_publishing_not_automatically_triggered(self, get_project, get_client):
        draft_project = dict(self.project)
        draft_project["status"] = "draft"
        db = FakeSupabaseClient({
            "projects": [draft_project],
            "project_blueprints": [dict(self.v2_blueprint)],
            "datasets": [dict(self.dataset)],
        })
        get_project.return_value = draft_project
        get_client.return_value = db

        revise_blueprint(self.project_id, self.business_user, self.business_profile)

        # Project status must remain 'draft', not automatically published
        self.assertEqual(db.records["projects"][0]["status"], "draft")
        self.assertFalse(any(op[1] == "projects" and op[0] == "update" for op in db.operations))

    # Test 11: Zero Gemini / LLM calls occur
    @patch("app.services.blueprint_service.get_llm_provider")
    @patch("app.services.blueprint_service.get_supabase_client")
    @patch("app.services.blueprint_service._get_project")
    def test_11_zero_llm_calls_during_revision(self, get_project, get_client, get_llm):
        db = self.client()
        get_project.return_value = self.project
        get_client.return_value = db

        # 1. Create revision
        revised = revise_blueprint(self.project_id, self.business_user, self.business_profile)

        # 2. Update draft
        v3_content = ProjectBlueprint.model_validate(sample_v3_three_work_areas_json())
        update_blueprint_draft(
            self.project_id,
            revised.id,
            BlueprintUpdateRequest(blueprint_json=v3_content),
            self.business_user,
            self.business_profile,
        )

        # LLM provider must NEVER be called
        get_llm.assert_not_called()


if __name__ == "__main__":
    unittest.main()
