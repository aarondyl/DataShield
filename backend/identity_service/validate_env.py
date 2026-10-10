"""Validate production Identity configuration without exposing secret values."""

import os
from pathlib import Path
import sys


def validate() -> list[str]:
    missing: list[str] = []
    for variable in (
        "IDENTITY_DATABASE_URL_FILE",
        "IDENTITY_SMTP_HOST",
        "IDENTITY_SMTP_PORT",
        "IDENTITY_SMTP_USER",
        "IDENTITY_SMTP_PASSWORD_FILE",
        "IDENTITY_EMAIL_FROM",
        "IDENTITY_SMTP_STARTTLS",
        "IDENTITY_LLM_API_KEY_FILE",
        "IDENTITY_LLM_MODEL",
    ):
        if not os.getenv(variable, "").strip():
            missing.append(variable)

    if os.getenv("IDENTITY_EMAIL_VERIFY_REQUIRED", "").strip().lower() != "true":
        missing.append("IDENTITY_EMAIL_VERIFY_REQUIRED=true")
    if os.getenv("IDENTITY_SMTP_STARTTLS", "").strip().lower() not in {"true", "false"}:
        missing.append("IDENTITY_SMTP_STARTTLS")
    smtp_port = os.getenv("IDENTITY_SMTP_PORT", "")
    if not smtp_port.isdecimal() or not 1 <= int(smtp_port) <= 65535:
        missing.append("IDENTITY_SMTP_PORT")

    for variable in (
        "IDENTITY_DATABASE_URL_FILE",
        "IDENTITY_SMTP_PASSWORD_FILE",
        "IDENTITY_LLM_API_KEY_FILE",
    ):
        path_value = os.getenv(variable, "").strip()
        if not path_value:
            continue
        try:
            contents = Path(path_value).read_text(encoding="utf-8").strip()
        except OSError:
            contents = ""
        if not contents:
            missing.append(variable)
        elif variable == "IDENTITY_DATABASE_URL_FILE" and not contents.startswith(("postgresql://", "postgres://", "postgresql+psycopg://")):
            missing.append(variable)

    return sorted(set(missing))


def main() -> int:
    missing = validate()
    if missing:
        print("Identity startup configuration is missing or invalid: " + ", ".join(missing), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
