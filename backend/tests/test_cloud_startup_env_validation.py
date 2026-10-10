import subprocess
import sys
from pathlib import Path


MODULE = "app.entrypoints.validate_cloud_env"


def test_cloud_validator_lists_missing_variable_names_without_values(tmp_path: Path) -> None:
    env = {
        "PYTHONPATH": str(Path(__file__).resolve().parents[1]),
        "RUNTIME_MODE": "cloud",
        "RUN_SEED": "false",
        "DATABASE_URL_FILE": str(tmp_path / "db-url"),
        "CLOUD_ADMIN_TOKEN_FILE": str(tmp_path / "admin-token"),
    }
    (tmp_path / "db-url").write_text("postgresql+psycopg://private-user:db-secret@db/cloud", encoding="utf-8")
    (tmp_path / "admin-token").write_text("highly-private-admin-token", encoding="utf-8")

    result = subprocess.run([sys.executable, "-m", MODULE], env=env, text=True, capture_output=True)
    assert result.returncode == 0
    assert "db-secret" not in result.stdout + result.stderr
    assert "highly-private-admin-token" not in result.stdout + result.stderr


def test_cloud_validator_reports_missing_secret_variable_not_contents(tmp_path: Path) -> None:
    env = {"PYTHONPATH": str(Path(__file__).resolve().parents[1]), "RUNTIME_MODE": "cloud", "RUN_SEED": "false"}
    result = subprocess.run([sys.executable, "-m", MODULE], env=env, text=True, capture_output=True)

    assert result.returncode == 1
    assert "DATABASE_URL_FILE" in result.stderr
    assert "CLOUD_ADMIN_TOKEN_FILE" in result.stderr
    assert "secret" not in result.stderr.lower()


def test_cloud_validator_rejects_non_postgres_database_without_echoing_url(tmp_path: Path) -> None:
    db_file = tmp_path / "db-url"
    db_file.write_text("sqlite:///sensitive-local.db", encoding="utf-8")
    token_file = tmp_path / "token"
    token_file.write_text("private-token", encoding="utf-8")
    env = {
        "PYTHONPATH": str(Path(__file__).resolve().parents[1]), "RUNTIME_MODE": "cloud", "RUN_SEED": "false",
        "DATABASE_URL_FILE": str(db_file), "CLOUD_ADMIN_TOKEN_FILE": str(token_file),
    }
    result = subprocess.run([sys.executable, "-m", MODULE], env=env, text=True, capture_output=True)

    assert result.returncode == 1
    assert "DATABASE_URL_FILE" in result.stderr
    assert "sensitive-local.db" not in result.stderr
    assert "private-token" not in result.stderr
