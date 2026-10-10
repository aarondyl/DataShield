from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[2]
WRAPPER = (ROOT / "deploy/datashield-cloud-deploy").read_text()


def test_wrapper_exposes_read_only_diagnose_command_for_immutable_images():
    assert "diagnose)" in WRAPPER
    assert "diagnose requires SHA, Compose SHA256, and three image digests" in WRAPPER
    assert 'run_readonly_diagnostic "$sha" "$compose_sha" "$cloud_digest" "$identity_digest" "$proxy_digest"' in WRAPPER


def test_diagnostics_cover_compose_databases_registry_and_host_capacity():
    body = re.search(r"(?ms)^run_readonly_diagnostic\(\) \{(.*?)^\}", WRAPPER)
    assert body, "read-only diagnostic function is missing"
    body = body.group(1)
    for expected in (
        "config --format json",
        "assert_existing_storage",
        "DB_CONNECTIONS_OK",
        "docker login ghcr.io",
        "docker manifest inspect",
        "df -Pk",
        "/proc/meminfo",
        "CLOUD_SECRETS_DIR/cloud_database_url",
        "CLOUD_SECRETS_DIR/identity_database_url",
        "assert_staged_compose_release",
    ):
        assert expected in body
    assert "2>/dev/null | grep -Fxq 'DB_CONNECTIONS_OK'" in body
    assert "release images must use immutable SHA256 digests" in (ROOT / "deploy/cloud-release-artifact.sh").read_text()


def test_readonly_diagnostic_uses_ephemeral_credentials_and_no_mutating_compose_action():
    body = re.search(r"(?ms)^run_readonly_diagnostic\(\) \{(.*?)^\}", WRAPPER).group(1)
    assert 'mktemp -d /tmp/datashield-cloud-diagnose.' in body
    assert 'docker_config="$(mktemp -d "$diagnostic_tmp/docker-config.' in body
    assert 'DOCKER_CONFIG="$docker_config" docker login' in body
    assert not re.search(r"\bcompose\s+(?:up|down|run|rm|stop|start)\b", body)
    assert "docker pull " not in body
    assert "docker exec -i" in body
    assert "raw.githubusercontent.com" not in body
    assert "curl " not in body


def test_deploy_revalidates_same_staged_compose_and_has_no_raw_github_dependency():
    deploy_case = WRAPPER.split("  deploy)", 1)[1].split("  rollback)", 1)[0]
    assert 'assert_staged_compose_release "$sha" "$compose_sha" "$cloud_digest" "$identity_digest" "$proxy_digest"' in deploy_case
    assert "raw.githubusercontent.com" not in deploy_case
    assert "curl " not in deploy_case
