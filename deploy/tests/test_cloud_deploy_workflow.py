from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = (ROOT / ".github/workflows/cloud-deploy.yml").read_text()


def job_block(name: str) -> str:
    match = re.search(
        rf"(?ms)^  {re.escape(name)}:\n(.*?)(?=^  [a-z][a-z-]*:\n|\Z)",
        WORKFLOW,
    )
    assert match, f"missing workflow job: {name}"
    return match.group(0)


def test_publish_only_runs_after_successful_main_cloud_validation():
    publish = job_block("build-and-publish")
    assert "workflows: [Cloud RegIntel validation]" in WORKFLOW
    assert "branches: [main]" in WORKFLOW
    assert "github.event_name == 'pull_request'" not in WORKFLOW
    assert "github.event_name == 'workflow_run'" in publish
    assert "github.event.workflow_run.conclusion == 'success'" in publish
    assert "github.event.workflow_run.event == 'push'" in publish
    assert "github.event.workflow_run.head_branch == 'main'" in publish
    assert "github.event.workflow_run.head_sha || github.sha" in publish
    assert "repos/${GITHUB_REPOSITORY}/commits/main" in publish
    assert '"$SOURCE_SHA" = "$current_main"' in publish
    manual = job_block("validate-approved-candidate")
    assert "gh run list --workflow cloud-validation.yml --branch main --commit \"$SOURCE_SHA\" --status success" in manual


def test_only_publish_job_has_package_write_and_it_has_no_production_secrets():
    publish = job_block("build-and-publish")
    deploy = job_block("deploy-production")
    audit = job_block("audit")
    assert "packages: write" in publish
    assert "packages: write" not in deploy + audit
    assert "ECS_SSH_KEY" not in publish
    assert "ECS_HOST" not in publish
    assert "environment:" not in publish


def test_all_images_are_published_by_digest_and_production_uses_those_digests():
    publish = job_block("build-and-publish")
    deploy = job_block("deploy-production")
    for image in ("datashield-cloud", "datashield-identity", "datashield-cloud-proxy"):
        assert f"ghcr.io/aarondyl/{image}:" in publish
        assert "provenance: false" in publish
    for output in ("cloud_digest", "identity_digest", "proxy_digest"):
        assert output in publish
        assert f"inputs.{output.replace('_digest', '_digest')}" in deploy or f"inputs.{output}" in job_block("validate-approved-candidate")
    assert ":latest" not in publish + deploy
    assert "needs: [build-and-publish, validate-approved-candidate]" in deploy
    assert "environment: Production" in deploy
    assert "vars.CLOUD_DEPLOY_ENABLED == 'true'" in deploy
    assert "sha256:[0-9a-f]{64}" in publish
    assert "sha256:[0-9a-f]{64}" in deploy


def test_manual_audit_is_retained_and_server_first_cutover_guard_remains_required():
    audit = job_block("audit")
    deploy = job_block("deploy-production")
    wrapper = (ROOT / "deploy/datashield-cloud-deploy").read_text()
    assert "inputs.action == 'audit'" in audit
    assert "datashield-cloud-deploy audit" in audit
    assert "ci-transfer-cloud-compose.sh" in deploy
    assert "datashield-cloud-deploy deploy $source_sha $compose_sha $cloud_digest $identity_digest $proxy_digest" in (ROOT / "deploy/ci-transfer-cloud-compose.sh").read_text()
    assert "production-cutover.approved" in wrapper
    assert "first production cutover requires root-created production-cutover.approved" in wrapper


def test_ssh_jobs_read_environment_secrets_from_production_and_use_admin_port_22():
    audit = job_block("audit")
    deploy = job_block("deploy-production")
    assert "environment: Production" in audit
    assert "environment: Production" in deploy
    for name in ("ECS_HOST", "ECS_PORT", "ECS_USER", "ECS_KNOWN_HOSTS", "ECS_SSH_KEY"):
        assert f"{name}: ${{{{ secrets.{name} }}}}" in audit
        assert f"{name}: ${{{{ secrets.{name} }}}}" in deploy
    assert "${{ vars.ECS_" not in WORKFLOW
    assert 'test -n "$ECS_HOST" && test "$ECS_USER" = admin && test "$ECS_PORT" = 22' in audit
    assert 'test "$ECS_USER" = admin && test "$ECS_PORT" = 22' in deploy
    assert "ECS_HOST: ${{ secrets.ECS_HOST }}" in deploy
    assert "ECS_KNOWN_HOSTS: ${{ secrets.ECS_KNOWN_HOSTS }}" in deploy
    assert "ECS_SSH_KEY: ${{ secrets.ECS_SSH_KEY }}" in deploy


def test_deployment_checks_out_same_validated_commit_and_passes_compose_hash():
    publish = job_block("build-and-publish")
    deploy = job_block("deploy-production")
    assert "compose_sha: ${{ steps.compose.outputs.sha256 }}" in publish
    assert "ref: ${{ env.SOURCE_SHA }}" in deploy
    assert 'test "$(git rev-parse HEAD)" = "$SOURCE_SHA"' in deploy
    assert "inputs.compose_sha256 || needs.build-and-publish.outputs.compose_sha" in deploy


def test_manual_deploy_checks_out_before_gh_cli_and_requires_fixed_candidate_inputs():
    workflow = WORKFLOW
    validator = job_block("validate-approved-candidate")
    checkout = validator.index("uses: actions/checkout@v4")
    gh_list = validator.index("gh run list --workflow cloud-validation.yml")
    assert checkout < gh_list
    for name in ("source_sha", "compose_sha256", "cloud_digest", "identity_digest", "proxy_digest"):
        assert f"      {name}:" in workflow
        assert f"inputs.{name}" in validator or f"inputs.{name}" in job_block("deploy-production")
    assert 'docker image inspect --format' in validator
    assert 'org.opencontainers.image.revision' in validator
    assert "packages: read" in validator
    assert "CLOUD_DEPLOY_ENABLED" in job_block("deploy-production")
    assert "ECS_SSH_KEY" not in validator and "ECS_HOST" not in validator
    assert "environment: Production" in job_block("deploy-production")


def test_deployment_job_keeps_production_and_first_cutover_gates():
    deploy = job_block("deploy-production")
    wrapper = (ROOT / "deploy/datashield-cloud-deploy").read_text()
    assert "vars.CLOUD_DEPLOY_ENABLED == 'true'" in deploy
    assert "environment: Production" in deploy
    assert "production-cutover.approved" in wrapper
    transfer = (ROOT / "deploy/ci-transfer-cloud-compose.sh").read_text()
    assert "StrictHostKeyChecking=yes" in transfer
    assert "KnownHostsFile=$known_hosts" in transfer
    assert "ECS_SSH_KEY" in transfer and "ECS_KNOWN_HOSTS" in transfer
