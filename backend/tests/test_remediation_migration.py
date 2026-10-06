"""Alembic and cross-dialect checks for Remediation persistence."""

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from app.models import Remediation, RemediationEvidence, RemediationRequirement


BACKEND = Path(__file__).resolve().parents[1]
NEW_TABLES = {"remediations", "remediation_requirements", "remediation_evidence"}


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
        return {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }


def test_sqlite_fresh_upgrade_to_0007_and_downgrade_to_0006(tmp_path):
    db_path = tmp_path / "fresh.db"
    _alembic(db_path, "upgrade", "head")
    assert NEW_TABLES <= _tables(db_path)
    _alembic(db_path, "downgrade", "0006")
    tables = _tables(db_path)
    assert not (NEW_TABLES & tables)
    assert {"findings", "tenant_agent_runs", "product_twin_versions"} <= tables


def test_sqlite_upgrade_from_0006_preserves_existing_data(tmp_path):
    db_path = tmp_path / "upgrade.db"
    _alembic(db_path, "upgrade", "0006")
    with sqlite3.connect(db_path) as connection:
        connection.execute("INSERT INTO companies (id, name) VALUES (100, 'existing tenant')")
        connection.execute(
            "INSERT INTO products (id, company_id, name) VALUES (100, 100, 'existing product')"
        )
        connection.commit()
    _alembic(db_path, "upgrade", "head")
    with sqlite3.connect(db_path) as connection:
        assert connection.execute(
            "SELECT name FROM products WHERE id=100"
        ).fetchone() == ("existing product",)
    assert NEW_TABLES <= _tables(db_path)


def test_remediation_models_compile_for_postgresql():
    dialect = postgresql.dialect()
    for model in (Remediation, RemediationRequirement, RemediationEvidence):
        ddl = str(CreateTable(model.__table__).compile(dialect=dialect))
        assert f"CREATE TABLE {model.__tablename__}" in ddl
        assert "CREATE TYPE" not in ddl
    assert "JSON" in str(CreateTable(Remediation.__table__).compile(dialect=dialect))
