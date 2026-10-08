# Cloud / Deployment 集成交接

2026-10-09 总集成复核补充：下文是原 Cloud PR 的历史交接，本轮独立复测和 Windows 构建结果以 `FINAL_INTEGRATION_REPORT.md` 为准。总集成修复了首次法规入库无法进入 Desktop 同步的问题，新增 `initial_import` 基线事件；修复英文官方 HTML 实体解码、英文抽取语言选择、重复条号以及不兼容或停滞的同步页面处理。API 主版本仍为 v1.0。

已在隔离 PostgreSQL/pgvector 环境抓取并技术导入 EUR-Lex 原始文档；官方来源可访问不等于现行版本、全文及抽取义务已经人工核验。该语料没有获准生产导入。生产审批方案见 `docs/PRODUCTION_CHANGE_PLAN.md`。

## 结论

**BLOCKED — 不具备生产验收或公网发布条件；具备进入总集成的受控代码与本地 Docker 验收条件。**

本 PR 未操作 ECS、DNS、防火墙、TLS、生产数据库或生产 Secret。PR #18 是独立可审查变更，不能作为部署授权。北京 ECS 上 `datashield.ltd` 的适用备案、受信任 TLS 证书和经核验法规语料完成前，`api.datashield.ltd` 不得公开提供 API。

## 已验证：本地临时 Docker

在临时的 Compose project 中，Cloud 容器使用 `backend/Dockerfile.cloud`、Cloud Alembic 链和 `pgvector/pgvector:pg16` 启动。验证结果：

- `/api/health` 返回 `status=ok`、`db=postgresql`。
- `alembic -c alembic-cloud.ini upgrade head` 创建 `alembic_version_cloud`、`vector` extension 和 RegIntel 表；未创建 `companies`、`products`、`findings`、`remediations` 或 `feedback`。
- `/api/v1/sync/events` 返回稳定的空 v1 cursor page；容器已清理。
- Python 集成测试覆盖 Cloud HTTP event/bundle → Local SQLite materialization → local Finding，以及同步 cursor、缓存原子提交和离线恢复行为。

这不是 ECS、Windows Desktop、真实 HTTPS 或真实法规语料验收。

## Cloud API v1 合同

公共只读 Desktop 面：

- `GET /api/health`
- `GET /api/v1/regulations`、`GET /api/v1/regulations/{id}`、`GET /api/v1/regulations/{id}/versions`
- `GET /api/v1/requirements`、`GET /api/v1/requirements/{id}`、`GET /api/v1/legal-units/{id}`
- `POST /api/v1/legal-search`
- `GET /api/v1/changes`、`GET /api/v1/changes/{id}`、`GET /api/v1/events`、`GET /api/v1/events/{event_id}`
- `GET /api/v1/sources`、`GET /api/v1/ingestion-runs`
- `GET /api/v1/sync/events?cursor=&snapshot_cursor=&limit=&jurisdiction=`
- `GET /api/v1/sync/events/{event_id}/bundle`

响应添加 `X-DataShield-Api-Version: 1.0`。客户端发送不兼容主版本会获得 `426` 和支持版本。同步 cursor 以单调事件 id 和固定 snapshot 分页；同一页 bundle 必须完整且事件不得重复，Local 在同一 SQLite transaction 中写法规、cursor 和待重分析任务。网络失败不会删除本地缓存。

`POST /api/v1/sources/{id}/ingest` 是 Cloud operator 写接口：仅 `RUNTIME_MODE=cloud` 时接受服务器 Secret 中的 `Authorization: Bearer <cloud_admin_token>`。没有配置 token 时返回 `503`，错误 token 返回 `401`。该 token 不属于 Desktop、Release 或客户端配置。Cloud runtime 只装载 health 与 RegIntel router，不装载租户、Product Twin、Finding、Feedback 或 Remediation routes。

## 镜像、迁移与 Compose

```bash
# 仅在获批的非生产或生产 deploy host 执行；生产必须使用 digest，不执行 build。
export CLOUD_IMAGE='registry.example/datashield-cloud@sha256:REPLACE_WITH_APPROVED_DIGEST'
export CLOUD_SECRETS_DIR=/opt/datashield/secrets
docker compose -f docker-compose.cloud.yml pull
docker compose -f docker-compose.cloud.yml up -d --no-build
docker compose -f docker-compose.cloud.yml ps
curl --fail --silent --show-error http://127.0.0.1:8000/api/health
```

Cloud image entrypoint exclusively runs:

```bash
alembic -c alembic-cloud.ini upgrade head
```

Never run generic `alembic upgrade head` against Cloud PostgreSQL. Migration failure prevents Uvicorn from starting; leave the existing running digest in place by first running the candidate as a separate, loopback-only Compose project or maintenance instance. Only repoint the reverse proxy after health and migration/schema checks succeed.

