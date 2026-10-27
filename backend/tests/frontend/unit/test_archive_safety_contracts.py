"""Contracts for project ZIP archive security and secret exclusion.

Validates that:
- .env and other secret configuration files (.env, .env.*) are strictly rejected.
- .env.example template is explicitly permitted.
- .git/ version control internals are strictly rejected.
- Virtual environments (.venv/, venv/, env/) are strictly rejected.
- Python caches (__pycache__, *.pyc, *.pyo) and test caches are rejected.
- Private keys, certificates, and credentials (*.pem, *.key, *.pfx) are rejected.
- Transient scratch files, database files, and logs are rejected.
- Legitimate project source files, docs, and assets are permitted.
- Archive validation detects and flags any leaked sensitive entry.
"""

import zipfile
from pathlib import Path

import pytest

from scripts.create_safe_project_zip import (
    is_path_safe_to_archive,
    validate_archive_contents,
)


class TestArchiveSafetyContracts:
    """Validate archive generation filter rules and security invariants."""

    @pytest.mark.parametrize(
        "secret_path",
        [
            ".env",
            ".env.local",
            ".env.production",
            ".env.test",
            "backend/.env",
            "frontend/.env",
            "server.key",
            "private.pem",
            "cert.pfx",
            "database.sqlite3",
            "app.db",
            "vector_index.faiss",
            "app.log",
            "logs/error.log",
            "backup.sql",
            "database_dump.sql",
            "scratch/db_backup/rag_assistant_db_backup_20261014_123058.sql",
        ],
    )
    def test_secrets_and_credentials_strictly_excluded(self, secret_path: str) -> None:
        """Secret files, credentials, and SQL database dumps must never be included in the archive."""
        assert is_path_safe_to_archive(secret_path) is False

    @pytest.mark.parametrize(
        "vcs_or_env_path",
        [
            ".git/HEAD",
            ".git/config",
            ".git/objects/00/1234",
            ".github/workflows/ci.yml",
            ".venv/Scripts/python.exe",
            ".venv/Lib/site-packages/fastapi/__init__.py",
            "venv/bin/activate",
            "env/pyvenv.cfg",
            "__pycache__/api_client.cpython-314.pyc",
            "backend/app/__pycache__/main.cpython-314.pyc",
            ".pytest_cache/v/cache/lastfailed",
            ".ruff_cache/content/12345",
            ".coverage",
            "coverage.xml",
            "htmlcov/index.html",
            "scratch/temp_dump.txt",
            "storage/documents/sample.pdf",
            "storage/uploads/user_doc.docx",
            ".nicegui/storage.json",
            ".tempmediaStorage/sample.png",
            "node_modules/package/index.js",
            ".vscode/settings.json",
            ".idea/workspace.xml",
            "bca_rag_assistant.egg-info/PKG-INFO",
            "bca_rag_assistant.egg-info/SOURCES.txt",
            "screenshot/archive/admin_navigation_part8a_desktop.png",
            "screenshot/test_capture.png",
            "screenshot/inspect_answer.png",
            "~$G_Assistant_Major_Project_Report.docx",
        ],
    )
    def test_vcs_venvs_caches_and_temp_files_excluded(self, vcs_or_env_path: str) -> None:
        """VCS internals, virtual environments, caches, storage, and scratch files are pruned."""
        assert is_path_safe_to_archive(vcs_or_env_path) is False

    @pytest.mark.parametrize(
        "legitimate_path",
        [
            ".env.example",
            "README.md",
            "PROJECT_CONTEXT.md",
            "pyproject.toml",
            "alembic.ini",
            "frontend/main.py",
            "frontend/client/api_client.py",
            "frontend/client/models.py",
            "frontend/pages/knowledge_bases_page.py",
            "frontend/pages/chat_page.py",
            "backend/app/main.py",
            "backend/app/api/v1/router.py",
            "backend/app/models/user.py",
            "context/FRONTEND_DESIGN_SYSTEM.md",
            "context/TASK_STATE.md",
            "scripts/create_safe_project_zip.py",
            "screenshot/admin/final/activity_desktop.png",
            "screenshot/ppt_evidence/unsupported_question_all_courses_live.png",
            "screenshot/chat_concise_grouped_citations.png",
            "static/images/hero.png",
        ],
    )
    def test_legitimate_project_source_files_permitted(self, legitimate_path: str) -> None:
        """Legitimate project source code, context, docs, and assets are safely permitted."""
        assert is_path_safe_to_archive(legitimate_path) is True

    def test_validate_archive_contents_detects_secret_leak(self, tmp_path: Path) -> None:
        """Archive audit flags any sensitive file present in a zip."""
        unsafe_zip = tmp_path / "unsafe.zip"
        with zipfile.ZipFile(unsafe_zip, "w") as zf:
            zf.writestr(".env", "DATABASE_URL=postgresql://secret:pass@localhost/db")
            zf.writestr(".git/HEAD", "ref: refs/heads/main")
            zf.writestr("frontend/main.py", "print('hello')")

        is_safe, violations = validate_archive_contents(unsafe_zip)
        assert is_safe is False
        assert len(violations) == 2
        assert ".env" in violations
        assert ".git/HEAD" in violations

    def test_validate_archive_contents_accepts_clean_archive(self, tmp_path: Path) -> None:
        """Archive audit verifies that a clean archive passes with zero violations."""
        clean_zip = tmp_path / "clean.zip"
        with zipfile.ZipFile(clean_zip, "w") as zf:
            zf.writestr(".env.example", "DATABASE_URL=postgresql://user:pass@localhost/db")
            zf.writestr("frontend/main.py", "print('hello')")
            zf.writestr("pyproject.toml", "[tool.pytest]")

        is_safe, violations = validate_archive_contents(clean_zip)
        assert is_safe is True
        assert len(violations) == 0
