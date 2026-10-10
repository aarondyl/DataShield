import gzip
import importlib.util
from pathlib import Path
import stat

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "deploy/verify-cloud-migrations.py"
SPEC = importlib.util.spec_from_file_location("datashield_migration_rehearsal", SCRIPT)
rehearsal = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(rehearsal)


def protected_file(path: Path, content: str | bytes) -> Path:
    if isinstance(content, bytes):
        path.write_bytes(content)
    else:
        path.write_text(content, encoding="utf-8")
    path.chmod(0o600)
    return path


def test_rewrite_database_url_preserves_percent_encoded_credentials():
    source = "postgresql+psycopg://role:p%40ss%25word@production.example:5432/cloud?sslmode=require"

    rewritten = rehearsal.rewrite_database_url_for_clone(source, 49152)

    assert rewritten == "postgresql+psycopg://role:p%40ss%25word@127.0.0.1:49152/cloud?sslmode=disable"


def test_rewrite_database_url_overrides_remote_host_query_options():
    source = "postgresql://role:secret@db.example:5432/cloud?host=private-db&port=5432&sslmode=verify-full&application_name=datashield"

    rewritten = rehearsal.rewrite_database_url_for_clone(source, 49152)

    assert rewritten == "postgresql://role:secret@127.0.0.1:49152/cloud?application_name=datashield&sslmode=disable"


def test_rewrite_database_url_rejects_non_postgres_scheme():
    with pytest.raises(rehearsal.RehearsalError, match="PostgreSQL"):
        rehearsal.rewrite_database_url_for_clone("https://user:secret@example/db", 5432)


def test_rehearsal_refuses_remote_docker_context_before_mutation(tmp_path, monkeypatch):
    backup = protected_file(tmp_path / "backup.sql.gz", gzip.compress(b"SELECT 1;\n"))
    cloud_url = protected_file(tmp_path / "cloud-url", "postgresql+psycopg://cloud:secret%40word@db.example:5432/cloud")
    identity_url = protected_file(tmp_path / "identity-url", "postgresql+psycopg://identity:secret%25word@db.example:5432/identity")
    calls = []

    def fake_docker(*args, **kwargs):
        calls.append(args)
        if args[:2] == ("context", "inspect"):
            return type("Result", (), {"returncode": 0, "stdout": b"ssh://production-host"})()
        raise AssertionError("remote Docker must be refused before creating resources")

    monkeypatch.setattr(rehearsal, "_docker", fake_docker)

    with pytest.raises(rehearsal.RehearsalError, match="not a local Unix socket") as error:
        rehearsal.rehearse(backup, cloud_url, identity_url)

    assert "secret" not in str(error.value)
    assert calls == [("context", "inspect", "default", "--format", '{{(index .Endpoints "docker").Host}}')]


def test_rehearsal_rejects_group_readable_production_backup(tmp_path):
    backup = protected_file(tmp_path / "backup.sql.gz", gzip.compress(b"SELECT 1;\n"))
    cloud_url = protected_file(tmp_path / "cloud-url", "postgresql://cloud:secret@localhost/cloud")
    identity_url = protected_file(tmp_path / "identity-url", "postgresql://identity:secret@localhost/identity")
    backup.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP)

    with pytest.raises(rehearsal.RehearsalError, match="group or others"):
        rehearsal.rehearse(backup, cloud_url, identity_url)
