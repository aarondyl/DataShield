# Cloud 生产变更审批方案

状态：待用户逐项批准；本文件不是执行授权。服务器 `123.57.252.25`，只读 SSH 使用现有 `deploy` key；聊天凭据不进入仓库、镜像、安装包或报告。

## 已确认与前置缺口

- 阿里云实例：Alibaba Cloud Linux 4；只读检查 Docker 24.0.9、Compose 2.26.1。
- 本轮只读观测内存总量 1674 MiB，可用 1297 MiB，swap 2047 MiB。实际部署前重新读数。
- 未检测到 80/443 监听；ECS 无法解析 `api.datashield.ltd`。用户必须确认域名控制权及适用的备案状态。
- `deploy` 无 Docker socket 访问权限，非交互 sudo 需要密码。提权方式与服务器变更须批准，不能把连通性通过当作部署通过。
- Cloud runtime 只提供公共法规接口，租户数据留在 Desktop；Worker 和 scheduler 关闭。
- 当前官方原始文档、规则抽取义务未人工核验，不复制临时数据库到生产，不向公网发布这些数据。

## 审批项目与执行顺序

| 项目 | 待批准的具体动作 | 完成后核验 |
| --- | --- | --- |
| ECS 文件与服务 | 在确认不覆盖现有服务后创建 `/opt/datashield`、受限目录、固定摘要的 Cloud 镜像和独立 Compose project；批准必要提权；Cloud 仅监听 loopback，PostgreSQL 无宿主端口 | 系统资源、Compose config、镜像摘要、容器健康、监听地址 |
| 生产 Secrets | 服务器上生成随机 PostgreSQL 密码、Cloud URL 和 operator token，三个 Secret 文件仅 `deploy` 可读，目录 0700、文件 0600；不使用聊天中的服务器密码作为数据库密码 | 文件权限；不打印内容，不上传 GitHub |
| 数据库迁移 | 新库只执行 `alembic -c alembic-cloud.ini upgrade head`；如已有库先备份并在临时恢复库验证，记录备份和迁移版本 | `c0001`、pgvector、法规表和私有租户表缺席 |
| DNS | 用户确认域名及备案后，将 `api.datashield.ltd` A 记录指向该 ECS；修改前保存旧记录，避免覆盖其他应用 | 多地解析与回滚记录 |
| TLS/反向代理 | 安装经过批准的 Nginx/Caddy，获得公开信任的证书、配置仅代理 loopback Cloud，并验证 HTTPS；不关闭证书校验 | 证书域名、有效期、受信任链、HTTP 跳转、HTTPS health |
| 官方语料与公开服务 | 用户审核原文、适用版本、生效日期、完整性、摘要和导入清单后再批准生产入库及公开服务 | 官方快照和哈希、审核人、条文/义务/事件计数、Windows 联调 |

DNS/TLS 批准不包含公开未经核验语料的批准。若备案、域名或语料门禁未满足，保持 loopback，不把自签名证书交给正式 Desktop 使用。

## 镜像与资源

镜像来源与摘要、安装候选提交、临时备份恢复证据记录于 `FINAL_INTEGRATION_REPORT.md`。首选受控 registry 中的 `@sha256`，不得在生产现场 `build` 或用可变 `latest`。若采用离线传输，须另行确认经过校验的镜像 archive；`docker load` 后核对镜像 digest，再使用完全相同的 digest 启动。

Cloud 550 MiB、PostgreSQL 700 MiB 是现有上限，不是内存需求承诺。隔离环境的低占用不能推断生产高峰安全。上线时观察 RSS、OOM、磁盘、swap 和请求延迟；不启动 Worker，不开启 scheduler。保留本机端口 8000，不对 ECS 防火墙新增此端口。

## 备份、回滚与健康

1. 迁移前使用容器内 `pg_dump -Fc`，备份文件受限并加密保存到批准的异机位置；记录备份哈希、版本和时间。
2. 非生产库用 `pg_restore --exit-on-error` 演练，核对迁移 revision、法规/版本/条文/义务/事件数量及内容哈希。
3. 候选仅 loopback 启动，检查 `/api/health`、版本协商、同步 page/bundle、operator 未授权拒绝，以及 Cloud 私有路由不存在。
4. 受信任 HTTPS 和官方数据通过后，在 Windows 真正安装的 Desktop 完成全业务闭环与离线恢复。
5. 应用回滚恢复先前批准 digest 和 Compose 文件；新服务上线失败时保持旧代理目标。不得自动 `alembic downgrade` 或删除生产 volume。若必须恢复数据库，单独批准后恢复至替代库。

## 最终 Release 门禁

独立集成 PR 未获批准不合并。Windows 安装、真实 HTTPS、已审核语料和完整闭环均通过后，向用户申请一次最终批准，列明拟合并 PR、固定来源和 Pre-release 资产。批准后由代理执行合并及从 main 固定提交重建、验收、Desktop Release 工作流发布、资产下载和 SHA256 复核；不能要求用户手动上传安装包。
