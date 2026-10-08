# DataShield Desktop v0.1.0 — Windows 预发布

默认简体中文，支持即时英文切换。包含本地工作区、产品画像、公开网站与授权本地仓库理解、法规同步、合规发现与证据、人工整改审批、反馈修正及关联重新分析、真实今日待办。

产品资料保存在本机 SQLite。法规通过 HTTPS 拉取，不直接连接 Cloud 数据库。当前默认 AI 为明确标记的确定性模拟模式，不代表真实 AI 合规结论；默认 Cloud AI Gateway、BYOK、Ollama 设置及安全自动更新尚未提供。

Windows 11 x64 用户下载安装包，无需另装 Python、Node 或 Docker。采用当前用户 NSIS 安装；首次安装可能需要联网安装 Microsoft WebView2 Runtime。运行 `Get-FileHash .\DataShield_0.1.0_x64-setup.exe -Algorithm SHA256`，与随附 `SHA256SUMS.txt` 核对，然后双击安装、启动 DataShield、创建工作区，在设置中填写经过验收的 HTTPS Cloud 地址并同步法规。

本轮集成补齐 `SHA256SUMS.txt`，每次启动重新生成 Runtime Token，正常退出时清理属于当前进程的运行时凭据文件。发布工作流检查来源为当前 main、安装器名称及 SHA256，Desktop 发布不调用 Cloud 部署。

用户数据存于 `%LOCALAPPDATA%\DataShield`。升级前退出软件并备份此目录，安装新版后检查工作区；卸载后需自行确认数据保留行为。未启用安全自动更新，更新方式为手动下载并安装经过批准的新版本。

已知限制：安装包尚未进行 Authenticode 签名；Windows 可能提示未知发布者。网站/仓库理解为静态提取，整改批准仅接受建议，不自动执行或判定合规。模拟分析、推断画像、未核验摘要、演示语料与官方法规应分别识别，演示语料不可作为正式依据。首次公开发布必须在 Windows 实机、真实 HTTPS 和官方语料验收完成且用户批准后执行；本文件当前为 Release Notes 草案。预发布不构成法律建议。

## English

Chinese-first Windows Desktop with instant English switching: local workspaces, append-only Product Twin, public website and authorized repository understanding, regulatory sync, findings and evidence, human-reviewed remediation, feedback correction, scoped reanalysis, and live Today tasks.

Private product data remains in local SQLite. Public regulations are pulled over HTTPS. The default AI is a clearly labeled deterministic mock, not a real AI compliance assessment. Cloud AI Gateway, secure BYOK, Ollama settings, and signed automatic updates are not available in this release.

Requires Windows 11 x64 and Microsoft WebView2 Runtime (the first installation may download it). No Python, Node, or Docker installation is required. Verify `DataShield_0.1.0_x64-setup.exe` against `SHA256SUMS.txt`, install for the current user, create a workspace, configure the accepted HTTPS Cloud endpoint, and sync regulations.

This integration adds a checksum manifest, rotates runtime credentials on each start, and removes the current process's descriptor on normal exit. Publication checks the main commit and asset checksums, with no Cloud deployment steps. The installer is not Authenticode signed. Understanding uses static extraction; remediation approval does not execute changes. Demo corpus and unverified summaries are not official legal evidence. Back up `%LOCALAPPDATA%\DataShield` before upgrading. Updates require manually downloading and installing an approved release. These notes remain a draft until Windows, HTTPS and official-corpus acceptance and user approval are complete. This pre-release is not legal advice.
