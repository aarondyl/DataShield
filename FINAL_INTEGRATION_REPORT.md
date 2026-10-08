# DataShield 最终集成报告

状态：**BLOCKED**。代码、自动化和隔离 Cloud 已推进；Windows 全项实机、阿里云可信 HTTPS、已审核现行法规及完整真实环境联调尚未完成，最终发布未批准。构建成功不等于产品验收完成。

本轮日期：2026-10-09（Asia/Shanghai）。本报告与后续文档提交不会改写安装包中的来源记录。

## 代码基线与修复

- 最新 main：`b24f9ec6d583fcaf112b1fbe2d03c0b9451e2906`，包含 Cloud PR #18（`7b25b667`）和 Desktop PR #16。
- 独立 worktree：`DataShield-integration`；分支：`release/integration-v0.1.0`。原工作目录改动保留。
- 本轮候选代码来源：`79d1c513203dccb1a8d5d9cd3d7f15d83106c524`，版本 `0.1.0`。新增集成 PR 尚未获批合并。
- 修复首次入库没有事件导致 Desktop 无法同步首版法规的 P0；`initial_import` 表示资料库基线，不代表新立法。
- 修复官方英文 HTML 实体和独立条号解析，拒绝重复条号；英文来源自动使用英文义务抽取。
- 修复同步页面版本与停滞分页校验，失败保持事务和缓存，返回可恢复错误。
- Local 每次启动生成新 token；正常退出清理属于当前进程的描述文件；Rust 拒绝零端口。
- 欢迎页隐私按钮可操作；动态和证据详情说明来源、未核验摘要、演示数据、画像推断与 AI 模拟边界。
- 增加 `SHA256SUMS.txt`，发布前核对固定来源、当前 main、安装器名称和 SHA256。

## 本轮自动化结果

历史交接 PASS 不计入以下结果。

