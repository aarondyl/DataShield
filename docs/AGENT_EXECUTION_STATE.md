# DataShield 交付断点状态

更新时间：2026-10-09（Asia/Shanghai）

## 当前代码

- 仓库：`aarondyl/DataShield`。
- 远端 main：`eeec5a5582ff79f11b38a85a17524b9443b40293`（PR #29 合入，rc.3 固定源 Commit）。
- 本文档更新分支：`docs/rc3-release-checkpoint`。
- Desktop 版本：`0.2.0-rc.3`；中英文 Release Notes 反映已实现的 Cloud Identity、Cloud AI、BYOK、Ollama，并注明 Cloud 服务仍依赖服务端配置。
- GitHub Pre-release：<https://github.com/aarondyl/DataShield/releases/tag/v0.2.0-rc.3>。正式 Windows NSIS 构建及安装升级验证由 Release workflow `37928809124` 执行。资产包含 EXE、SHA256、源 Commit；从 GitHub 下载 EXE 后 `sha256sum -c` 校验通过，EXE 大小 36,482,778 bytes，固定源 SHA 与 main 一致。
- 发布工作流：`.github/workflows/desktop-release.yml`，固定完整 main SHA 并校验 SemVer，复用 Windows NSIS 工作流，在 Windows 实际静默安装/启动 sidecar/原位升级后创建 Pre-release。

## 已完成并验证

- PR #25 已合入：隔离的 Cloud Identity（邮箱验证注册、登录/刷新/退出、密码重置、组织/成员/RBAC、邀请及停用）与 DeepSeek JSON Gateway；AI 用量落库但不记录提示词，按账户限流。Identity 使用独立迁移和数据库配置，与 RegIntel/本地租户数据隔离。
- Desktop 经 Rust Bridge 与本地 Agent 调用 Cloud AI；Windows Credential Manager 保存凭据；明确征得远程上下文同意。默认 Cloud API 地址为 `https://api.datashield.ltd`，初始 AI 仍为离线/mock。
- Cloud 法规来源目录已包含官方 PIPL 与 DSL，原始响应归档及哈希，2 个法规版本、284 个法律单元、137 个自动提取 Requirement；内容核验状态明确为 UNREVIEWED；有启动及每日轮询。
- PR #25 GitHub CI 全绿（Backend/PostgreSQL/Identity 隔离迁移，Cloud migration/API/image，Windows sidecar/Rust Bridge/NSIS/安装及升级验证）。本地完整后端：349 passed；前端 TypeScript/Vite 构建通过。
- 旧版中文优先产品体验、Product Twin、Tenant Agent、Finding/Evidence、Remediation、Feedback/Reanalysis 已在 main；之前 Windows CI 做了安装与升级、sidecar 验收。尚无人工 Windows GUI 验收。

## 外部服务实际状态与未完成

- ECS：`123.57.252.25`，Alibaba Cloud Linux 4.0.3，RAM 1674 MiB，磁盘 40 GiB（已知剩余约 31 GiB）。GitHub Actions 现有 SSH 只允许 `deploy`。ECS 本机旧 RegIntel API 健康检查曾返回 200；无法读取 Docker/容器/Postgres，因为 `deploy` 对 Docker socket 和 `sudo -n docker` 均无权限。`/opt/datashield-cloud/secrets` 为 admin 所有且权限 700，内容未读取。
- `https://api.datashield.ltd/api/health` 此执行环境无法成功访问，因此不能声称公网 TLS/API 可用；Identity/Nginx 新路径尚未部署验证。
- 可访问 GitHub Actions secret 名称中没有 DeepSeek 或邮件配置项；没有验证线上 DeepSeek API Key、邮件发送或真实模型推理。不要把 Secret 值输出或写入此文件。
- 没有 Aliyun 管理 CLI/授权接口或可用云平台 MCP。用户给出的 ECS 密码无法用于 SSH（主机只接受公钥）；不得绕过权限限制。
- 目前 Release 仍为 `v0.2.0-rc.2`；无 rc.3 安装包和发布。不得以 Workflow/Artifact 代替 Release。
- 未完成真实 Windows→公网 Cloud→SQLite→Finding→Remediation→Feedback E2E；BYOK/Ollama 仍需真实模型配置和推理验证。

## 恢复后具体操作

1. `v0.2.0-rc.3` 已合入 main，Release 已由 `desktop-release.yml` 发布并实际下载验证；发布 SHA 为 `eeec5a5582ff79f11b38a85a17524b9443b40293`。
2. 等待用户提供已请求的受限 ECS 管理部署通道。不得绕过 deploy 权限或尝试读取 Secret 文件。
3. 管理员通过安全服务器配置 Identity 独立 Postgres DB/角色、DeepSeek 服务端密钥及邮件 SMTP；绝不向聊天或仓库写凭据。检查现有卷/DB备份及 Compose 状态，确认数据保护，再部署 Identity/Gateway/Nginx，不覆盖既有 RegIntel 数据。
4. 验证公网 HTTPS、真实注册邮件、DeepSeek Gateway 推理、RegIntel 实际法规查询/增量同步、Desktop 同步缓存，以及真实 AI 业务分析和用户反馈闭环。
5. 未经公有服务及 AI 端到端验证，不得把现有 rc.3 宣称为完整交付或 Stable。完整链路验证后应递增版本并以新的固定 main SHA 发布下一 Pre-release。

## 已知外部授权请求（已向用户提出一次，等待回复）

待本地/CI/版本候选工作完成后，若 ECS 管理通道仍不存在，仅需请求用户通过阿里云控制台配置第 4 步所述最小受限授权；无需提供服务器密码、密钥或将 Secret 发到聊天。未获得该授权时，继续保留可恢复代码状态，不宣称服务或版本已经交付。
