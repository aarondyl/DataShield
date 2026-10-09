# DataShield Desktop v0.2.0-rc.1 — Windows 预发布

## 本版本包含

恢复 DataShield 原版中文优先体验：欢迎页、版本选择、账户入口、三阶段产品引导、Today、法规监控与资料库、Finding 与证据、整改和反馈、Product Twin、工作区/产品切换及设置。支持简体中文和英文切换。

Windows 桌面版当前提供本机离线工作区。产品资料、Product Twin、Finding 与证据保存在本机 SQLite；法规通过配置的 HTTPS Cloud RegIntel API 同步。离线工作区不是 DataShield Cloud 账户。Cloud 身份登录、企业成员邀请与角色管理、Cloud AI Gateway、BYOK 和 Ollama 配置尚未在此桌面预发布版启用。法规分析依赖当前本地可用的规则和服务配置，不能把确定性规则结果理解为法律结论。

## 系统要求

- Windows 10 1809 或更新版本，或 Windows 11，64 位 x64。
- Microsoft Edge WebView2 Runtime。Windows 11 通常已包含；若系统提示，可通过 Microsoft 官方安装程序安装。
- 安装和首次启动需要足够磁盘空间，用于本地数据库和法规缓存。

## 安装与更新

下载 `DataShield_*_x64-setup.exe` 后，使用同目录的 `.sha256` 文件校验 SHA256。运行安装程序并按提示安装。更新时运行新版本安装程序；它会覆盖应用文件，保留用户目录中的本地数据库。卸载前请先备份本地数据目录。

## 首次使用

启动后选择开发者版或企业版入口，创建离线工作区并添加产品。可填写产品信息、目标市场及功能，也可输入公开网站地址或本机授权仓库路径。检查并确认 Product Twin 后运行合规检查，再查看 Finding、证据和整改建议。可在法规监控页面配置 Cloud RegIntel 服务地址并同步法规；设置页会显示本地服务和数据状态。

此版本为预发布，尚未完成 Windows 11 人工图形界面验收。它不构成法律建议。

## English

DataShield Desktop v0.2.0-rc.1 restores the Chinese-first product experience: welcome and edition selection, account entry, three-stage product onboarding, Today, regulation monitoring and library, findings and evidence, remediation and feedback, Product Twin, workspace/product switching, and settings. Simplified Chinese and English are available.

The Windows desktop build currently provides a private local offline workspace. Product details, Product Twin, findings, and evidence are stored in local SQLite. Regulations sync over HTTPS with the configured Cloud RegIntel API. An offline workspace is not a DataShield Cloud account. Cloud identity sign-in, enterprise invitations and role management, Cloud AI Gateway, BYOK, and Ollama configuration are not enabled in this desktop pre-release. Analysis depends on the available local rules and service configuration; deterministic rule output is not a legal conclusion.

### System requirements

- 64-bit x64 Windows 10 version 1809 or later, or Windows 11.
- Microsoft Edge WebView2 Runtime. It is usually included with Windows 11; install it from Microsoft if prompted.
- Sufficient disk space for the local database and regulation cache.

### Install and update

Download `DataShield_*_x64-setup.exe` and verify its SHA256 using the accompanying `.sha256` file. Run the installer and follow the prompts. To update, run the newer installer; it replaces application files and preserves the local database in the user data directory. Back up local data before uninstalling.

### First use

Choose the Developer or Enterprise entry, create an offline workspace, and add a product. Enter product details and markets, or provide a public website URL or an authorized local repository path. Review and confirm the Product Twin, run a compliance check, then inspect findings, evidence, and remediation suggestions. Configure the Cloud RegIntel service URL in Regulation Monitoring and sync regulations. Settings shows local service and data status.

This is a pre-release and has not received manual Windows 11 GUI acceptance. It is not legal advice.