| 检查 | 本轮结果 | 可复核证据 |
| --- | --- | --- |
| 后端全量 | PASS，328 项；本机 47、CI 34 项弃用警告 | `docs/integration-evidence/backend-junit.xml`；RC validate |
| Desktop 交互与词条 | PASS，14 项；生产构建 PASS；npm audit 0 漏洞 | 新 Windows CI 的对应步骤；本机复测 |
| Cloud 合同子集 | PASS，14 项（含官方 HTML 和首版同步回归） | 本机独立子集复测；Cloud CI |
| Cloud PostgreSQL/pgvector migration、表隔离、镜像构建 | PASS | [Cloud CI](https://github.com/aarondyl/DataShield/actions/runs/37823528147) |
| 完整 PostgreSQL 业务迁移和 smoke、SQLite 迁移、Web 构建 | PASS | [Product Twin CI](https://github.com/aarondyl/DataShield/actions/runs/37823533729) |
| Rust Bridge、打包 sidecar、NSIS 及安装目录 smoke | PASS：Rust 4 项；NSIS 构建及静默安装后 smoke 通过 | [Windows RC](https://github.com/aarondyl/DataShield/actions/runs/37823520025) |
| Web frontend 依赖审计 | 未通过漏洞门禁：7 high、5 moderate | 属于独立 Web 项目，不进入该 Desktop frontend 或 Cloud 镜像 |

API v1.0 主版本兼容、Cloud/Local/Web 路由边界、Local 只能 SQLite、Cloud-only migration 不创建私有表、事务提交 cursor/cache/materialization/task、离线恢复、Tenant 归属、Finding 证据快照、整改状态、反馈确认与应用、新 Twin 与关联重新分析已有自动化覆盖。

## Windows Installer

- 构建来源：`79d1c513203dccb1a8d5d9cd3d7f15d83106c524`，指定完整 SHA 重新构建；此前被修复取代的 RC 已取消，不作为最终产物。
- [CI Run](https://github.com/aarondyl/DataShield/actions/runs/37823520025)，发布开关 `publish_approved=false`。
- Artifact：`DataShield-Windows-Installer`，ID `11570279273`，压缩体积 35,471,891 字节；安装器 `DataShield_0.1.0_x64-setup.exe`。构建、校验文件生成和上传均成功；实际下载校验仍在进行。
- Artifact ID、下载路径、大小及 SHA256：待本轮构建完成后填写并实际下载复核。
- 正式 Release：**未创建**；Actions Artifact 不是 Release Asset。
- 发布说明：[中英文草案](docs/DESKTOP_RELEASE_NOTES.md)。最低要求 Windows 11 x64、WebView2 Runtime；安装包未 Authenticode 签名，不启用安全自动更新。
- 已存在的旧 `v0.1.0` 包名为 `DataShield.Setup.0.1.0.exe`，不是本轮 Tauri 候选，不用作本轮成功证据。

## Windows 11 实机

通过本机 PowerShell 确认 Windows build `10.0.26200.0`，执行 token 为非管理员，存在 Explorer 会话；未发现现有 DataShield 进程或默认 SQLite；另发现系统已注册旧 Electron 版 `DataShield 0.1.0`，位于 `C:\Program Files\DataShield`。本轮不覆盖或卸载该版本，Tauri 候选使用独立安装目录。能访问 PowerShell 不等于 GUI 业务通过。

本轮实际安装、GUI、语言、sidecar 启停/token、持久化、卸载/升级结果：待安装器生成后逐项记录。真实 Cloud 未就绪前，HTTPS 同步及后续官方法规业务链不得标为 PASS。操作矩阵见 [Windows 11 验收](docs/WINDOWS_11_ACCEPTANCE.md)。Windows 完整重启及用户人工反馈尚未完成。

## 隔离 Cloud 与 ECS 状态

- 独立本机 Compose project：`datashield-integration-20261009`，临时 Secret 位于仓库外，loopback `127.0.0.1:18080`，未操作现有其他容器。
- Cloud 来源与候选代码一致；镜像 digest：`sha256:518f906e58b19df5ab092842332d02b8d08f0cc3c2ff616ccd119ea6d707a38c`。
- 镜像离线归档已准备；SHA256：`c2afafaef1469ac318dcb180f065db8ca0cb6bf633da0ad618f5b814c94a6679`。仅是部署审批材料，尚未上传 ECS。
- Health PASS：`status=ok`、`db=postgresql`；Cloud migration `c0001`、pgvector PASS，12 个公共法规/迁移表，私有公司/产品/Finding/Feedback/Remediation 表缺席。
- API v1.0 header PASS；请求主版本 2 得到 426；私有路由 404；未授权 operator 写入 401；首版 event/bundle 可下载；不变内容重抓 `NO_CHANGE`。
- 有数据恢复演练 PASS：独立恢复库 113 article、578 requirement、1 event，revision 和规范化哈希一致。备份受限保存在临时环境；生产备份加密、异机保存及批准仍待完成。
- Worker/scheduler 保持关闭。一次隔离观测 Cloud 约 100 MiB、PostgreSQL 约 68 MiB，仅代表该负载，不能作为生产容量承诺。
- ECS 仅做只读检查：SSH 成功；总内存 1674 MiB、可用 1297 MiB、swap 2047 MiB；Docker 24.0.9、Compose 2.26.1；未检测到 80/443；`deploy` 无 Docker socket 权限，sudo 需要密码。
- **实际 HTTPS Cloud API：尚未部署、未验收。** `api.datashield.ltd` 在 ECS 无法解析；本机请求也未得到可验证的健康 TLS 响应。它是候选地址，不提供虚假实际服务链接。
- ECS 文件/服务、Secrets、迁移已分别提出审批；DNS、TLS、官方语料和公开服务须另行批准。[生产方案](docs/PRODUCTION_CHANGE_PLAN.md)。

## 真实法规核验

直接获取 [EUR-Lex 官方原始文档](https://eur-lex.europa.eu/eli/reg/2024/1689/oj/eng)，获取时间 `2026-10-08T18:06:00.332898+00:00`，原始 HTML 1,538,648 字节，SHA256 `6ea378420e63ff29aef7303f637c0cf57ad67fe7463b9b8e917549a46d83b4b4`；技术规范化 SHA256 `19439df728ce7bc3eafc74f645a1d3bdb0965429272f72a0bfdc3dea20c99dc8`。

在干净的隔离 Cloud 中技术导入 113 条文章、578 条规则抽取义务、512 chunk、1 首次入库事件；没有导入生产。来源明确标为“未人工核验/2024 原始版本”，暂停轮询。官方页面另提供现行整合版本入口；本次原始文本不能宣称为已核验现行语料。附件没有自动抽取义务。

区分：官方原始文件已获取；现行性、生效日期和全文人工核验未完成；义务摘要未经人工复核；仓库 `DEMO SUMMARY` 仍是演示数据；Twin 是用户事实或静态推断；反馈/整改/Agent 默认是确定性模拟模型。真实 AI Gateway、安全 BYOK、Ollama 未提供，UI 和 Notes 已明示。模拟闭环不算真实 AI 合规分析。

## Desktop ↔ Cloud 业务链

测试夹具链 PASS：实际 Cloud TCP HTTP 路由 → bundle → Local SQLite → Requirement → Local Tenant Agent → Finding → Evidence → Remediation 创建、批准与拒绝 → 中文 Feedback → 确认/应用 → Twin 新版本 → Reanalysis → Today；Cloud 停止后同步失败，法规、原 Finding 和新 Twin 仍保留。

以上使用明确的测试夹具、HTTP 和 mock。官方原始文档入库、事件和 bundle 技术验证独立报告，不把它与夹具业务链拼接成“真实端到端 PASS”。**已审核法规 → 阿里云可信 HTTPS → 安装后的 Windows Desktop → 完整业务链：未执行。**

## 问题分级与 Release 门禁

| 优先级 | 状态 | 问题 |
| --- | --- | --- |
| P0 | 已修复并回归 | 首次法规入库无同步事件 |
| P0 | 阻断 | ECS HTTPS 尚未部署；生产各项授权、域名及备案状态缺失 |
| P0 | 阻断 | 现行官方法规、全文/义务人工核验及生产导入未完成 |
| P0 | 阻断 | Windows 全项及实际 HTTPS 完整业务验收未完成 |
| P1 | 待核验 | Windows 构建已通过；GUI、完整重启、升级及卸载的数据行为待核验 |
| P1 | 已明示限制 | 真实 AI Gateway、安全 BYOK、Ollama 未提供；不能宣传完整真实 AI 产品 |
| P1 | 已明示限制 | 安装包未签名，异常强制终止/系统崩溃清理行为需进一步验收 |
| P1 | 待生产准备 | 生产 registry/备份留存、受控提权、公开 API 限流与观测；GitHub `desktop-release` Environment 尚未配置审批保护 |
| P2 | 已明示限制 | 手动更新；安全自动 updater 未实现 |
| P2 | 独立 Web 风险 | Web build 依赖审计存在漏洞，未部署本次 Cloud/Windows 的 Web 项目 |

Release 目标 `desktop-v0.1.0`，首次 Pre-release。必要验收通过后申请一次最终发布批准；获批后由代理执行，不把上传工作交给用户。必须使用经批准的 main 固定提交重新构建，发布 `DataShield_0.1.0_x64-setup.exe`、`SHA256SUMS.txt` 和中英文 Notes，实际下载资产复核。

当前结论 **BLOCKED**；没有对外发布或修改生产 ECS/Secrets/DNS/TLS/数据库，也没有合并集成 PR。

简体中文操作说明：[DataShield 使用教程](docs/DATASHIELD_USER_GUIDE_ZH.md)。
