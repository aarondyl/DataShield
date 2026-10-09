# DataShield Identity Service

Identity runs as a separate FastAPI process and uses its own PostgreSQL database and database role. It owns account, organization, membership, session, invitation, verification, and audit records only. It must not be pointed at the RegIntel database using the RegIntel database role.

## Required production secrets

Set `IDENTITY_DATABASE_URL_FILE` to a root/deploy-user-only file containing a PostgreSQL URL for a dedicated database and least-privilege role, such as `postgresql+psycopg://datashield_identity:<URL-encoded-password>@postgres/datashield_identity`. The role should have privileges only in the identity database. `docker-compose.cloud.yml` mounts this file as a Compose secret and does not publish PostgreSQL.

Set `IDENTITY_SMTP_HOST`, `IDENTITY_SMTP_PORT`, `IDENTITY_SMTP_USER`, `IDENTITY_EMAIL_FROM`, and `IDENTITY_SMTP_PASSWORD_FILE`. Use a verified sender and a deploy-only password file. Account registration and invitations remain unavailable when email delivery is not configured; email verification is required by default.

Identity is an opt-in Compose profile so an existing RegIntel-only deployment does not start an unprovisioned account service. After creating the separate database and SMTP secrets, validate the full Compose config, then start it with `docker compose --profile identity up -d identity`.

For an existing PostgreSQL volume, create the identity database and role through an administrator session without touching the RegIntel database. Generate a unique password in the server's secret manager, then grant the dedicated role access only to the new database. Do not put credentials in shell history, source control, or chat. Before deployment, take and verify a PostgreSQL backup, inspect current memory and disk headroom, and validate Compose configuration. The service container runs the identity-only Alembic chain on startup.

The first platform administrator must be provisioned out of band after registration has been email-verified. Use a restricted DBA session to set `identity_users.is_platform_admin = TRUE` for the verified operator account, record the operation, and close the DBA session. There is no shared admin key or public admin bootstrap endpoint. Platform account disable immediately revokes active sessions.

## Network boundary

The service listens on container port 8001; Compose publishes it only on `127.0.0.1:8001`. The reviewed example `deploy/nginx/api.datashield.ltd.conf.example` routes `/identity/` to the loopback service and `/api/` to RegIntel, enforces HTTPS, and rate-limits Identity auth routes. Install it only after DNS/TLS/ICP prerequisites are verified. It sets `X-Forwarded-For` to the observed peer; the Identity rate limiter reads the right-most address. Do not expose ports 8000/8001 or PostgreSQL directly to the Internet. The desktop client requires verified HTTPS and stores session tokens in Windows Credential Manager.

## Local validation

```sh
IDENTITY_DATABASE_URL=sqlite:////tmp/datashield-identity.db \
  python -m alembic -c alembic-identity.ini upgrade head
```

This migration uses `IdentityBase` metadata only; it does not import the tenant or Cloud RegIntel metadata.
