# DataShield Desktop

桌面容器使用 **Tauri 2**，产品界面和 Web 端共享 `frontend/` 中的 React 页面。桌面页面在 Tauri WebView 中运行，业务请求由 Rust Bridge 转发到本地 FastAPI Sidecar。

Tauri host 只负责 sidecar 生命周期、runtime descriptor 校验和受限的本地 API bridge。渲染进程只能调用 bridge，不能读取 token、`runtime.json` 或直接连接数据库。

## 当前开发与打包状态

- 开发 UI：`npm --prefix apps/desktop ci && npm --prefix apps/desktop run tauri -- dev`。
- Tauri 的 `beforeDevCommand` 会启动 `frontend/` Vite 服务；产品页面和双语资源由此构建。
- 生产安装包由 `npm --prefix apps/desktop run tauri -- build` 构建，Tauri 会先执行 `frontend/` 的 TypeScript 检查与正式打包。
- Windows CI 使用 `backend/datashield-local.spec` 打包当前 `app.entrypoints.local` 为 sidecar，再由 Tauri 生成 NSIS 当前用户安装包。
- sidecar 不包含 `.env`、SQLite、workspace、日志或 provider key；它们均不属于安装产物。
- 本机必须先有 `apps/desktop/src-tauri/binaries/datashield-local-<target-triple>.exe` 才能运行 `tauri dev/build`。该二进制由 CI 或受控构建流程生成，禁止提交。
- 目前尚未完成 Windows 干净机安装验收、签名和自动更新；CI 产物是后续验收输入，不代表已发布。

## 身份与离线模式

- 本地桌面版使用 Windows 当前用户隔离的 SQLite 工作区。工作区和 Product Twin 信息保存在本机应用数据目录，重启后继续使用。
- 当前构建未配置 DataShield Cloud 身份服务。桌面注册入口明确创建离线工作区；它不创建 Cloud 账户，也不把本机 Company ID 当作 Cloud 用户身份。
- 本地 Sidecar 的单用户模式依赖 Tauri Rust Bridge 的进程令牌，外部请求不会因离线工作区而绕过 Bridge。
- 在线 Cloud 登录、企业成员邀请/角色管理需等 Cloud 身份与组织成员服务完成部署后开放。

## 与 Local FastAPI 的契约

Desktop 主进程先启动：

```bash
cd backend
RUNTIME_MODE=local python -m app.entrypoints.local
```

Local 服务只监听内核分配的 `127.0.0.1` 随机空闲端口。启动后会在用户目录生成：

- Linux：`$XDG_DATA_HOME/DataShield/runtime.json`，默认 `~/.local/share/DataShield/runtime.json`
- Windows：`%LOCALAPPDATA%/DataShield/runtime.json`

该文件包含实际 `base_url`、`runtime_token` 和进程 PID。Desktop **主进程**读取它，并对每个 `/api/*` 请求附加 `X-Runtime-Token`；不得把 token 写入前端静态包、遥测、日志或远端服务。Renderer 不应自行访问 Cloud PostgreSQL，也不得上传 Product Twin 或私人证据。

健康检查 `GET /api/health` 无需 token；其他本地 API 都需要 token。Cloud 同步只允许 Local 后端调用 Cloud HTTP API。

## 可复用资产

`frontend/` 中已有 React/Vite 路由、组件、样式和 API 类型，属于旧 Web 托管 UI。Desktop 开发可有选择地迁移无服务端身份假设的组件；不要直接把 `frontend/` 当作 Desktop 应用，也不要以浏览器 cookie/`/api` 相对路径作为 Desktop 通信方案。

## AI 与更新契约（尚未实现）

- `DESKTOP_AI_MODE=mock` 是开发与 demo 默认值；`byok`、`local`、`cloud` 仅定义配置边界，不在本轮实现 API Key、Ollama 或 Cloud Gateway。
- Global Agent 的 provider secret 只存于 Cloud/Server secret storage。Desktop 用户自己的 API Key 未来只存 OS Keychain；DataShield Default AI 未来调用 Cloud LLM Gateway，绝不能把共享 provider key 打进安装包；本地模型未来经本机 provider（例如 Ollama）访问。
- 最终 Desktop 将使用 Tauri updater：启动或定期查询已签名元数据，提示用户确认后下载、验签、安装并重启。第一版不强制自动更新。
- 更新产物必须签名且 updater 必须验签；数据目录独立于安装目录，更新不得覆盖 SQLite 或 workspace。新版本启动时的应用迁移、迁移失败及回滚必须 fail-safe。