`CLOUD_SECRETS_DIR` must be a `deploy`-only `0700` directory containing `postgres_password`, `cloud_database_url` and random `cloud_admin_token` files. PostgreSQL has no host port and is on `cloud_database` (internal). Cloud defaults to `127.0.0.1:8000`, has a 550 MiB limit; PostgreSQL has 700 MiB. This fits the 1.6 GiB RAM + 2 GiB swap host only when no independent worker runs; leave `SCHEDULER_ENABLED=false`. Docker 24.0.9 and Compose 2.26.1 support the used Compose features (file secrets, health dependencies, memory limits, local log driver); validate `docker compose config` on the ECS before rollout.

## Reverse proxy / DNS / TLS (after approval only)

1. Confirm required Beijing ICP/备案 status and that the domain is eligible to serve the API. Do not publish a DNS record before this gate.
2. Point `api.datashield.ltd` A/AAAA only to the approved ECS address; keep port 8000 firewall-private/loopback.
3. Install Nginx or Caddy from the approved OS repository, obtain a trusted ACME certificate after DNS and eligibility are ready, and redirect HTTP to HTTPS. Do not use self-signed certificates or disable Desktop TLS verification.
4. Proxy only loopback Cloud, set short request/time limits, and pass no operator credential from proxy config.

Example Nginx server block after the certificate exists:

```nginx
server {
  listen 443 ssl http2;
  server_name api.datashield.ltd;
  ssl_certificate /etc/letsencrypt/live/api.datashield.ltd/fullchain.pem;
  ssl_certificate_key /etc/letsencrypt/live/api.datashield.ltd/privkey.pem;
  location / {
    proxy_pass http://127.0.0.1:8000;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_connect_timeout 5s;
    proxy_read_timeout 30s;
  }
}
```

## Backup and rollback

- Before an approved migration, create and verify an encrypted, access-controlled logical backup from inside the PostgreSQL container: `pg_dump -Fc -U datashield_cloud datashield_cloud > approved-backup.dump`. Store it off-host according to retention policy; test `pg_restore --list` and a restore to a non-production database.
- Record deployed Git commit SHA, image digest, Compose config checksum, migration revision, backup object/version and UTC timestamp in the deploy change record.
- Roll back application code by restoring the prior approved immutable image digest and `docker compose ... up -d --no-build`; do not run Alembic downgrade against shared production data automatically.
- If a schema change is not backward-compatible, restore the verified backup into a replacement database and bring up the matching prior image after explicit incident approval.

## Real regulation import gate

`backend/data/regulations` is labelled `DEMO SUMMARY` and is prohibited as production corpus. First production sources must be approved official publications (for example EUR-Lex / Chinese government authority pages), with legal/content review that records canonical URL, authority, retrieval time, original artifact checksum, normalized-text checksum, parser version, reviewer and effective dates. Import into a non-production Cloud database first; manually inspect source, version, legal-unit, requirement and event counts before authorizing production ingestion. Never claim public data freshness merely because the scheduler completed.

## CI / deployment boundary

- `Cloud RegIntel validation` runs Cloud-only PostgreSQL/pgvector migration, confirms Cloud tables and the absence of private tables, runs Cloud contract/sync tests, and builds only `backend/Dockerfile.cloud` with the Git SHA tag.
- Existing Desktop workflow builds an installer artifact only; it has no ECS credentials or deployment step.
- `test-ssh.yml` is read-only and manually dispatched; no repository workflow automatically deploys to ECS.
- A future deployment workflow must be `workflow_dispatch` only, use a protected GitHub Environment with required reviewers, accept only an image `@sha256` digest plus recorded commit SHA, and execute the approved change procedure above. It is intentionally **NOT IMPLEMENTED** here because its environment protection, registry and production Secrets require owner approval.

## Open issues

| Priority | Status | Required owner action |
| --- | --- | --- |
| P0 | BLOCKED | Complete ICP/备案, trusted TLS, controlled ECS rollout and genuine Windows Desktop → HTTPS Cloud acceptance. |
| P0 | BLOCKED | Approve and ingest reviewed official regulation source artifacts; current demo corpus is not valid. |
| P0 | OPEN | Configure protected production Environment, registry and deployment/backup retention policy before any deploy workflow is enabled. |
| P1 | OPEN | Add rate limiting/WAF and production observability after public exposure is approved. |
| P1 | OPEN | Exercise restore drill and image rollback on a non-production ECS-equivalent host. |
| P2 | NOT IMPLEMENTED | Automatic source polling/worker scaling; intentionally disabled for the current 1.6 GiB host. |
