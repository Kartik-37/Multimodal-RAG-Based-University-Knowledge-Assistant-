"""
Integration tests for PostgreSQL and pgvector database foundation.

Verifies:
1. Database connectivity using real PostgreSQL test database.
2. PostgreSQL server version (PostgreSQL 16+).
3. pgvector extension installation and version (0.8.6).
4. SQLAlchemy engine and session operations.
5. Transaction rollback integrity.
6. Transaction commit integrity.
7. Alembic migration compatibility.
8. Application readiness probe behavior under database availability and failure.
9. Vector operations with 1024 dimensions (matching qwen3-embedding:0.6b).
"""

from unittest.mock import patch

from alembic.config import Config
from fastapi import status
from fastapi.testclient import TestClient
from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, Engine, Integer, String, text
from sqlalchemy.orm import Session

from alembic import command
from backend.app.core.config import Settings
from backend.app.db.base import Base
from backend.app.main import create_application


class VectorTestTable(Base):
    """Temporary test table for verifying vector(1024) schema integration."""

    __tablename__ = "itest_vector_dim_check"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True)
    label = Column(String(50), nullable=False)
    embedding = Column(Vector(1024), nullable=False)


def test_postgres_connection_and_version(db_session: Session) -> None:
    """1 & 2: Verify database connection and PostgreSQL 16+ version."""
    row = db_session.execute(text("SELECT version();")).fetchone()
    assert row is not None
    version_str = row[0]
    assert "PostgreSQL 16" in version_str, f"Expected PostgreSQL 16, got: {version_str}"


def test_pgvector_extension_availability(db_session: Session) -> None:
    """3: Verify pgvector extension is installed and active in PostgreSQL."""
    row = db_session.execute(
        text("SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';")
    ).fetchone()
    assert row is not None, "pgvector extension is not installed in database"
    extname, extversion = row
    assert extname == "vector"
    assert extversion.startswith("0.8"), f"Expected pgvector 0.8.x, got: {extversion}"


def test_sqlalchemy_session_operations(db_session: Session) -> None:
    """4: Verify basic query and session execution through SQLAlchemy."""
    result = db_session.execute(text("SELECT 42 AS answer;")).scalar_one()
    assert result == 42


def test_transaction_rollback(db_engine: Engine) -> None:
    """5: Verify transaction rollback discards uncommitted mutations."""
    with db_engine.begin() as conn:
        conn.execute(text("CREATE TABLE IF NOT EXISTS itest_txn_rb (id int PRIMARY KEY);"))
        conn.execute(text("DELETE FROM itest_txn_rb;"))

    try:
        with db_engine.connect() as conn:
            trans = conn.begin()
            conn.execute(text("INSERT INTO itest_txn_rb (id) VALUES (100);"))
            trans.rollback()

        with db_engine.connect() as conn:
            count = conn.execute(
                text("SELECT COUNT(*) FROM itest_txn_rb WHERE id = 100;")
            ).scalar_one()
            assert count == 0
    finally:
        with db_engine.begin() as conn:
            conn.execute(text("DROP TABLE IF EXISTS itest_txn_rb;"))


def test_transaction_commit(db_engine: Engine) -> None:
    """6: Verify transaction commit persists mutations across sessions."""
    with db_engine.begin() as conn:
        conn.execute(text("CREATE TABLE IF NOT EXISTS itest_txn_cm (id int PRIMARY KEY);"))
        conn.execute(text("DELETE FROM itest_txn_cm;"))

    try:
        with db_engine.connect() as conn:
            trans = conn.begin()
            conn.execute(text("INSERT INTO itest_txn_cm (id) VALUES (200);"))
            trans.commit()

        with db_engine.connect() as conn:
            count = conn.execute(
                text("SELECT COUNT(*) FROM itest_txn_cm WHERE id = 200;")
            ).scalar_one()
            assert count == 1
    finally:
        with db_engine.begin() as conn:
            conn.execute(text("DROP TABLE IF EXISTS itest_txn_cm;"))


def test_alembic_migration(app_settings: Settings) -> None:
    """7: Verify Alembic migration can execute against the test database."""
    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", app_settings.TEST_DATABASE_URL)

    # Run upgrade head on test database
    command.upgrade(alembic_cfg, "head")

    # Verify migration stamped current revision
    from alembic.migration import MigrationContext
    from alembic.script import ScriptDirectory

    from backend.app.db.session import create_db_engine

    engine = create_db_engine(app_settings.TEST_DATABASE_URL)
    with engine.connect() as conn:
        context = MigrationContext.configure(conn)
        current_rev = context.get_current_revision()
        script = ScriptDirectory.from_config(alembic_cfg)
        head_rev = script.get_current_head()
        assert current_rev == head_rev
    engine.dispose()


def test_readiness_probe_database_available(client: TestClient) -> None:
    """8a: Verify /ready returns 200 when database is healthy and reachable."""
    response = client.get("/ready")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["status"] == "ready"
    assert data["checks"]["database"] == "ok"
    assert "password" not in response.text
    assert "postgresql" not in response.text.lower()


def test_readiness_probe_database_unavailable() -> None:
    """8b: Verify /ready returns 503 when database is unreachable without exposing secrets."""
    with patch("backend.app.main.check_database_connection", return_value=False):
        app = create_application()
        with TestClient(app) as test_client:
            # Liveness remains healthy even if DB is down
            health_res = test_client.get("/health")
            assert health_res.status_code == status.HTTP_200_OK
            assert health_res.json()["status"] == "healthy"

            # Readiness probe fails with 503 Service Unavailable
            ready_res = test_client.get("/ready")
            assert ready_res.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
            data = ready_res.json()
            assert data["status"] == "not_ready"
            assert data["checks"]["database"] == "unavailable"
            # Ensure no internal error strings or passwords leak
            assert "password" not in ready_res.text
            assert "traceback" not in ready_res.text.lower()


def test_vector_1024_operations(db_engine: Engine) -> None:
    """9: Verify Vector(1024) schema creation, insertion, and L2 distance search."""
    VectorTestTable.__table__.drop(db_engine, checkfirst=True)
    VectorTestTable.__table__.create(db_engine, checkfirst=True)

    try:
        with Session(db_engine) as session:
            vec_a = [0.1] * 1024
            vec_b = [0.9] * 1024

            obj_a = VectorTestTable(id=1, label="alpha", embedding=vec_a)
            obj_b = VectorTestTable(id=2, label="beta", embedding=vec_b)
            session.add_all([obj_a, obj_b])
            session.commit()

            # Query vector dimension
            dim = session.execute(
                text("SELECT vector_dims(embedding) FROM itest_vector_dim_check WHERE id = 1;")
            ).scalar_one()
            assert dim == 1024

            # Perform L2 distance ordering
            query_vec = str([0.1] * 1024)
            closest = session.execute(
                text(
                    "SELECT id, label FROM itest_vector_dim_check "
                    "ORDER BY embedding <-> :q LIMIT 1;"
                ),
                {"q": query_vec},
            ).fetchone()
            assert closest is not None
            assert closest[0] == 1
            assert closest[1] == "alpha"
    finally:
        VectorTestTable.__table__.drop(db_engine, checkfirst=True)
