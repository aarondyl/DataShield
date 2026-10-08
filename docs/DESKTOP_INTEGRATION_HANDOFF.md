# DataShield Desktop v0.1.0 集成交接

分支：feat/desktop-app。PR：https://github.com/aarondyl/DataShield/pull/16。
已同步 Cloud PR #18 后的 main（7b25b66），保留 Cloud operator credential 与 Desktop HTTPS 地址两套配置。未操作生产服务器、数据库或密钥。

## 功能验收矩阵

| 模块 | 自动化状态 | 实现及证据 |
| --- | --- | --- |
| 工作区 / Company / Product / SQLite | PASS | 复用既有本地持久化；Local Runtime tests |
| Finding / Evidence | PASS | Requirement、LegalUnit、法规版本、官方来源、正文、历史快照、真实 Twin 版本和分析引用；FindingDetail、tenant_findings tests |
| Remediation | PASS | 创建文档/代码建议、详情/历史、关联证据、人工批准与拒绝；RemediationPage、remediation API/persistence/contracts tests |
| Feedback / correction / scoped reanalysis | PASS（模拟解释器明确标识） | 原文与候选分离、澄清、确认、单独应用、失败重试、新 Twin 和 run；FeedbackPanel、feedback API/twin/reanalysis tests |
| Today | PASS | 真实任务/缺失上下文/最新检查，法规变化单列；未同步/未检查不显示全部合规；TodayPage、today tests |
| Website / Repository | PASS（静态提取） | 网站异步分析，Windows 原生目录选择及 Rust 内部授权，确认导入同一 Twin；UnderstandingPage、website/repository/facade/grant tests |
| Twin 审核 | PASS | 事实确认追加新版本并显示历史；手动输入能力/控制/市场/主体及不同状态；TwinPage、Product Twin tests |
| Cloud→Local | PASS（HTTP 契约） | HTTPS 配置持久化；来源切换不覆盖已有缓存；失败使用缓存；真实 TCP→SQLite→Finding 保留来源、主体与可信度 |
| 中英双语 | PASS（自动化） | 中文默认、即时切换、偏好持久化、键树完整，两种语言相同业务路径 |
| Windows NSIS / 实机 | PENDING | 新增完整 onedir 依赖、无控制台日志修复、sidecar 启动/PID/token 检查及 Rust tests；旧构建不代表当前 HEAD |
| AI Gateway / 安全 BYOK / Ollama | NOT AVAILABLE（明确标识） | 默认 deterministic mock，不是真实 AI 合规判断；不包含共享密钥 |
| Release workflow | IMPLEMENTED / UNPUBLISHED | 指定完整 SHA 重建、全后端及 Windows 测试、SHA256；默认不发布 |
| 自动更新 | DEFERRED | 未启用无签名 updater |

## 中文业务演示

1. 默认中文 → 创建工作区及产品 → 写入本机 SQLite。
2. 产品接入：手动事实，或网站分析/原生选择仓库；审核后确认导入。
3. 产品画像：逐项确认，查看新版本及历史；不足的市场/主体信息可补充。
4. 设置填写 Cloud 团队提供的公开 HTTPS 地址 → 法规动态同步；离线明确使用缓存。
5. 合规发现运行本地检查 → 详情阅读风险、法规正文、官方来源、证据与画像版本。当前 mock 提示明确可见。
6. 从发现生成文档/代码整改 → 审核 → 批准或拒绝；不会执行代码或自动解决缺口。
7. 原发现提交纠正 → 解释/澄清 → 确认 → 单独应用 → 新画像版本和关联重新分析。失败可重试，历史保留。
8. 返回发现/Today 查看结果。English 切换后同一路径可操作，偏好重启保留。

## 安全边界

Runtime token 只由 sidecar/Rust 持有，Renderer 不读取描述文件。Rust 校验 loopback/PID，拒绝 URL、遍历、编码路径及普通桥接调用目录授权端点。
目录授权仅当前进程有效，重启需重选；跳过链接/敏感文件，不执行或上传仓库。
Local-only 配置/缓存/目录授权不注册到 Cloud/Web。Cloud 不加载 Tenant 私有 API；同步只获取公开法规。
CONFIRMED != APPLIED；UNKNOWN != FALSE；NOT_DETECTED != ABSENT；APPROVED != EXECUTED != RESOLVED。

## 自动化回归

后端：PYTHONPATH=/tmp/datashield-deps PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest tests -q（backend）。
前端：npm test -- --maxWorkers=1；npm run build；npm audit --json（apps/desktop）。
最近后端 310 项通过、39 项弃用警告；前端 14 项（含离线缓存和模拟结果不冒充无待办）、生产构建与共享 Web 构建通过；Desktop audit 0 漏洞。最终 CI 以对应提交和 SOURCE_COMMIT.txt 为准。
Linux cargo test 缺少 pkg-config/dbus 开发环境，不能报告通过；Windows CI 已加入 Rust 安全测试。

## Windows 人工验收（尚未完成）

下载最终 CI Artifact DataShield-Windows-Installer，核对 SOURCE_COMMIT.txt 与 SHA256。
Windows 11 无 Python/Node 环境验证：安装、启动、中文业务链、English 切换、退出/重启 SQLite 持久化、离线启动、sidecar 清理、卸载/升级保留用户数据。
%LOCALAPPDATA%/DataShield/runtime.json 应为动态 loopback 和当前 PID；不要分享 token/文件。Renderer DevTools 不应含 token，退出 Desktop 后无遗留 backend。

## 待解决门禁与发布

P0：最终 Windows 构建与 sidecar 启动尚需通过，未通过不合并。
P1：Windows GUI 实机验收；真实 Provider 尚未支持，不冒充真实 AI。
P1：desktop-release.yml 不触发 Vercel/ECS，发布 desktop-v0.1.0 Pre-release 需实机验收及批准；Stable 另行批准。建议配置 desktop-release Environment 审批人。
P2：安全签名 updater、更多内部事实名称/错误细节本地化、Windows GUI E2E。

PR 保持 Draft，相关门禁全部通过才按条件授权转 Ready/合并，不绕过保护。没有发布 Release。
