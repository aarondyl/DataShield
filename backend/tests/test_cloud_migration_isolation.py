"""Cloud 迁移谱系不得创建 Local/Web 私有表。"""
import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy import create_engine, inspect


BACKEND = Path(__file__).resolve().parents[1]
PRIVATE_TABLES = {"companies", "products", "product_twin_versions", "findings", "remediations", "feedback", "tenant_agent_runs"}
CLOUD_TABLES = {"regulations", "regulation_versions", "legal_units", "requirements", "legal_chunks", "regulation_events", "regulatory_sources"}


def test_cloud_alembic_chain_excludes_private_tables(tmp_path):
    path = tmp_path / "cloud.db"
    env = {**os.environ, "DATABASE_URL": f"sqlite:///{path}", "RUNTIME_MODE": "cloud"}
    subprocess.run([sys.executable, "-m", "alembic", "-c", "alembic-cloud.ini", "upgrade", "head"], cwd=BACKEND, env=env, check=True)
    tables = set(inspect(create_engine(f"sqlite:///{path}")).get_table_names())
    assert CLOUD_TABLES <= tables
    assert not PRIVATE_TABLES & tables
