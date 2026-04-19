import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import backend.database as database
from backend.deps import get_current_user
from backend.main import app


class ProjectSchemaMigrationTests(unittest.TestCase):
    def test_project_migration_adds_required_columns(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            db_path = Path(temp_dir) / "legacy.db"
            with sqlite3.connect(str(db_path)) as conn:
                conn.executescript(
                    """
                    CREATE TABLE users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        email TEXT NOT NULL UNIQUE,
                        full_name TEXT NOT NULL DEFAULT '',
                        password_hash TEXT NOT NULL,
                        created_at TEXT NOT NULL DEFAULT (datetime('now')),
                        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
                    );
                    CREATE TABLE projects (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        owner_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                        title TEXT NOT NULL,
                        rfp_id TEXT NOT NULL DEFAULT '',
                        issuer TEXT NOT NULL DEFAULT '',
                        status TEXT NOT NULL DEFAULT 'draft',
                        deadline TEXT NOT NULL DEFAULT '',
                        rfp_filename TEXT NOT NULL DEFAULT '',
                        response_filename TEXT NOT NULL DEFAULT '',
                        parsed_rfp_json TEXT,
                        created_at TEXT NOT NULL DEFAULT (datetime('now')),
                        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
                    );
                    CREATE TABLE analysis_jobs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        job_id TEXT NOT NULL UNIQUE,
                        project_id INTEGER NOT NULL,
                        status TEXT NOT NULL DEFAULT 'queued',
                        financial_scenario TEXT NOT NULL DEFAULT 'expected',
                        error_message TEXT,
                        created_at TEXT NOT NULL DEFAULT (datetime('now')),
                        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
                    );
                    """
                )

            with patch.object(database, "DB_PATH", db_path):
                database.init_db()
                with sqlite3.connect(str(db_path)) as conn:
                    columns = {
                        row[1]: {"notnull": row[3], "default": row[4]}
                        for row in conn.execute("PRAGMA table_info(projects)").fetchall()
                    }

            self.assertIn("company_knowledge_data", columns)
            self.assertEqual(columns["company_knowledge_data"]["notnull"], 1)
            self.assertIn("response_rfp", columns)
            self.assertEqual(columns["response_rfp"]["notnull"], 1)


class ProjectCreationRequirementTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = Path(self.temp_dir.name) / "bidintel.db"
        self.db_patch = patch.object(database, "DB_PATH", self.db_path)
        self.db_patch.start()
        database.init_db()
        conn = database.get_db()
        try:
            conn.execute(
                "INSERT INTO users (id, email, full_name, password_hash, token_version) VALUES (?,?,?,?,?)",
                (1, "tester@example.com", "Test User", "hash", 0),
            )
            conn.commit()
        finally:
            conn.close()
        app.dependency_overrides[get_current_user] = lambda: {
            "id": 1,
            "email": "tester@example.com",
            "full_name": "Test User",
            "token_version": 0,
        }
        self.client_ctx = TestClient(app)
        self.client = self.client_ctx.__enter__()

    def tearDown(self):
        self.client_ctx.__exit__(None, None, None)
        app.dependency_overrides.clear()
        self.db_patch.stop()
        try:
            self.temp_dir.cleanup()
        except PermissionError:
            pass

    def test_create_project_without_company_knowledge_returns_400(self):
        response = self.client.post(
            "/api/projects",
            data={
                "title": "Transit Bid",
                "response_rfp": "Bid response draft",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("company_knowledge_data", response.json()["detail"])

    def test_create_project_without_response_rfp_returns_400(self):
        response = self.client.post(
            "/api/projects",
            data={
                "title": "Transit Bid",
                "company_knowledge_data": "Past wins and certifications",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("response_rfp", response.json()["detail"])

    def test_create_project_with_required_fields_returns_201(self):
        response = self.client.post(
            "/api/projects",
            data={
                "title": "Transit Bid",
                "issuer": "City Transit Authority",
                "company_knowledge_data": "Past wins and certifications",
                "response_rfp": "Detailed response narrative",
            },
        )

        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertEqual(body["company_knowledge_data"], "Past wins and certifications")
        self.assertEqual(body["response_rfp"], "Detailed response narrative")

        conn = database.get_db()
        try:
            project = conn.execute(
                "SELECT company_knowledge_data, response_rfp FROM projects WHERE id=?",
                (body["id"],),
            ).fetchone()
        finally:
            conn.close()

        self.assertEqual(project["company_knowledge_data"], "Past wins and certifications")
        self.assertEqual(project["response_rfp"], "Detailed response narrative")


if __name__ == "__main__":
    unittest.main()
