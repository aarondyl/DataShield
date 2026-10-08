# DataShield Desktop 前端开发入口

本目录是 Desktop 壳与桌面 UI 的唯一新增位置；本轮不创建页面、不引入 Electron/Tauri，也不替换已有 `frontend/` Web UI。

建议技术栈：**Tauri 2 + React + TypeScript + Vite**。原因是现有 UI 已使用 React/Vite/TypeScript，可逐步复用视觉组件和类型，同时桌面壳体积较小；最终选择应在桌面团队评审后落地。

## 与 Local FastAPI 的契约

Desktop 主进程先启动：

```bash
cd backend
RUNTIME_MODE=local python -m app.entrypoints.local
```

Local 服务只监听 `127.0.0.1:18321`。启动后会在用户目录生成：

- Linux：`$XDG_DATA_HOME/DataShield/runtime.json`，默认 `~/.local/share/DataShield/runtime.json`
- Windows：`%LOCALAPPDATA%/DataShield/runtime.json`

该文件包含 `base_url`、`runtime_token` 和进程 PID。Desktop **主进程**读取它，并对每个 `/api/*` 请求附加 `X-Runtime-Token`；不得把 token 写入前端静态包、遥测、日志或远端服务。Renderer 不应自行访问 Cloud PostgreSQL，也不得上传 Product Twin 或私人证据。

健康检查 `GET /api/health` 无需 token；其他本地 API 都需要 token。Cloud 同步只允许 Local 后端调用 Cloud HTTP API。

## 可复用资产

`frontend/` 中已有 React/Vite 路由、组件、样式和 API 类型，属于旧 Web 托管 UI。Desktop 开发可有选择地迁移无服务端身份假设的组件；不要直接把 `frontend/` 当作 Desktop 应用，也不要以浏览器 cookie/`/api` 相对路径作为 Desktop 通信方案。
