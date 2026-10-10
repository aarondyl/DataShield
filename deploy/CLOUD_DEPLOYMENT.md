# DataShield Cloud CI/CD (Alibaba Cloud Simple Application Server)

## Architecture

The `Cloud RegIntel validation` workflow tests Cloud contracts/migrations and builds isolated Cloud, Identity and Caddy images on GitHub-hosted runners. After successful validation of a `main` push, `Publish and deploy Cloud` builds and publishes the three private GHCR images under the immutable full source SHA. Its summary records the validated source SHA and each image digest. This publishing job has `packages:write` but receives no server credentials and does not depend on the production deployment switch. A separate `deploy-production` job consumes only those published digests and runs only when `CLOUD_DEPLOY_ENABLED=true`; it uses the `Production` GitHub Environment, which must have required reviewers configured before production use. The restricted server wrapper independently requires the root-owned first-cutover approval marker. Deployment retains the existing Compose project name `source`, working directory `/opt/datashield-cloud/source`, and its `docker-compose.ecs.yml` overlay. The host runs the project as root through `/usr/local/sbin/datashield-cloud-deploy`; the `deploy` SSH user receives sudo permission for that fixed, root-owned wrapper only. PostgreSQL is never included among services updated by deployment: migration and application `up` commands use `--no-deps`, then assert the same PostgreSQL container ID and `source_cloud_postgres_data` mount remain in place. API ports stay loopback-bound, and Caddy is added on TCP 80/443.

Global RegIntel scheduling runs in the Cloud API lifespan, so this resource-limited single-server deployment does not add another worker container. The helper requires the existing `source-postgres-1`-equivalent service in project `source`, verifies its `source_cloud_postgres_data` mount and database network, and checks the candidate Compose file resolves the same volume, network, and `127.0.0.1:8000` API mapping. It refuses to create an alternate empty production database. A full `pg_dumpall` backup is gzip-validated and stored mode `0600` under `/opt/datashield/backups/` before additive migrations. Before first cutover it also tags the current Cloud image locally and saves a rollback override without stopping the container. It never runs `down -v`, starts the PostgreSQL service, or downgrades database migrations. Updating the single Cloud API container can briefly interrupt API requests; this is not zero-downtime deployment. Compose resource caps are 450 MiB PostgreSQL, 400 MiB Cloud, 192 MiB Identity and 80 MiB Caddy; deployment refuses migration when current available RAM is below 600 MiB.

## Deployment triggers

Cloud validation and the subsequent Cloud deployment run when `main` changes under:

- `backend/**` (Cloud, Identity, shared runtime, dependencies, migrations and tests)
- `docker-compose.cloud.yml`
- `deploy/**`
- `.dockerignore`, `backend/.dockerignore`
- Cloud validation/deployment workflows and the SSH host audit workflow

Desktop-only paths such as `frontend/**`, `apps/desktop/**`, `src-tauri/**` and Desktop release configuration do not trigger Cloud deployment. Desktop release workflows remain independent. A manual workflow dispatch supports a read-only host audit or publishing and deployment of the current validated `main` head. Manual publishing checks that the source SHA is current `main` and has a successful Cloud validation run. The deployment rejects stale commits and serialized deploys cannot overwrite a newer commit. Production uses digest references (`ghcr.io/aarondyl/datashield-cloud@sha256:…`, `datashield-identity@sha256:…`, and `datashield-cloud-proxy@sha256:…`); SHA tags are for traceability, not deployment identity.

## One-time host preparation and external settings

The manual read-only audit and production deployment both use the `Production` GitHub Environment because Environment Secrets do not cross environment boundaries. Store `ECS_HOST`, `ECS_PORT`, `ECS_USER`, `ECS_KNOWN_HOSTS` and `ECS_SSH_KEY` there. If required reviewers are configured, the read-only audit is also subject to that Environment's approval gate. The host must have Docker Compose v2 and both current Compose files. The administrator must install the restricted root wrapper using the documented command in [cloud-secrets.md](cloud-secrets.md). Before writing host files or sudo policy, the installer verifies the live `source` PostgreSQL container, health, named volume, network and Cloud loopback port; checks that TCP 80/443/8001 are free on first install; and validates existing Secret paths, ownership and modes without reading or printing their contents. On updates, it permits those ports only when the current `source` gateway owns 80/443 and the current `source` Identity service owns 8001. Any failed preflight leaves host files and running containers unchanged. This step cannot be completed by the unprivileged `deploy` SSH account.

For safety, only the production deployment job requires the repository Actions variable `CLOUD_DEPLOY_ENABLED=true`. Leave it unset/false until host installation, Production Environment SSH settings and required reviewers, DNS/firewall, existing database-project verification, and the operator's first-cutover approval marker are complete. Cloud CI and GHCR publishing can run while production deployment is disabled. The workflow also supports a read-only host audit.

