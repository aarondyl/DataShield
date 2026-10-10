# DataShield Desktop v0.2.0-rc.4 — Windows 预发布

## 本版本

本预发布版修复 Windows 安装版的 Desktop renderer 路径及重复 React 加载问题。

**Cloud 功能尚未上线：** 当前公共 Cloud API 的 DNS/HTTPS 入口未配置，Identity 服务及法规数据库尚未切换上线。Cloud 登录、法规同步和 Cloud AI 暂不可用。可使用离线工作区及已安装的 Ollama；只有实际显示来源和引文的检索结果才视为法规证据。

恢复 DataShield 中文优先的桌面体验，支持简体中文和英文，包括版本选择、账户入口、产品引导、Today、法规监控与资料库、Finding 与证据、整改、反馈、Product Twin、工作区和设置。

产品资料、画像、Finding、证据、整改和反馈默认保存在本机 SQLite。法规可通过 HTTPS 同步并缓存到本机；法规同步不会上传私人产品资料。DataShield Cloud 登录、组织与成员角色由独立身份服务管理。Cloud AI 经用户选择并确认后会把当前分析所需上下文发送至 Cloud。用户也可配置 OpenAI-compatible BYOK 服务或本机 Ollama；BYOK 凭据保存在 Windows Credential Manager。

Cloud 登录、Cloud AI 和法规同步需要已运行并正确配置的 DataShield Cloud 服务。Cloud API 默认地址为 `https://api.datashield.ltd`。如果该服务尚未对你的账户开放，可以先使用离线工作区；不得将离线工作区视为 Cloud 账户。

AI 输出与自动提取内容应由用户核验，不是法律意见。法规原文来源及核验状态在产品中分别呈现。

## 系统要求

- Windows 10 1809 或更新版本，或 Windows 11，64 位 x64。
- Microsoft Edge WebView2 Runtime。Windows 11 通常已包含；若系统提示，可安装 Microsoft 官方运行时。
- 足够磁盘空间用于本地数据库、法规缓存和附件。

## 安装与更新

下载 `DataShield_*_x64-setup.exe` 并用同目录 `.sha256` 文件校验。运行安装程序并按提示操作。更新时运行较新版本安装包；本地数据库位于用户数据目录，更新会保留该目录。卸载前请备份本地数据。

## 首次使用

启动后选择开发者版或企业版。可注册/登录 Cloud 账户，也可创建离线工作区。添加产品并输入产品描述、公开网站或有权访问的本地仓库。审阅事实及来源，确认 Product Twin 后同步法规、运行分析，并检查 Finding、证据和整改建议。通过反馈修正画像后可重新分析。

设置中的 AI 模型可选择 DataShield Cloud、BYOK 或 Ollama。Cloud 模式要求 Cloud 账户和管理员已配置模型服务；BYOK 需要兼容的模型 API 地址、模型名和个人 API Key；Ollama 需要本机 Ollama 服务及已下载模型。发送上下文至远程模型前请阅读并确认界面提示。

此版本为预发布版本。已在 Windows 上完成人工安装、升级、启动与首页显示冒烟验收；未完成联网 Cloud 业务流程验收。AI 输出与自动提取内容不是法律意见。

## English

DataShield Desktop v0.2.0-rc.4 restores the Chinese-first desktop experience with Simplified Chinese and English, edition selection, account entry, product onboarding, Today, regulation monitoring and library, findings and evidence, remediation, feedback, Product Twin, workspace, and settings.

Product details, Twin, findings, evidence, remediation, and feedback are stored in local SQLite by default. Regulations can be synchronized over HTTPS and cached locally; syncing regulations does not upload private product data. Cloud accounts, organizations, and member roles are managed by the separate Identity service. Cloud AI sends the context needed for the selected analysis only after user selection and consent. Users may also configure an OpenAI-compatible BYOK service or local Ollama. BYOK credentials are stored in Windows Credential Manager.

Cloud is not live in this release: the public API DNS/HTTPS endpoint is not configured, and the Identity service and regulation corpus have not been switched on. Cloud sign-in, regulation sync, and Cloud AI are unavailable. Offline workspaces and locally installed Ollama remain available. Treat legal evidence as present only when the app displays actual sources and citations. The default API URL is `https://api.datashield.ltd`. An offline workspace is available when Cloud is unavailable and is not a Cloud account.

AI output and automatically extracted content require human review and are not legal advice. The product distinguishes source text from review status.

### Requirements and installation

64-bit Windows 10 version 1809 or later, or Windows 11, and Microsoft Edge WebView2 Runtime. Download `DataShield_*_x64-setup.exe`, verify it with the accompanying `.sha256` file, and run the installer. An in-place update preserves the local database in the user data directory. Back up local data before uninstalling.

### First use

Choose Developer or Enterprise, then register/sign in to a Cloud account or create an offline workspace. Add a product using a description, public website, or an authorized local repository. Review facts and sources, confirm the Product Twin, sync regulations, run analysis, and review findings, evidence, and remediation. Submit feedback to correct the Twin and run scoped reanalysis.

Settings offers DataShield Cloud, BYOK, and Ollama. Cloud requires an account and a configured Cloud model service. BYOK requires an OpenAI-compatible endpoint, model name, and personal API key. Ollama requires a local service and downloaded model. Review the consent notice before sending context to a remote model.

This is a pre-release. Windows installation, upgrade, startup, and home screen were manually smoke-tested; the connected Cloud workflow was not. AI output is not legal advice.
