# DataShield 演示验收状态

更新日期：2026-10-10（Asia/Shanghai）

状态仅根据本轮实际运行记录填写。源代码存在或 CI 通过不等于功能已在真实环境验收。

## 本轮真实证据

| 项目 | 状态 | 证据 |
|---|---|---|
| PR #46 部署修复 | 已合并 | Commit `7a3334233285fea9e1455104f1975947062cf7b5`；Cloud CI [Run 38041835256](https://github.com/aarondyl/DataShield/actions/runs/38041835256) 通过。 |
| Cloud、Identity、Proxy 镜像构建 | 已发布 GHCR | [Run 38041917596](https://github.com/aarondyl/DataShield/actions/runs/38041917596) 成功；发布来源 `7a3334233285fea9e1455104f1975947062cf7b5`；Compose SHA256 `ba4dccd621245498025fad82db03bde109fc89448d2d4fc1f4c227d8b88a4b6b`；Cloud `sha256:8eddf9278ab4576d3d051618f2640cbd05c4f5eccae7ea518272637549453f04`；Identity `sha256:f3aa4fa259a4a3e25d611a8f32e0724c5ac67609d08e90675b00f2a4e4c08239`；Proxy `sha256:7f5035a32dc32ced4c7a3e7ea456f0a5d4693d1e43318088850c6bb24a8beba0`。 |
| ECS 部署器及辅助脚本 | 已更新 | 使用 main 固定 Commit 的 `install-cloud-host.sh`；部署器、容器 ID、状态、发布校验、Compose 存储检查与配置检查脚本均安装为 root 所有。 |
| ECS 配置预检 | 通过 | `/usr/local/sbin/datashield-cloud-deploy preflight` 返回通过；没有显示环境变量值。 |
| 候选 stage / diagnose | 通过 | 固定 Commit 与 Compose SHA 候选已暂存；read-only diagnose 覆盖合并配置、存储身份、Cloud/Identity 数据库角色、GHCR、磁盘和内存。没有调用 deploy。 |
| PostgreSQL 备份 | 已生成并校验 | `/opt/datashield/backups/pre-demo-cutover-20261010T093952Z.sql.gz`，gzip 完整性通过；大小 9,180 bytes，SHA256 `d69ec7e79e54d044e953c7636cd4e77c7494e93293aadbc807b058eaaec7f017`；前后 PostgreSQL 容器完整 ID 与 `source_cloud_postgres_data` 卷均未改变。 |
| ECS Cloud 与 PostgreSQL | 健康（旧版） | SSH 只读检查显示 `source-cloud-1` 与 `source-postgres-1` 均 Healthy；旧 Cloud API 只绑定 `127.0.0.1:8000`。 |
| 生产数据库现有法规 | 不存在 | 只读计数：法规、版本、Legal Unit、Requirement、法规事件和来源快照均为 0；Identity 数据库当前没有 public 表。 |
| 域名 DNS | 通过 | `api.datashield.ltd` 解析到 `123.57.252.25`。 |
| 公网 HTTPS / Identity / Proxy | 未上线 | 公网 TCP 443 无服务监听，HTTPS 请求失败；Identity 与 Proxy 容器尚不存在。当前不能声称 Desktop 已连 Cloud。 |
| Windows RC4 安装包 | 安装冒烟通过 | GitHub Release `v0.2.0-rc.4` 的 EXE SHA256 校验通过；隔离路径静默安装退出码 0；启动后窗口标题为 DataShield，未黑屏。画面检查发现品牌 Logo 资源缺失，已在本分支修复 Vite 公共资源目录；修复版仍需 Windows CI 和实际安装验证。 |
| Desktop Local sidecar | 健康 | Windows 进程启动 `datashield-local.exe`；`/api/health` 返回 `status=ok, db=sqlite`。 |
| Ollama `qwen3:4b` | 实际推理通过 | Windows Ollama API 返回 `qwen3:4b`；Desktop sidecar 的 provider 测试返回 `status=ok, provider=local, model=qwen3:4b`。测试请求不含产品资料。 |
| Desktop 到 Cloud 法规同步 | 未验收 | 当前公网入口不可连接，尚未完成从 Production 下载法规并写入 Desktop SQLite。 |
| Local Tenant Agent Finding 闭环 | 未验收 | 本轮没有伪造法规或 Finding；待 Cloud 切换和实际法规同步后执行 Ollama 分析、Finding 展示及重启持久化验收。 |
| 迁移备份副本演练 | 未完成 | WSL Docker default socket 返回权限不足；没有把迁移演练改在低内存生产机上运行。Production DB 未执行迁移。 |

## 安全边界与下一步

- `CLOUD_DEPLOY_ENABLED` 保持关闭，`production-cutover.approved` 标记不存在。
- 新候选的 `stage` 与只读 `diagnose` 已通过；未调用 `deploy`、未迁移数据库、未停止或替换容器。
- 新备份 gzip 可读性已验证，但尚未在隔离数据库恢复验证；生产数据库尚无已知法规或用户数据行。
- 正式演示仍需首次切换批准。批准前不能完成公网 HTTPS、Identity 注册、Cloud 法规导入、Desktop 云同步或端到端 Agent Finding。
