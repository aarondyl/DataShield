# Desktop 资产复用矩阵

本文记录 `origin/feat/chinese-first-ux` 对 `feat/desktop-app` 的选择性复用决定。该分支是资产来源，不是当前 Cloud/Local 架构基线；所有判断以 `main` 的 Local Runtime 契约为准。

| 旧文件或模块 | 原有作用 | 决定 | 本次处理 | 风险与边界 |
| --- | --- | --- | --- | --- |
| `frontend/src/i18n/locales/zh/**` | 中文优先的产品词条 | ADAPT | 以中文词汇、页面命名和交互语气为来源，迁入 Desktop 独立的强类型词条 | 不直接把旧 Web 路由的词条当成已实现功能；法律原文不翻译为认证法规文本 |
| `frontend/src/i18n/locales/en/**` | 英文对照词条 | ADAPT | 与中文词条保持同一类型约束，作为 Desktop 的完整切换语言 | 新页面必须同时补齐，不能回退为原始 key |
| `frontend/src/i18n/index.ts` | i18next 初始化与语言检测 | ADAPT | 保留中文默认、系统语言初始化及即时切换的产品行为；不复用其依赖和实现 | 语言偏好不是密钥；runtime token 绝不进入浏览器存储 |
| `frontend/src/components/LanguageSwitcher.tsx` | 中英文切换器 | REUSE/ADAPT | 复用双按钮、即时切换的交互模式 | Desktop 使用自己的 i18n context，不依赖旧 Web 全局状态 |
| `frontend/src/components/BrandLogo.tsx` | 品牌标识 | ADAPT | 复用简洁品牌呈现思路，暂不引用旧分支的大型 PNG 资产 | 安装包图标另行准备，不能把未经审计的二进制打包工具带入 |
| `frontend/src/components/ErrorBoundary.tsx` | 渲染异常兜底 | REUSE/ADAPT | 作为 Desktop 页面错误提示的结构参考 | 不在错误日志中输出 runtime token、请求头或私有数据 |
| `desktop/main.js` | Electron 生命周期、后端拉起 | DISCARD（仅参考） | 仅参考健康检查、单实例和退出时回收 sidecar 的思路 | Electron、固定 `18321`、`taskkill` 与 PR #15 动态 socket/runtime descriptor 冲突 |
| `desktop/preload.js` | Electron IPC/token 桥接 | DISCARD（仅参考） | 改为 Rust 主进程持有 token 的受限 Tauri command | token 不能经 preload、JS 全局、localStorage、日志或静态 bundle 暴露 |
| `desktop/package.json`、构建脚本 | Electron Builder/NSIS 打包 | ADAPT | 仅参考 Windows 产物和 sidecar 的构建目标 | 不引入 Electron 或旧 `7za.exe` 二进制工具 |
| `backend/desktop_entry.py` | 旧后端桌面入口 | DISCARD | 当前权威入口为 `backend/app/entrypoints/local.py` | 旧入口固定端口、旧 CORS，且历史上曾加载 bundled provider key，违反安全边界 |
| `backend/datashield-backend.spec` | PyInstaller hidden imports 与数据收集 | ADAPT（后续 Stage 2） | 后续以 current local entrypoint 重写 spec，并仅随 sidecar 打包必要资源 | 不能包含 `.env`、API key、开发数据库或 Cloud 私有实现 |

## 本阶段的可验证边界

Stage 1 只交付可开发、可审查的 Tauri 壳与中文优先入口：它以主进程读取 PR #15 已有的 `runtime.json`，并由主进程附加短期 `X-Runtime-Token`。产品接入、Finding、整改和反馈的真实业务 API 接线会在后续 UI/集成阶段完成；本文件不把静态原型误述为业务功能已完成。
