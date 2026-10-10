from pathlib import Path
import hashlib
import os
import subprocess


ROOT = Path(__file__).resolve().parents[2]
TRANSFER = ROOT / "deploy/ci-transfer-cloud-compose.sh"


def run_transfer(tmp_path: Path, fail_upload: bool = False) -> tuple[subprocess.CompletedProcess, list[str]]:
    mock_bin = tmp_path / "bin"
    mock_bin.mkdir()
    command_log = tmp_path / "ssh-commands"
    fake_ssh = mock_bin / "ssh"
    fake_ssh.write_text('''#!/usr/bin/env bash
set -eu
last="${@: -1}"
printf '%s\\n' "$last" >> "$FAKE_SSH_LOG"
bash -n -c "$last"
if [[ "$last" == *".datashield-cloud-upload"* ]]; then
  cat >/dev/null
  [[ "${FAKE_SSH_FAIL_UPLOAD:-0}" != 1 ]] || exit 57
fi
''')
    fake_ssh.chmod(0o755)
    compose_file = tmp_path / "docker-compose.cloud.yml"
    compose_file.write_text("services:\n  cloud:\n")
    compose_sha = hashlib.sha256(compose_file.read_bytes()).hexdigest()
    sha = "a" * 40
    digests = ["sha256:" + str(i) * 64 for i in (1, 2, 3)]
    env = {
        **os.environ,
        "PATH": f"{mock_bin}:{os.environ['PATH']}",
        "FAKE_SSH_LOG": str(command_log),
        "ECS_USER": "admin",
        "ECS_PORT": "22",
        "ECS_HOST": "cloud.example.invalid",
        "ECS_KNOWN_HOSTS": "cloud.example.invalid ssh-ed25519 AAAATEST",
        "ECS_SSH_KEY": "PRIVATE-KEY-MARKER",
        "RUNNER_TEMP": str(tmp_path),
    }
    if fail_upload:
        env["FAKE_SSH_FAIL_UPLOAD"] = "1"
    result = subprocess.run(
        ["bash", str(TRANSFER), sha, compose_sha, *digests, str(compose_file)],
        env=env,
        text=True,
        capture_output=True,
    )
    commands = command_log.read_text().splitlines() if command_log.exists() else []
    return result, commands


def test_ssh_transfer_failure_stops_before_stage_diagnose_and_deploy(tmp_path):
    result, commands = run_transfer(tmp_path, fail_upload=True)

    assert result.returncode != 0
    assert len(commands) == 1
    assert "stage " not in commands[0] and " diagnose " not in commands[0] and " deploy " not in commands[0]
    assert "PRIVATE-KEY-MARKER" not in result.stdout + result.stderr


def test_successful_transfer_stages_diagnoses_and_deploys_same_sha_hash_and_digests(tmp_path):
    result, commands = run_transfer(tmp_path)

    assert result.returncode == 0, result.stderr
    assert len(commands) == 4
    assert ".datashield-cloud-upload" in commands[0]
    for action in ("stage", "diagnose", "deploy"):
        command = next(line for line in commands if f"cloud-deploy {action} " in line)
        assert "a" * 40 in command
        assert hashlib.sha256(b"services:\n  cloud:\n").hexdigest() in command
        assert all(("sha256:" + str(i) * 64) in command for i in (1, 2, 3))
    assert [next(i for i, command in enumerate(commands) if f"cloud-deploy {action} " in command) for action in ("stage", "diagnose", "deploy")] == [1, 2, 3]
    assert "PRIVATE-KEY-MARKER" not in result.stdout + result.stderr
