#!/usr/bin/env python3
"""Require expand/contract DB changes before automatic Cloud app rollback is enabled."""

import ast
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
MIGRATION_DIRS = (
    ROOT / "backend" / "alembic_cloud" / "versions",
    ROOT / "backend" / "identity_service" / "migrations" / "versions",
)
DESTRUCTIVE = {
    "drop_column", "drop_table", "drop_index", "drop_constraint", "rename_table",
    "rename", "alter_column",
}


def main() -> int:
    failures: list[str] = []
    for directory in MIGRATION_DIRS:
        for path in sorted(directory.glob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) or node.name != "upgrade":
                    continue
                for operation in ast.walk(node):
                    if not isinstance(operation, ast.Call) or not isinstance(operation.func, ast.Attribute):
                        continue
                    if operation.func.attr in DESTRUCTIVE:
                        relative = path.relative_to(ROOT)
                        failures.append(f"{relative}:{operation.lineno}: op.{operation.func.attr}")
    if failures:
        print("Automatic rollout requires backward-compatible expand/contract migrations:", file=sys.stderr)
        print("\n".join(failures), file=sys.stderr)
        return 1
    print("Cloud and Identity upgrade migrations are additive; app rollback remains compatible.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
