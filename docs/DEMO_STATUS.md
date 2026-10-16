# DataShield 本地比赛版验收状态

更新日期：2026-10-10。记录只描述实际验证结果；本地完成的 CI/单元测试不替代安装包的 Windows GUI 验收。

| 验收项 | 状态 | 证据/剩余工作 |
|---|---|---|
| Tauri 本地 API Bridge | RC4 缺失模式标记；RC5 分支已修复 | 桌面启动时读取 Tauri `isTauri()`，再决定 HashRouter、Rust Bridge 和本地工作区；新增桌面/浏览器两种模式回归测试。等待当前 Windows 安装包作业完成后安装复验。 |
| 首次启动进入本地流程 | 已实现，待安装复验 | Desktop 根路径跳过营销页；新用户进入开发者/企业版选择，已有本机工作区直接进入 Today。 |
| 本地 SQLite | RC4 已验证可启动及持久化文件存在 | 旧版 `%LOCALAPPDATA%\DataShield\datashield.db` 有既有数据，本轮不会删除或覆盖。需在 RC5 安装后新增专用工作区、重启复验。 |
| PIPL / 数据安全法离线资料 | 有官方正文与导入流水线；首次启动导入刚实现 | 冷启动仅导入 PIPL/数据安全法，不生成示例企业或产品；来源快照保存在用户数据目录；版本标记未人工核验。需跑新增隔离 SQLite 测试并安装实测。 |
| 用户模型配置 | 已实现设置与 Windows Credential Manager 路径 | Base URL、模型、BYOK Key、同意勾选和真实推理测试已存在；Ollama 不需要 Key。Key 不进 SQLite/明文配置。当前运行的 RC4 Ollama `qwen3:4b` provider 测试曾成功；需要在修复版安装后复验。 |
| 禁止 Mock 冒充 | 已加 API 门禁 | Desktop 本地模式为 Mock 时，Tenant Agent 返回 409 并提示先配置真实模型。新增回归测试待运行。 |
| Product Twin 向导 | 已有三步页面 | 需在修复版安装后逐步点击验收。 |
| Finding 证据链 / 今日待办 | 已有业务页面与本地持久化 API | 需用真实 Ollama、新导入法规做完整分析后验收；当前不能把 RC4 的演示法条当成真实证据。 |
| Windows EXE | RC4 安装冒烟已通过；RC5 处理中 | RC4 安装包 SHA256 校验、隔离路径安装和启动窗口检查通过；RC5 Windows workflow 进行中。WSL 无 Windows Rust 工具链，需优先使用仓库 Windows Runner 生成的安装 artifact 在本机真实安装验收。 |
| Cloud / 网站 | 本地比赛版不依赖 | 不执行任何生产 Cloud 操作、不发布 GitHub Release。 |
| 比赛截图 | 未完成 | 等 RC5 实际安装后，从真实 Windows GUI 截取画像向导、Finding 证据链、Today/法规库三张图；不得伪造数据或构图替代实机。 |

演示步骤见 [`DEMO_GUIDE.md`](DEMO_GUIDE.md)，数据准备说明见 [`DEMO_DATA.md`](DEMO_DATA.md)。
