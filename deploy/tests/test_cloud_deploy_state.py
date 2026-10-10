from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[2]
STATE_HELPER = ROOT / "deploy/cloud-deploy-state.sh"


def run_state_scenario(tmp_path: Path, scenario: str) -> str:
    harness = r'''set -Eeuo pipefail
ROOT="$TEST_ROOT"
PROJECT=source
PROJECT_DIR="$TEST_ROOT/source"
LOG="$TEST_ROOT/deploy.log"
BASE="$PROJECT_DIR/docker-compose.cloud.yml"
ECS_BASE="$PROJECT_DIR/docker-compose.ecs.yml"
EXTRA_FILES=()
COMPOSE=(docker compose)
mkdir -p "$PROJECT_DIR"
touch "$BASE" "$ECS_BASE"
source "$STATE_HELPER"
die() { echo "unexpected die: $*" >&2; exit 1; }
log() { printf '%s\n' "$*" >> "$LOG"; }
PG_ID=dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd
CLOUD_ID=cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
GATEWAY_ID=eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee
CLOUD_IMAGE=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
GATEWAY_IMAGE=bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
CALLS="$TEST_ROOT/compose-calls"
: > "$CALLS"
DOCKER_CALLS="$TEST_ROOT/docker-calls"
: > "$DOCKER_CALLS"
docker() {
  local arg service format id
  printf '%s\n' "$*" >> "$DOCKER_CALLS"
  if [[ "$1" == ps ]]; then
    service=""
    for arg in "$@"; do [[ "$arg" == label=com.docker.compose.service=* ]] && service="${arg##*=}"; done
    case "$service" in
      cloud) echo "$CLOUD_ID" ;;
      identity) { [[ "${IDENTITY_REMOVED:-0}" != 1 ]] && { [[ "${IDENTITY_BEFORE:-absent}" == present ]] || [[ "${SNAPSHOT_DONE:-0}" == 1 ]]; }; } && echo ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff ;;
      gateway) [[ "${GATEWAY_BEFORE:-present}" == present ]] && echo "$GATEWAY_ID" ;;
      postgres) echo "$PG_ID" ;;
      *) return 1 ;;
    esac
    return 0
  fi
  if [[ "$1" == inspect ]]; then
    format="$3"; id="$4"
    case "$format" in
      '{{.Image}}') [[ "$id" == "$CLOUD_ID" ]] && echo "sha256:$CLOUD_IMAGE" || echo "sha256:$GATEWAY_IMAGE" ;;
      '{{.State.Running}}') [[ "$id" == "$GATEWAY_ID" ]] && echo "${GATEWAY_RUNNING:-false}" || echo true ;;
      '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}') echo healthy ;;
      '{{range .Mounts}}{{if eq .Destination "/var/lib/postgresql/data"}}{{.Name}}{{end}}{{end}}') echo source_cloud_postgres_data ;;
      *) return 1 ;;
    esac
    return 0
  fi
  [[ "$1" == image && "$2" == tag ]] && return 0
  if [[ "$1" == rm && "$2" == --force ]]; then IDENTITY_REMOVED=1; return 0; fi
  echo "unexpected docker operation: $*" >&2
  return 1
}
compose() { printf '%s\n' "$*" >> "$CALLS"; }
existing_postgres_id() { echo "$PG_ID"; }
restore_previous_cloud() { restore_first_cutover_state; }
save_first_cutover_state
SNAPSHOT_DONE=1
case "$SCENARIO" in
  restore-first-cutover)
    restore_first_cutover_state
    ;;
  migration-failure)
    activation_started=0
    rollback_after_failed_activation 1
    test ! -s "$CALLS"
    ;;
  health-check-failure)
    activation_started=1
    rollback_after_failed_activation 1
    grep -q 'up -d --no-build --no-deps cloud gateway' "$CALLS"
    grep -q 'stop gateway' "$CALLS"
    grep -q 'rm --force ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff' "$DOCKER_CALLS"
    ;;
  manual-rollback)
    restore_previous_cloud
    grep -q 'up -d --no-build --no-deps cloud gateway' "$CALLS"
    ;;
  *) exit 2 ;;
esac
! grep -Eq '(^| )(postgres|down|volume|--volumes)( |$)' "$CALLS"
'''
    env = {
        "TEST_ROOT": str(tmp_path),
        "STATE_HELPER": str(STATE_HELPER),
        "SCENARIO": scenario,
        "GATEWAY_BEFORE": "present",
        "GATEWAY_RUNNING": "false",
        "IDENTITY_BEFORE": "absent",
    }
    result = subprocess.run(["bash", "-c", harness], env=env, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr + result.stdout
    return (tmp_path / "compose-calls").read_text()


def test_failed_first_switch_restores_cloud_and_prior_proxy_and_removes_new_identity(tmp_path):
    calls = run_state_scenario(tmp_path, "restore-first-cutover")
    assert "datashield-cloud-rollback:" in (tmp_path / "first-cutover-rollback/compose.override.yml").read_text()
    assert "datashield-gateway-rollback:" in (tmp_path / "first-cutover-rollback/compose.override.yml").read_text()
    assert "identity" in calls and "gateway" in calls and "cloud" in calls


def test_migration_failure_before_activation_does_not_restart_services(tmp_path):
    assert run_state_scenario(tmp_path, "migration-failure") == ""


def test_health_check_failure_restores_prior_service_states_without_postgres(tmp_path):
    calls = run_state_scenario(tmp_path, "health-check-failure")
    assert "stop gateway" in calls
    docker_calls = (tmp_path / "docker-calls").read_text()
    assert "rm --force ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff" in docker_calls
    assert not any(line.startswith("rm ") and "dddddddddddddddddddddddddddddddd" in line for line in docker_calls.splitlines())


def test_manual_first_cutover_rollback_uses_saved_three_service_state(tmp_path):
    calls = run_state_scenario(tmp_path, "manual-rollback")
    assert "up -d --no-build --no-deps cloud gateway" in calls
