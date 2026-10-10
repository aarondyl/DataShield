# DataShield Cloud 生产配置与 Secret 文件

部署入口仅在 `/opt/datashield/secrets/` 创建缺失的 `cloud.env` 和 GHCR pull token，并复用 `/opt/datashield-cloud/secrets/` 中已有的数据库/API Secret。不会覆盖、迁移或改变已有 Secret 所有权。新配置目录权限为 `0700 root:root`，`cloud.env` 与 GHCR token 为 `0600 root:root`；Docker Compose 由受限 root-owned 部署程序运行。不得将这些文件加入 GitHub Actions、镜像构建上下文或命令行参数。

## 配置文件

首次由服务器管理员运行 `deploy/prepare-cloud-secrets.sh` 后会创建：

`/opt/datashield/secrets/cloud.env`

该文件从 [`cloud.env.example`](cloud.env.example) 创建，仅含非 Secret 设置。请在服务器上编辑以下字段：

- `IDENTITY_SMTP_HOST`：SMTP 服务主机名。
- `IDENTITY_SMTP_PORT`：通常为 `587`（STARTTLS）或邮件服务商要求的端口。
- `IDENTITY_SMTP_USER`：SMTP 用户名。
- `IDENTITY_EMAIL_FROM`：验证邮件发件地址。
- 如邮件服务商不支持 STARTTLS，按服务商配置 `IDENTITY_SMTP_STARTTLS`；默认启用。

不要在该文件写 DeepSeek API Key、数据库密码、SMTP 密码或 registry token。

部署管理员应通过已批准的 Simple Application Server root 管理渠道，在仓库版本目录运行一次 `sudo bash deploy/install-cloud-host.sh`。该安装步骤先核实 Compose Project `source` 下现有 PostgreSQL 容器健康状态、`source_cloud_postgres_data` 挂载、Compose 文件映射、数据库网络、Cloud 容器健康状态及 8000 端口映射，并确认 80/443/8001 空闲；预检失败时不改主机。通过后只建立受限部署 wrapper、缺失的非 Secret 模板和空 Secret 占位文件；不会停止容器、重建数据库卷或覆盖已有 Secret。不会在 `/opt/datashield` 创建一个新的 Compose project。

## 独立 Secret 文件

管理员通过服务器安全终端分别填写这些 root-only 文件，不要在 shell 命令行参数中传值，也不要启用 `set -x`：

| 文件 | 内容 | 用途 |
| --- | --- | --- |
| `/opt/datashield-cloud/secrets/postgres_password` | PostgreSQL 初始化管理员密码 | PostgreSQL Compose 服务 |
| `/opt/datashield-cloud/secrets/cloud_database_url` | Cloud 数据库连接串，用户为 `datashield_cloud` | RegIntel 数据库 |
| `/opt/datashield-cloud/secrets/cloud_admin_token` | 高熵随机 Bearer token | 限制法规采集/管理 API |
| `/opt/datashield-cloud/secrets/identity_database_url` | 独立 Identity 数据库连接串及专用账户 | 用户身份数据库 |
| `/opt/datashield-cloud/secrets/identity_smtp_password` | SMTP 密码或服务商 App Password | 注册/找回账户邮件 |
| `/opt/datashield-cloud/secrets/identity_llm_api_key` | DeepSeek 服务端 API Key | Cloud LLM Gateway |
| `/opt/datashield/secrets/ghcr_pull_token` | GitHub fine-grained PAT，`read:packages` 权限 | 私有 GHCR 镜像拉取 |

两个数据库连接串必须指向同一 PostgreSQL 服务中的不同数据库/角色，建议使用 `postgresql+psycopg://用户名:URL编码密码@postgres:5432/数据库名`。PostgreSQL 初次初始化时使用 `datashield_cloud` 数据库角色；Identity 应由管理员在 PostgreSQL 中单独创建数据库和最小权限角色后填写自己的连接串。特殊字符必须按 URL 规则编码。不要把这些示例格式中的占位字符串直接当作密码使用。

`cloud_database_url`、`identity_database_url` 和 `postgres_password` 不得互相复用。Identity 数据库应在 PostgreSQL 中单独建立数据库和最小权限登录角色；不得将租户业务表迁入 Identity 库。

完成后验证：

```sh
sudo stat -c '%a %U:%G %n' /opt/datashield/secrets /opt/datashield/secrets/cloud.env /opt/datashield/secrets/ghcr_pull_token /opt/datashield-cloud/secrets/identity_llm_api_key
```

预期目录为 `700 root:root`，文件为 `600 root:root`。不要用 `cat`、`env`、`docker inspect` 或 `docker compose config` 输出 Secret 内容。

完成 Secret 录入后，以交互式安全终端运行 `/usr/local/libexec/datashield-cloud/check-cloud-config.sh`。检查器只输出缺少/权限错误的变量名，不输出值。`GHCR_PULL_USERNAME` 应是创建私有镜像拉取 token 的 GitHub 用户名。私有 GHCR 拉取 token 需要 `read:packages` 权限；保存在 `/opt/datashield/secrets/ghcr_pull_token`。以后换 token 时使用 root 管理终端就地编辑该文件，保持 `root:root 0600`，不要在命令参数、Actions 日志或聊天中传递 token。
