"""Alembic and cross-dialect checks for Tenant Intelligence persistence."""

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from app.models import Finding, FindingEvidence, FindingRequirement, TenantAgentRun, TenantMissingContextItem


BACKEND = Path(__file__).resolve().parents[1]
NEW_TABLES = {
    "tenant_agent_runs", "findings", "finding_requirements",
    "finding_evidence", "tenant_missing_context_items",
}


def _alembic(db_path: Path, *args: str) -> None:
    env = {
        **os.environ,
        "DATABASE_URL": f"sqlite:///{db_path}",
        "PYTHONPATH": str(BACKEND) + os.pathsep + os.environ.get("PYTHONPATH", ""),
    }
    subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=BACKEND,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )


def _tables(db_path: Path) -> set[str]:
    with sqlite3.connect(db_path) as connection:
        return {row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )}


def test_sqlite_fresh_upgrade_and_downgrade_preserves_old_tables(tmp_path):
    db_path = tmp_path / "fresh.db"
    _alembic(db_path, "upgrade", "head")
    assert NEW_TABLES <= _tables(db_path)

    _alembic(db_path, "downgrade", "0005")
    tables = _tables(db_path)
    assert not (NEW_TABLES & tables)
    assert {"products", "requirements", "product_twin_versions"} <= tables


def test_sqlite_upgrade_from_0005_preserves_existing_data(tmp_path):
    db_path = tmp_path / "upgrade.db"
    _alembic(db_path, "upgrade", "0005")
    with sqlite3.connect(db_path) as connection:
        connection.execute("INSERT INTO companies (id, name) VALUES (100, 'existing tenant')")
        connection.execute("INSERT INTO products (id, company_id, name) VALUES (100, 100, 'existing product')")
        connection.commit()

    _alembic(db_path, "upgrade", "head")

    with sqlite3.connect(db_path) as connection:
        assert connection.execute("SELECT name FROM products WHERE id=100").fetchone() == ("existing product",)
    assert NEW_TABLES <= _tables(db_path)


def test_tenant_models_compile_for_postgresql():
    dialect = postgresql.dialect()
    for model in (TenantAgentRun, Finding, FindingRequirement, FindingEvidence, TenantMissingContextItem):
        ddl = str(CreateTable(model.__table__).compile(dialect=dialect))
        assert f"CREATE TABLE {model.__tablename__}" in ddl
    assert "JSON" in str(CreateTable(TenantAgentRun.__table__).compile(dialect=dialect))
