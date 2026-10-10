# DataShield Cloud CI/CD (Alibaba Cloud Simple Application Server)

## Architecture

The `Cloud RegIntel validation` workflow tests Cloud contracts/migrations and builds isolated Cloud, Identity and Caddy images on GitHub-hosted runners. On a successful `main` push validation, `Deploy Cloud to Simple Application Server` builds and pushes each image to private GHCR under the immutable source SHA, then deploys by registry digest over pinned-host-key SSH. The host runs the existing Docker Compose project as root through `/usr/local/sbin/datashield-cloud-deploy`; the `deploy` SSH user receives sudo permission for that fixed, root-owned wrapper only. Compose keeps PostgreSQL private and persistent, API ports loopback-bound, and exposes Caddy on TCP 80/443.

Global RegIntel scheduling runs in the Cloud API lifespan, so this resource-limited single-server deployment does not add another worker container. The deployment helper refuses to proceed unless it finds the existing `datashield-cloud` PostgreSQL service; it never initializes an alternate empty production database. Database dumps are written mode `0600` to `/opt/datashield/backups/` before additive migrations. It never runs `down -v` or database downgrade. Single-host Compose replacement can briefly interrupt API requests; this is not zero-downtime deployment.

## Deployment triggers

Cloud validation and the subsequent Cloud deployment run when `main` changes under:

- `backend/**` (Cloud, Identity, shared runtime, dependencies, migrations and tests)
- `docker-compose.cloud.yml`
- `deploy/**`
- `.dockerignore`, `backend/.dockerignore`
- Cloud validation/deployment workflows and the SSH host audit workflow

Desktop-only paths such as `frontend/**`, `apps/desktop/**`, `src-tauri/**` and Desktop release configuration do not trigger Cloud deployment. Desktop release workflows remain independent. A manual workflow dispatch supports a read-only host audit or deployment of the current validated `main` head. The deployment rejects stale commits and serialized deploys cannot overwrite a newer commit.

## One-time host preparation and external settings

The existing GitHub Actions `test-ssh` environment supplies the pinned host key and deploy SSH key. The host must have Docker Compose v2, and the administrator must install the restricted root wrapper using the documented one-time command in [cloud-secrets.md](cloud-secrets.md). This step cannot be completed by the unprivileged `deploy` SSH account.

For safety, automatic and manual deployment jobs require the repository Actions variable `CLOUD_DEPLOY_ENABLED=true`. Leave it unset/false until host installation, all required secrets, DNS/firewall, existing database-project verification, and the operator's first-cutover approval marker are complete. The workflow still runs Cloud CI and supports a read-only audit while deployment is disabled.

In the Alibaba Cloud Simple Application Server console firewall, allow inbound TCP 80 (ACME certificate issuance and HTTP-to-HTTPS redirect) and TCP 443 (public HTTPS API). Keep SSH TCP 22 restricted to the existing administration policy. Do not open 8000, 8001, 5432, or Docker's API port. Set the DNS A record `api.datashield.ltd` to the server's public IPv4 address before Caddy requests a certificate. Do not enable deployment until the host has been audited and the operator approves the first production cutover by creating the root-only `/opt/datashield/production-cutover.approved` marker.

Add the actual non-secret SMTP host/user/sender values to `/opt/datashield/secrets/cloud.env`. Populate the six application Secret files and GHCR token described in [cloud-secrets.md](cloud-secrets.md). Never store credentials in GitHub workflow variables or Docker build arguments. GitHub Actions only receives the existing SSH credential, and the server-only registry pull token is used for GHCR access.

## CI and deployment operations

- `Cloud RegIntel validation` is the required build/test workflow. It runs on PRs and matching `main` changes.
- `Deploy Cloud to Simple Application Server` runs after successful Cloud validation for a `main` push. It builds SHA-tagged packages, records/passes immutable digests, runs controlled migrations, starts Compose, verifies internal dependencies, then checks public Cloud, Identity, and regulation API endpoints.
- The workflow uses Actions concurrency group `datashield-cloud-production`; the host also uses `flock`.
- If public smoke checks fail after activation, the workflow requests restoration of the saved last-good application image. The host never downgrades migrations automatically. If rollback cannot be proven safe, inspect the root-only deployment log and restore the database only from an explicit operator-approved backup procedure.

Useful administrator commands (run via the approved root channel):

```sh
/usr/local/sbin/datashield-cloud-deploy audit
/usr/local/sbin/datashield-cloud-deploy preflight
docker compose --project-name datashield-cloud --env-file /opt/datashield/secrets/cloud.env -f /opt/datashield/docker-compose.cloud.yml ps
tail -n 100 /opt/datashield/deploy.log
cat /opt/datashield/active-sha
ls -lh /opt/datashield/backups
```

Do not publish output of `docker compose config`, `docker inspect` environment dumps, or secret files. Container logs are retained by Docker's bounded `local` log driver. Restore a database dump only after stopping writes and explicit review; never restore a dump over production as an automated deployment step.

## Validation boundaries

The deployment workflow does not change the Simple Server panel firewall, DNS, SSH policy, server sudoers, existing systemd service, or first-cutover marker. External HTTPS smoke tests prove deployment only after those prerequisites are configured. If the server still has an unmanaged `datashield.service`, the wrapper will not stop it; administrator review and explicit cutover approval are required.
