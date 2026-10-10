from pathlib import Path
import hashlib
import os
import subprocess


ROOT = Path(__file__).resolve().parents[2]
HELPER = ROOT / "deploy/cloud-release-artifact.sh"


def run_helper(tmp_path: Path, operation: str, *, compose: bytes | None = b"services:\n  cloud:\n") -> subprocess.CompletedProcess:
    source_sha = "a" * 40
    cloud_digest = "sha256:" + "1" * 64
    identity_digest = "sha256:" + "2" * 64
    proxy_digest = "sha256:" + "3" * 64
    compose_sha = hashlib.sha256(compose or b"").hexdigest()
    home = tmp_path / "home" / "admin"
    upload_dir = home / ".datashield-cloud-upload" / source_sha
    upload_dir.mkdir(parents=True, exist_ok=True)
    home.chmod(0o700)
    (home / ".datashield-cloud-upload").chmod(0o700)
    upload_dir.chmod(0o700)
    if compose is not None:
        upload = upload_dir / "docker-compose.cloud.yml"
        upload.write_bytes(compose)
        upload.chmod(0o600)
    root = tmp_path / "opt" / "datashield"
    (root / "releases").mkdir(parents=True, exist_ok=True)
    root.chmod(0o700)
    (root / "releases").chmod(0o700)
    script = f'''set -Eeuo pipefail
ROOT={str(root)!r}
die() {{ printf '%s\\n' "$1" >&2; exit 1; }}
getent() {{ printf 'admin:x:1000:1000::%s:/bin/bash\\n' "$TEST_ADMIN_HOME"; }}
source {str(HELPER)!r}
ARTIFACT_ROOT_OWNER="$(id -un)"
ARTIFACT_UPLOAD_OWNER="$(id -un)"
'''
    if operation == "stage":
        script += f'''stage_compose_release {source_sha} {compose_sha} {cloud_digest} {identity_digest} {proxy_digest}'''
    elif operation == "wrong_hash":
        script += f'''stage_compose_release {source_sha} {"0" * 64} {cloud_digest} {identity_digest} {proxy_digest}'''
    elif operation == "missing":
        script += f'''stage_compose_release {source_sha} {compose_sha} {cloud_digest} {identity_digest} {proxy_digest}'''
    elif operation == "wrong_commit":
        script += f'''stage_compose_release {source_sha} {compose_sha} {cloud_digest} {identity_digest} {proxy_digest}
sed -i 's/DATASHIELD_RELEASE_SHA={source_sha}/DATASHIELD_RELEASE_SHA={"b" * 40}/' "$ROOT/releases/{source_sha}/release.manifest"
assert_staged_compose_release {source_sha} {compose_sha} {cloud_digest} {identity_digest} {proxy_digest}'''
    elif operation == "wrong_digest":
        script += f'''stage_compose_release {source_sha} {compose_sha} {cloud_digest} {identity_digest} {proxy_digest}
assert_staged_compose_release {source_sha} {compose_sha} {"sha256:" + "4" * 64} {identity_digest} {proxy_digest}'''
    elif operation == "tampered_after_stage":
        script += f'''stage_compose_release {source_sha} {compose_sha} {cloud_digest} {identity_digest} {proxy_digest}
printf tampered >> "$ROOT/releases/{source_sha}/docker-compose.cloud.yml"
assert_staged_compose_release {source_sha} {compose_sha} {cloud_digest} {identity_digest} {proxy_digest}'''
    result = subprocess.run(["bash", "-c", script], env={**os.environ, "TEST_ADMIN_HOME": str(home)}, text=True, capture_output=True)
    return result


def test_stages_compose_with_sha_commit_and_all_digests(tmp_path):
    result = run_helper(tmp_path, "stage")

    assert result.returncode == 0, result.stderr
    release = tmp_path / "opt/datashield/releases" / ("a" * 40)
    assert (release / "docker-compose.cloud.yml").read_bytes() == b"services:\n  cloud:\n"
    assert "DATASHIELD_RELEASE_SHA=" + "a" * 40 in (release / "release.manifest").read_text()
    assert not (tmp_path / "home/admin/.datashield-cloud-upload" / ("a" * 40) / "docker-compose.cloud.yml").exists()


def test_missing_uploaded_compose_is_rejected(tmp_path):
    result = run_helper(tmp_path, "missing", compose=None)

    assert result.returncode != 0
    assert "uploaded Compose file is missing" in result.stderr


def test_compose_hash_mismatch_is_rejected_before_staging(tmp_path):
    result = run_helper(tmp_path, "wrong_hash")

    assert result.returncode != 0
    assert "SHA256 does not match" in result.stderr
    assert not list((tmp_path / "opt/datashield/releases").iterdir())


def test_commit_and_digest_mismatch_cannot_reuse_staged_compose(tmp_path):
    commit_result = run_helper(tmp_path / "commit", "wrong_commit")
    digest_result = run_helper(tmp_path / "digest", "wrong_digest")

    assert commit_result.returncode != 0
    assert digest_result.returncode != 0


def test_compose_tampering_after_stage_is_rejected_before_diagnose_or_deploy(tmp_path):
    result = run_helper(tmp_path, "tampered_after_stage")

    assert result.returncode != 0
    assert "Compose file SHA256 does not match" in result.stderr


def test_host_installer_checks_and_installs_runtime_helpers_as_a_set():
    installer = (ROOT / "deploy/install-cloud-host.sh").read_text()
    required = ("datashield-cloud-deploy", "container-id.sh", "cloud-deploy-state.sh", "cloud-release-artifact.sh", "check-cloud-config.sh")
    preflight = installer.split("# Finish every host-state preflight", 1)[1].split("install -d -o root", 1)[0]
    installs = installer.split("install -d -o root", 1)[1]
    for filename in required:
        assert filename in preflight
        assert f"install -o root -g root" in installs
        assert filename in installs
    assert "updating_install=1" in installer
    assert '80|443) expected_service=gateway' in installer
    assert '8001) expected_service=identity' in installer
    assert 'label=com.docker.compose.project=source' in installer
