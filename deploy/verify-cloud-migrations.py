#!/usr/bin/env python3
"""Replay a protected pg_dumpall backup and test both migrations on local Docker only."""

from __future__ import annotations

import argparse
import gzip
import os
from pathlib import Path
import re
import secrets
import shutil
import stat
import subprocess
import sys
import tempfile
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


BACKEND = Path(__file__).resolve().parents[1] / "backend"


class RehearsalError(RuntimeError):
    pass


def _docker_environment() -> dict[str, str]:
    env = os.environ.copy()
    env.pop("DOCKER_HOST", None)
    env.pop("DOCKER_CONTEXT", None)
    return env


def _docker(*args: str, check: bool = True, **kwargs) -> subprocess.CompletedProcess:
    result = subprocess.run(
        ["docker", "--context", "default", *args],
        env=_docker_environment(),
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
        **kwargs,
    )
    if check and result.returncode:
        raise RehearsalError("local Docker operation failed; command output was suppressed")
    return result


def rewrite_database_url_for_clone(database_url: str, port: int) -> str:
    """Preserve encoded credentials/database while forcing the local clone endpoint."""
    parts = urlsplit(database_url.strip())
    if parts.scheme not in {"postgresql", "postgresql+psycopg", "postgres"}:
        raise RehearsalError("database URL must use a PostgreSQL driver")
    if not parts.netloc or "@" not in parts.netloc or not parts.path.strip("/"):
        raise RehearsalError("database URL must include a role and database")
    userinfo = parts.netloc.rsplit("@", 1)[0]
    query = [(key, value) for key, value in parse_qsl(parts.query, keep_blank_values=True)
             if key.lower() not in {"host", "hostaddr", "port", "sslmode"}]
    query.append(("sslmode", "disable"))
    return urlunsplit((parts.scheme, f"{userinfo}@127.0.0.1:{port}", parts.path, urlencode(query), ""))


def _read_protected_file(path: Path, label: str) -> str:
    if path.is_symlink() or not path.is_file():
        raise RehearsalError(f"{label} must be a regular non-symlink file")
    if stat.S_IMODE(path.stat().st_mode) & 0o077:
        raise RehearsalError(f"{label} must not be readable by group or others")
    value = path.read_text(encoding="utf-8").strip()
    if not value:
        raise RehearsalError(f"{label} is empty")
    return value


