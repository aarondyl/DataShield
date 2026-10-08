# Desktop–Cloud MVP 部署与验收

## 状态与上线边界

2026-10-09 总集成复核：历史交接的 PASS 不作为本轮验收结果；本轮状态以仓库根目录 `FINAL_INTEGRATION_REPORT.md` 为准。首次入库现在发布 `initial_import` 同步基线；英文官方 HTML 可配置 `parser_type=eu_english`，默认选择英文义务抽取。正文来源与摘要人工核验仍是独立门禁。

当前仓库具备可在受控环境测试的 Cloud → Desktop Local Runtime 数据路径；**尚未获准部署到阿里云，也不应公开暴露 API**。北京服务器上的 `datashield.ltd` 未完成适用的备案/上线手续时，不得把 `api.datashield.ltd` 配置为公开生产服务。不要使用自签名证书，也不要关闭 Desktop 的 TLS 验证。

现有 `backend/data/regulations` 内容在仓库 README 中标为 `DEMO SUMMARY`。因此它不能作为“真实、已核验法规数据”的生产验收证据。上线前须由法规运营人员导入、复核官方来源内容，并保存来源 URL、抓取时间与内容哈希。

## API v1 契约

Desktop 只能从 Local FastAPI 调用 Cloud；不会直连 PostgreSQL。Cloud 对 Desktop 保持只读：

- `GET /api/health`：服务与 PostgreSQL 连通性。
- `GET /api/v1/regulations`、`GET /api/v1/requirements`、`POST /api/v1/legal-search`：公共法规查询。
- `GET /api/v1/sync/events`、`GET /api/v1/sync/events/{event_id}/bundle`：增量同步；Bundle 仅含法规、版本、法条和义务。

Cloud 在 v1 响应中返回 `X-DataShield-Api-Version: 1.0`。Local 客户端可发送同名 header；不兼容的主版本返回 `426`。`POST /api/v1/sources/{id}/ingest` 是运维操作，必须使用仅保存在服务器 Secret 中的 `Authorization: Bearer` operator token；该 token 绝不能置入 Desktop、安装器、日志或 GitHub Release。

同步失败时 Local `CloudSyncClient` 保留已提交的 SQLite 缓存、标记离线并返回可恢复错误；它不上传 Product Twin、用户文件、Finding、SQLite 或 Agent 上下文。

## 受控环境部署步骤（需人工批准）

在服务器的仅 `deploy` 用户可读目录（例如 `/opt/datashield/secrets`，权限 `0700`）创建三个文件：`postgres_password`、完整 PostgreSQL URL 的 `cloud_database_url`，以及随机的 `cloud_admin_token`。以 `CLOUD_SECRETS_DIR=/opt/datashield/secrets` 传给 Compose；它们以 Docker Compose secret 文件挂载，不进入仓库、镜像、Compose 环境变量或 Actions 日志。

启动命令为：

```bash
export CLOUD_IMAGE='registry.example/datashield-cloud@sha256:经批准的镜像摘要'
docker compose -f docker-compose.cloud.yml pull
docker compose -f docker-compose.cloud.yml up -d --no-build
```

Cloud 镜像在启动前只运行独立的 `alembic -c alembic-cloud.ini upgrade head`，表版本为 `alembic_version_cloud`；不得运行通用 Alembic 链。PostgreSQL 无宿主端口、位于内部网络且使用持久化 `cloud_postgres_data` volume。两个容器有内存上限、健康检查、`unless-stopped` 重启策略和本地 Docker 日志轮转；在 1.6 GiB 服务器上不部署独立 Worker，scheduler 默认关闭。

在 DNS、备案和受信任 TLS 入口获批之前，保持 `CLOUD_BIND_ADDRESS=127.0.0.1`，仅通过 SSH 端口转发或同机反向代理进行测试。获批后由受信任的 TLS 反向代理暴露 `api.datashield.ltd`，并将 Cloud 容器保持在 loopback；Desktop 必须使用 `https://api.datashield.ltd`。

## 验收顺序

1. 在非生产 PostgreSQL/pgvector 执行 Cloud migration，确认 `/api/health` 报告 `db=postgresql`。
2. 使用经过核验的官方法规创建 `regulation.change.ready` 事件，确认 `/sync/events` 和 Bundle 可查询。
3. 从 Windows Desktop 触发 Local `/api/v1/local-regulations/sync`，检查本机 SQLite 中出现法规/义务及同步游标。
4. 对已同步义务运行本地分析，确认 Finding 的证据链接指向本地物化法规；断开 Cloud 后重复检查，本地缓存仍可读而同步返回可恢复离线状态。

第 2–4 步和 Windows 安装、正式 HTTPS、真实法规数据验证的本轮结果须逐项查看 `FINAL_INTEGRATION_REPORT.md`。实现、临时环境通过和生产验收是不同状态，不能相互替代。

## 隔离环境与批准后的执行材料

使用独立 Compose project、临时凭据及 `CLOUD_BIND_PORT=18080` 可避开已有服务；生产默认仍是 `127.0.0.1:8000`。只允许清理明确属于临时 project 的 volume，不执行全局 Docker 清理。

在 ECS 生产变更前审阅 `docs/PRODUCTION_CHANGE_PLAN.md`，分别批准服务器变更、生产 Secret、迁移、DNS 和 TLS。先准备镜像摘要、提交记录、校验文件、备份恢复结果和回滚指令；在这些材料准备好之前不请求最终发布批准。Desktop Release 工作流不执行 ECS SSH、数据库操作或 Cloud 部署。
