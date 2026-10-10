import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CHECKER = ROOT / "deploy/check-cloud-storage-compose.py"
WRAPPER = (ROOT / "deploy/datashield-cloud-deploy").read_text()


def compose_document():
    return {
        "volumes": {"cloud_postgres_data": {"name": "source_cloud_postgres_data"}},
        "networks": {"cloud_database": {"name": "source_cloud_database", "internal": True}},
        "services": {
            "postgres": {
                "volumes": [{"type": "volume", "source": "cloud_postgres_data", "target": "/var/lib/postgresql/data"}],
                "ports": [],
                "networks": {"cloud_database": {}},
            },
            "cloud": {"ports": [{"host_ip": "127.0.0.1", "published": "8000", "target": 8000}]},
            "identity": {"ports": [{"host_ip": "127.0.0.1", "published": "8001", "target": 8001}]},
            "gateway": {"ports": [{"host_ip": "0.0.0.0", "published": "443", "target": 443}]},
        },
    }


def run(document):
    return subprocess.run(
        [sys.executable, str(CHECKER)],
        input=json.dumps(document),
        text=True,
        capture_output=True,
        check=False,
    )


def test_production_compose_storage_and_loopback_api_bindings_are_accepted():
    result = run(compose_document())
    assert result.returncode == 0, result.stderr
    assert result.stdout == result.stderr == ""


def test_compose_port_may_be_string_or_integer_without_weakening_loopback_check():
    document = compose_document()
    document["services"]["cloud"]["ports"][0]["published"] = 8000
    assert run(document).returncode == 0
    document["services"]["cloud"]["ports"][0]["host_ip"] = "0.0.0.0"
    result = run(document)
    assert result.returncode == 1
    assert "cloud_loopback_port" in result.stderr


def test_volume_network_and_database_port_protections_remain_enforced():
    for mutation, expected in (
        (lambda d: d["volumes"]["cloud_postgres_data"].update(name="different_volume"), "postgres_volume_name"),
        (lambda d: d["services"]["postgres"]["volumes"][0].update(target="/tmp/data"), "postgres_volume_mount"),
        (lambda d: d["networks"]["cloud_database"].update(name="different_network"), "postgres_network_name"),
        (lambda d: d["networks"]["cloud_database"].update(internal=False), "postgres_network_name"),
        (lambda d: d["services"]["postgres"]["volumes"].append({"type": "bind", "source": "/tmp", "target": "/var/lib/postgresql/data"}), "postgres_volume_mount"),
        (lambda d: d["services"]["postgres"].update(ports=[{"published": "5432"}]), "postgres_public_port"),
        (lambda d: d["services"]["cloud"]["ports"].append({"host_ip": "0.0.0.0", "published": "8000", "target": 8000}), "cloud_public_port"),
    ):
        document = compose_document()
        mutation(document)
        result = run(document)
        assert result.returncode == 1
        assert expected in result.stderr


def test_public_identity_port_is_rejected_and_invalid_compose_is_reported_without_traceback():
    document = compose_document()
    document["services"]["identity"]["ports"][0]["host_ip"] = "0.0.0.0"
    result = run(document)
    assert result.returncode == 1
    assert "identity_public_port" in result.stderr
    invalid = subprocess.run([sys.executable, str(CHECKER)], input="", text=True, capture_output=True)
    assert invalid.returncode == 2
    assert "invalid_json" in invalid.stderr
    assert "Traceback" not in invalid.stderr


def test_deployer_checks_compose_render_before_validating_invariants():
    assert "if ! merged_config=\"$(compose --profile identity --profile production config --format json 2>/dev/null)\"; then" in WRAPPER
    assert "check-cloud-storage-compose.py" in WRAPPER
    assert "candidate Compose configuration could not be rendered" in WRAPPER


def test_storage_assertion_runs_in_current_shell_so_die_is_not_swallowed():
    assert 'postgres_before="$(assert_existing_storage)"' not in WRAPPER
    assert '[[ "$(assert_existing_storage)" == "$postgres_before" ]]' not in WRAPPER
    assert WRAPPER.count("    assert_existing_storage\n") >= 2
    assert 'postgres_before="$EXISTING_POSTGRES_ID"' in WRAPPER
    assert 'postgres_id="$EXISTING_POSTGRES_ID"' in WRAPPER
