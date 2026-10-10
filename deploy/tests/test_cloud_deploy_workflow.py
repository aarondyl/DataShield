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


def test_publish_only_runs_after_successful_main_cloud_validation_or_manual_main_deploy():
    publish = job_block("build-and-publish")
    assert "workflows: [Cloud RegIntel validation]" in WORKFLOW
    assert "branches: [main]" in WORKFLOW
    assert "github.event_name == 'pull_request'" not in WORKFLOW
    assert "github.event_name == 'workflow_run'" in publish
    assert "github.event.workflow_run.conclusion == 'success'" in publish
    assert "github.event.workflow_run.event == 'push'" in publish
    assert "github.event.workflow_run.head_branch == 'main'" in publish
    assert "inputs.action == 'deploy'" in publish
    assert "github.ref == 'refs/heads/main'" in publish
    assert "github.event.workflow_run.head_sha || github.sha" in publish
    assert "repos/${GITHUB_REPOSITORY}/commits/main" in publish
    assert '"$SOURCE_SHA" = "$current_main"' in publish
    assert "gh run list --workflow cloud-validation.yml --branch main --commit \"$SOURCE_SHA\" --status success" in publish


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
    for output in ("cloud_digest", "identity_digest", "proxy_digest"):
        assert output in publish
        assert f"needs.build-and-publish.outputs.{output}" in deploy
    assert ":latest" not in publish + deploy
    assert "needs: build-and-publish" in deploy
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
    assert "datashield-cloud-deploy deploy $SOURCE_SHA $CLOUD_DIGEST $IDENTITY_DIGEST $PROXY_DIGEST" in deploy
    assert "production-cutover.approved" in wrapper
    assert "first production cutover requires root-created production-cutover.approved" in wrapper
