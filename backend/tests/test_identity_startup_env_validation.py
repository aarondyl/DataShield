import subprocess
import sys
from pathlib import Path


MODULE = "identity_service.validate_env"


def test_identity_validator_accepts_ready_secret_files_and_never_prints_values(tmp_path: Path) -> None:
    values = {
        "IDENTITY_DATABASE_URL_FILE": ("postgresql+psycopg://identity:db-secret@db/identity", "db-url"),
        "IDENTITY_SMTP_PASSWORD_FILE": ("smtp-private-password", "smtp-password"),
        "IDENTITY_LLM_API_KEY_FILE": ("deepseek-private-api-key", "llm-key"),
    }
    env = {
        "PYTHONPATH": str(Path(__file__).resolve().parents[1]),
        "IDENTITY_SMTP_HOST": "smtp.example.test",
        "IDENTITY_SMTP_PORT": "587",
        "IDENTITY_SMTP_USER": "sender@example.test",
        "IDENTITY_EMAIL_FROM": "DataShield <sender@example.test>",
        "IDENTITY_EMAIL_VERIFY_REQUIRED": "true",
        "IDENTITY_SMTP_STARTTLS": "true",
        "IDENTITY_LLM_MODEL": "deepseek-flash",
    }
    for variable, (contents, file_name) in values.items():
        path = tmp_path / file_name
        path.write_text(contents, encoding="utf-8")
        env[variable] = str(path)

    result = subprocess.run([sys.executable, "-m", MODULE], env=env, text=True, capture_output=True)
    assert result.returncode == 0
    combined = result.stdout + result.stderr
    assert "db-secret" not in combined
    assert "smtp-private-password" not in combined
    assert "deepseek-private-api-key" not in combined


def test_identity_validator_names_missing_configuration_without_leaking_secrets(tmp_path: Path) -> None:
    env = {"PYTHONPATH": str(Path(__file__).resolve().parents[1])}
    result = subprocess.run([sys.executable, "-m", MODULE], env=env, text=True, capture_output=True)

    assert result.returncode == 1
    assert "IDENTITY_DATABASE_URL_FILE" in result.stderr
    assert "IDENTITY_SMTP_HOST" in result.stderr
    assert "IDENTITY_LLM_API_KEY_FILE" in result.stderr


def test_identity_validator_rejects_sqlite_database_without_echoing_connection_string(tmp_path: Path) -> None:
    path = tmp_path / "database-url"
    path.write_text("sqlite:///private-test-data.db", encoding="utf-8")
    env = {
        "PYTHONPATH": str(Path(__file__).resolve().parents[1]),
        "IDENTITY_DATABASE_URL_FILE": str(path),
        "IDENTITY_SMTP_HOST": "smtp.example.test",
        "IDENTITY_SMTP_PORT": "587",
        "IDENTITY_SMTP_USER": "sender@example.test",
        "IDENTITY_EMAIL_FROM": "sender@example.test",
        "IDENTITY_EMAIL_VERIFY_REQUIRED": "true",
        "IDENTITY_SMTP_STARTTLS": "true",
        "IDENTITY_LLM_MODEL": "deepseek-flash",
    }
    for variable, value in (("IDENTITY_SMTP_PASSWORD_FILE", "smtp-key"), ("IDENTITY_LLM_API_KEY_FILE", "llm-key")):
        secret = tmp_path / variable.lower()
        secret.write_text(value, encoding="utf-8")
        env[variable] = str(secret)

    result = subprocess.run([sys.executable, "-m", MODULE], env=env, text=True, capture_output=True)
    assert result.returncode == 1
    assert "IDENTITY_DATABASE_URL_FILE" in result.stderr
    assert "private-test-data.db" not in result.stderr
