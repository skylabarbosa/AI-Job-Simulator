import unittest
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from fastapi import HTTPException

from app.services.sql_execution_service import execute_task_sql


class FakeQuery:
    def __init__(self, client):
        self.client = client
        self.data = list(client.datasets)

    def select(self, *_):
        return self

    def eq(self, field, value):
        self.data = [row for row in self.data if str(row.get(field)) == str(value)]
        return self

    def execute(self):
        return SimpleNamespace(data=self.data)


class FakeStorage:
    def __init__(self, client):
        self.client = client

    def from_(self, _bucket):
        return self

    def download(self, path):
        return self.client.files[path]


class FakeClient:
    def __init__(self, datasets, files):
        self.datasets = datasets
        self.files = files
        self.storage = FakeStorage(self)

    def table(self, table_name):
        if table_name != "datasets":
            raise AssertionError(f"Unexpected table access: {table_name}")
        return FakeQuery(self)


class TestSqlExecution(unittest.TestCase):
    def setUp(self):
        self.project_id = str(uuid4())
        self.dataset = {
            "id": str(uuid4()),
            "project_id": self.project_id,
            "file_name": "employees.csv",
            "storage_path": "project/employees.csv",
            "schema_metadata": {"table_name": "employees", "columns": []},
            "status": "ready",
        }
        self.client = FakeClient(
            [self.dataset],
            {"project/employees.csv": b"department,salary\nSales,10\nOps,20\n"},
        )
        self.task = {"reference_solution": {"sql_tables": ["employees"]}}

    def _run(self, query, task=None):
        with patch("app.services.sql_execution_service.get_supabase_client", return_value=self.client):
            return execute_task_sql(project_id=self.project_id, task=task or self.task, query=query)

    def test_select_returns_columns_and_rows(self):
        result = self._run("SELECT department, salary FROM employees ORDER BY salary")
        self.assertEqual(result["columns"], ["department", "salary"])
        self.assertEqual(result["rows"], [["Sales", "10"], ["Ops", "20"]])
        self.assertEqual(result["row_count"], 2)

    def test_empty_result_is_successful(self):
        result = self._run("SELECT * FROM employees WHERE salary = '999'")
        self.assertEqual(result["execution_status"], "success")
        self.assertEqual(result["rows"], [])

    def test_missing_table_is_safe_error(self):
        with self.assertRaises(HTTPException) as error:
            self._run("SELECT * FROM missing_table")
        self.assertEqual(error.exception.status_code, 422)

    def test_mutations_pragma_and_multiple_statements_are_rejected(self):
        for query in ("INSERT INTO employees VALUES ('X', 1)", "UPDATE employees SET salary = 1", "DELETE FROM employees", "DROP TABLE employees", "PRAGMA table_info(employees)", "SELECT 1; SELECT 2"):
            with self.subTest(query=query), self.assertRaises(HTTPException) as error:
                self._run(query)
            self.assertEqual(error.exception.status_code, 422)

    def test_only_task_declared_project_table_is_loaded(self):
        other_project = str(uuid4())
        other = {**self.dataset, "project_id": other_project, "storage_path": "other/employees.csv"}
        client = FakeClient([self.dataset, other], {"project/employees.csv": b"department,salary\nSales,10\n", "other/employees.csv": b"department,salary\nSecret,999\n"})
        with patch("app.services.sql_execution_service.get_supabase_client", return_value=client):
            result = execute_task_sql(project_id=self.project_id, task=self.task, query="SELECT * FROM employees")
        self.assertEqual(result["rows"], [["Sales", "10"]])

    def test_result_rows_are_capped_and_marked_truncated(self):
        content = b"value\n" + b"\n".join(str(index).encode() for index in range(150)) + b"\n"
        dataset = {**self.dataset, "storage_path": "project/many.csv", "file_name": "many.csv", "schema_metadata": {"table_name": "many", "columns": []}}
        client = FakeClient([dataset], {"project/many.csv": content})
        with patch("app.services.sql_execution_service.get_supabase_client", return_value=client):
            result = execute_task_sql(project_id=self.project_id, task={"reference_solution": {"sql_tables": ["many"]}}, query="SELECT * FROM many")
        self.assertEqual(result["displayed_row_count"], 100)
        self.assertTrue(result["truncated"])


if __name__ == "__main__":
    unittest.main()