def _run_migration(config: str, url_file: Path, env: dict[str, str]) -> None:
    migration_env = env.copy()
    if config == "cloud":
        migration_env.update(RUNTIME_MODE="cloud", DATABASE_URL_FILE=str(url_file))
        args = [sys.executable, "-m", "alembic", "-c", "alembic-cloud.ini", "upgrade", "head"]
    else:
        migration_env["IDENTITY_DATABASE_URL_FILE"] = str(url_file)
        args = [sys.executable, "-m", "alembic", "-c", "alembic-identity.ini", "upgrade", "head"]
    result = subprocess.run(args, cwd=BACKEND, env=migration_env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if result.returncode:
        raise RehearsalError(f"{config.title()} migration failed on the local backup clone; details suppressed")


def rehearse(backup: Path, cloud_url_file: Path, identity_url_file: Path) -> None:
    backup = Path(os.path.abspath(backup))
    if not backup.exists():
        raise RehearsalError("backup does not exist")
    if backup.is_symlink() or not backup.is_file():
        raise RehearsalError("backup must be a regular file")
    if stat.S_IMODE(backup.stat().st_mode) & 0o077:
        raise RehearsalError("backup must not be readable by group or others")
    cloud_url = _read_protected_file(cloud_url_file, "Cloud URL file")
    identity_url = _read_protected_file(identity_url_file, "Identity URL file")

    try:
        with gzip.open(backup, "rb") as stream:
            stream.read(1)
    except (OSError, EOFError):
        raise RehearsalError("backup is not a readable gzip archive") from None

    context = _docker("context", "inspect", "default", "--format", "{{(index .Endpoints \"docker\").Host}}", check=False)
    endpoint = context.stdout.decode("utf-8", "replace").strip()
    if context.returncode or not endpoint.startswith("unix://"):
        raise RehearsalError("refusing migration rehearsal: Docker default context is not a local Unix socket")

    suffix = secrets.token_hex(6)
    container = f"datashield-migration-rehearsal-{suffix}"
    network = f"datashield-migration-rehearsal-{suffix}"
    restore_user = f"ds_restore_{suffix}"
    restore_db = f"ds_restore_{suffix}"
    restore_password = secrets.token_urlsafe(32)
    temp_path: Path | None = None
    network_created = False
    container_started = False
    try:
        temp_path = Path(tempfile.mkdtemp(prefix="datashield-migration-rehearsal-"))
        temp_path.chmod(0o700)
        _docker("network", "create", "--internal", network)
        network_created = True
        _docker(
            "run", "--detach", "--rm", "--name", container,
            "--network", network,
            "--publish", "127.0.0.1::5432",
            "--env", f"POSTGRES_USER={restore_user}",
            "--env", f"POSTGRES_PASSWORD={restore_password}",
            "--env", f"POSTGRES_DB={restore_db}",
            "pgvector/pgvector:pg16",
        )
        container_started = True

        port_result = _docker("port", container, "5432/tcp")
        match = re.fullmatch(r"127\.0\.0\.1:(\d+)\s*", port_result.stdout.decode("utf-8", "replace"))
        if not match:
            raise RehearsalError("temporary PostgreSQL did not bind to loopback")
        port = int(match.group(1))
        for _ in range(60):
            ready = _docker("exec", container, "pg_isready", "-U", restore_user, "-d", restore_db, check=False)
            if ready.returncode == 0:
                break
            import time
            time.sleep(1)
        else:
            raise RehearsalError("temporary PostgreSQL did not become ready")

        restore_errors = temp_path / "restore-errors.log"
        with restore_errors.open("wb") as error_stream:
            psql = subprocess.Popen(
                ["docker", "--context", "default", "exec", "-i", "--env", f"PGPASSWORD={restore_password}", container,
                 "psql", "--no-psqlrc", "-U", restore_user, "-d", restore_db],
                env=_docker_environment(), stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                stderr=error_stream,
            )
            assert psql.stdin is not None
            try:
                with gzip.open(backup, "rb") as source:
                    shutil.copyfileobj(source, psql.stdin)
            finally:
                psql.stdin.close()
            restore_status = psql.wait()
        errors = restore_errors.read_text(encoding="utf-8", errors="replace").splitlines()
        # A pg_dumpall replay necessarily collides with the temporary cluster's
        # built-in postgres role/database. psql continues after those two known
        # errors; every other restore error invalidates the rehearsal.
        unexpected_errors = [
            line for line in errors
            if "ERROR:" in line
            and not re.search(r'ERROR:  role "postgres" already exists$', line)
            and not re.search(r'ERROR:  database "postgres" already exists$', line)
        ]
        if restore_status != 0 or unexpected_errors:
            raise RehearsalError("backup restore failed on the isolated local clone; details suppressed")

        cloud_clone_url = rewrite_database_url_for_clone(cloud_url, port)
        identity_clone_url = rewrite_database_url_for_clone(identity_url, port)
        from urllib.parse import unquote, urlsplit as split_url

        if split_url(cloud_clone_url).path == split_url(identity_clone_url).path:
            raise RehearsalError("Cloud and Identity URLs must target distinct databases")
        if unquote(split_url(cloud_clone_url).username or "") == unquote(split_url(identity_clone_url).username or ""):
            raise RehearsalError("Cloud and Identity URLs must use distinct database roles")

        cloud_file = temp_path / "cloud-url"
        identity_file = temp_path / "identity-url"
        cloud_file.write_text(cloud_clone_url, encoding="utf-8")
        identity_file.write_text(identity_clone_url, encoding="utf-8")
        cloud_file.chmod(0o600)
        identity_file.chmod(0o600)
        _run_migration("cloud", cloud_file, env)
        _run_migration("identity", identity_file, env)
        print("Cloud and Identity Alembic migrations passed against the local restored backup clone.")
    finally:
        if container_started:
            _docker("rm", "--force", container, check=False)
        if network_created:
            _docker("network", "rm", network, check=False)
        if temp_path:
            shutil.rmtree(temp_path, ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backup", type=Path, required=True, help="mode-0600 pg_dumpall .sql.gz backup copy")
    parser.add_argument("--cloud-url-file", type=Path, required=True, help="mode-0600 Cloud DB URL secret file")
    parser.add_argument("--identity-url-file", type=Path, required=True, help="mode-0600 Identity DB URL secret file")
    args = parser.parse_args()
    try:
        rehearse(args.backup, args.cloud_url_file, args.identity_url_file)
    except (OSError, RehearsalError) as exc:
        print(f"Migration rehearsal refused or failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
