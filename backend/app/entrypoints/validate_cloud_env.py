"""Validate production Cloud configuration without ever printing secret values."""

import os
from pathlib import Path
import sys


def validate() -> list[str]:
    missing: list[str] = []
    if os.getenv("RUNTIME_MODE", "").strip() != "cloud":
        missing.append("RUNTIME_MODE=cloud")
    if os.getenv("RUN_SEED", "").strip().lower() != "false":
        missing.append("RUN_SEED=false")

    for variable in ("DATABASE_URL_FILE", "CLOUD_ADMIN_TOKEN_FILE"):
        path_value = os.getenv(variable, "").strip()
        if not path_value:
            missing.append(variable)
            continue
        try:
            contents = Path(path_value).read_text(encoding="utf-8").strip()
        except OSError:
            contents = ""
        if not contents:
            missing.append(variable)
        elif variable == "DATABASE_URL_FILE" and not contents.startswith(("postgresql://", "postgres://", "postgresql+psycopg://")):
            missing.append(variable)

    return sorted(set(missing))


def main() -> int:
    missing = validate()
    if missing:
        print("Cloud startup configuration is missing or invalid: " + ", ".join(missing), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