In the Alibaba Cloud Simple Application Server console firewall, allow inbound TCP 80 (ACME certificate issuance and HTTP-to-HTTPS redirect) and TCP 443 (public HTTPS API). Keep SSH TCP 22 restricted to the existing administration policy. Do not open 8000, 8001, 5432, or Docker's API port. Set the DNS A record `api.datashield.ltd` to the server's public IPv4 address before Caddy requests a certificate. Do not enable deployment until the host has been audited and the operator approves the first production cutover by creating the root-only `/opt/datashield/production-cutover.approved` marker.

Add the actual non-secret SMTP host/user/sender values to `/opt/datashield/secrets/cloud.env`. Populate the six application Secret files and GHCR token described in [cloud-secrets.md](cloud-secrets.md). Never store credentials in GitHub workflow variables or Docker build arguments. GitHub Actions only receives the existing SSH credential, and the server-only registry pull token is used for GHCR access.

## CI and deployment operations

- `Cloud RegIntel validation` is the required build/test workflow. It runs on PRs and matching `main` changes.
- `Publish and deploy Cloud` publishes each SHA-tagged image after successful Cloud validation. Its job summary records the full source SHA and immutable digest of all three GHCR images. The separate `deploy-production` job is guarded by `CLOUD_DEPLOY_ENABLED`, the `Production` GitHub Environment, and the server's first-cutover approval marker. It deploys those digest references, runs controlled migrations, starts Compose, verifies internal dependencies, then checks public Cloud, Identity, and regulation API endpoints.
- The workflow uses Actions concurrency group `datashield-cloud-production`; the host also uses `flock`.
- If public smoke checks fail after activation, the workflow requests restoration of the saved last-good application image. The host never downgrades migrations automatically. If rollback cannot be proven safe, inspect the root-only deployment log and restore the database only from an explicit operator-approved backup procedure.

Useful administrator commands (run via the approved root channel):

```sh
/usr/local/sbin/datashield-cloud-deploy audit
/usr/local/sbin/datashield-cloud-deploy preflight
/usr/local/sbin/datashield-cloud-deploy diagnose <40-char-source-sha> <compose-sha256> sha256:<cloud-digest> sha256:<identity-digest> sha256:<proxy-digest>
docker compose --project-name source --project-directory /opt/datashield-cloud/source --env-file /opt/datashield/secrets/cloud.env -f /opt/datashield-cloud/source/docker-compose.cloud.yml -f /opt/datashield-cloud/source/docker-compose.ecs.yml ps
tail -n 100 /opt/datashield/deploy.log
cat /opt/datashield/active-sha
ls -lh /opt/datashield/backups
```

The deployment workflow checks out the exact validated source commit, hashes its `docker-compose.cloud.yml`, and streams that file to the admin account over the existing host-key-verified SSH connection. The server-side `stage` command verifies the transmitted SHA256, binds the file to the source commit and all three immutable image digests in a root-owned manifest, and stores it under `/opt/datashield/releases/<sha>/`. `diagnose` and `deploy` both re-check that manifest and the Compose file hash before using the same versioned file. Neither the production host nor the deployment wrapper downloads from `raw.githubusercontent.com`.

`diagnose` is a read-only production-host check after staging. It validates the candidate merged Compose configuration, preserves and verifies the live PostgreSQL container/volume identity, connects to Cloud and Identity databases with their configured roles, verifies private GHCR access to the three immutable image manifests, and checks free disk and memory. It uses short-lived files under `/tmp` and a temporary Docker credential directory; the diagnostic output omits connection strings and registry responses. It does not pull images, run migrations, or change application containers. Production activation retains the existing `CLOUD_DEPLOY_ENABLED`, Production Environment approval, and root-owned first-cutover approval gates.

Do not publish output of `docker compose config`, `docker inspect` environment dumps, or secret files. Container logs are retained by Docker's bounded `local` log driver. Restore a database dump only after stopping writes and explicit review; never restore a dump over production as an automated deployment step.

## Migration rehearsal against a backup copy

Before approving production migrations, an administrator can copy a protected `pg_dumpall` backup and the two database URL files to an isolated workstation. Treat the backup and URL files as production secrets because the backup contains identity data. Keep all three files mode `0600`, install the repository's backend development dependencies locally, and run:

```sh
python deploy/verify-cloud-migrations.py \
  --backup /secure/path/production-copy.sql.gz \
  --cloud-url-file /secure/path/cloud_database_url \
  --identity-url-file /secure/path/identity_database_url
```

The tool refuses group/world-readable inputs and remote Docker contexts. It explicitly selects the local default Unix-socket Docker context, restores the backup into a randomly named temporary PostgreSQL container on an internal Docker network, rewrites both DB endpoints to loopback, then runs Cloud and Identity Alembic migrations against that restored clone. It removes only its randomly named temporary container and network. It never connects to the production host and is not a command to run on the server. The backup copy should be deleted using the workstation's approved sensitive-data handling process after review.

## Validation boundaries

The deployment workflow does not change the Simple Server panel firewall, DNS, SSH policy, or existing service containers during installation/preflight. The production deployment changes only Cloud, Identity and gateway services after explicit first-cutover approval. External HTTPS smoke tests prove deployment only after firewall and DNS prerequisites are configured.
