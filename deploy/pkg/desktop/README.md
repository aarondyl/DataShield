# DataShield 桌面版（Electron + 内嵌 FastAPI）

把 DataShield 封装为 Windows 桌面应用：Electron 负责窗口与进程管理，FastAPI 后端以
PyInstaller 打包成 `datashield-backend.exe` 随应用分发（无需用户安装 Python），
前端为 Vite + React 构建产物，通过 `file://` 加载，API 直连本机回环
`http://127.0.0.1:18321`。

## 目录结构

```
desktop/
├── package.json   # 脚本 + electron-builder 配置（appId com.datashield.app，NSIS）
├── main.js        # 主进程：单例锁、spawn/守护后端、健康检查轮询、窗口管理
├── preload.js     # contextBridge 注入 window.datashieldDesktop.apiBase
└── release/       # electron-builder 输出（安装包）

打包时通过 extraResources 带入：
resources/
├── datashield-backend/  # ../backend/dist/datashield-backend（PyInstaller onedir）
└── frontend-dist/       # ../frontend/dist（Vite 构建产物）
```

## 数据存储位置

- SQLite 数据库与法规快照副本都放在 Electron 的 `userData` 目录：
  `%APPDATA%/datashield-desktop/`（数据库 `datashield.db`，数据文件 `data/`）。
- 主进程通过环境变量 `DATASHIELD_DATA_DIR` 传给后端；首次启动时后端把内置
  法规文本拷贝到该目录（安装目录只读，必须拷到可写位置）。

## Windows 非管理员环境注意事项（winCodeSign 符号链接）

electron-builder 解压其 winCodeSign 缓存（含 macOS 签名用的 `*.dylib` 符号链接）时，
Windows 普通用户（无开发者模式/管理员）会报 `Cannot create symbolic link : 客户端没有所需的特权`
而失败，且每次重试都换随机缓存目录名，无法预置缓存。

本仓库的解决办法：`tools/7za-wrapper.py` 打包出的 `tools/7za.exe` 是一个包装器，
对路径含 `winCodeSign` 的解压命令自动追加 `-xr!libcrypto.dylib -xr!libssl.dylib`
（仅排除 macOS 签名库，Windows 打包用不到）。安装依赖后需执行一次：

```bash
cd desktop
mv node_modules/7zip-bin/win/x64/7za.exe node_modules/7zip-bin/win/x64/7za-real.exe
cp tools/7za.exe node_modules/7zip-bin/win/x64/7za.exe
```

（`npm install` 重装 7zip-bin 后需重新执行。）

另外 `dist` 脚本通过 `CSC_IDENTITY_AUTO_DISCOVERY=false` 关闭证书自动发现，
跳过代码签名（输出未签名安装包，首次运行会有 SmartScreen 提示）。

## 开发模式

需要系统 Python 已安装 backend/requirements.txt 依赖。三条进程一条命令拉起：

```bash
cd desktop
npm install
npm run dev
```

- `dev:backend`：`python ../backend/desktop_entry.py`（DESKTOP_MODE=true，127.0.0.1:18321）
- `dev:frontend`：Vite dev server（localhost:5173）
- 两者就绪后启动 Electron，加载 `http://localhost:5173`；页面内 axios 经
  preload 注入的 `apiBase` 直连 18321 后端。

## 打包（产出 NSIS 安装包）

国内网络镜像已在仓库 `desktop/.npmrc` 里配好（registry、electron、electron-builder
二进制都走 npmmirror），无需手工 `npm config set`（新版 npm 已拒绝
`electron_mirror` 这类自定义键）。

然后：

```bash
cd desktop
npm run dist
```

`dist` 脚本依次执行：
1. `build:backend`：PyInstaller 按 `../backend/datashield-backend.spec` 构建
   `../backend/dist/datashield-backend/datashield-backend.exe`；
2. `build:frontend`：`npm --prefix ../frontend run build` 产出 `../frontend/dist`；
3. `electron-builder --win nsis`：输出到 `desktop/release/`。

## 关键实现说明

- 后端桌面模式由 `DESKTOP_MODE=true` 开启（`backend/app/core/config.py`）：
  非 GET 请求无 Origin / `null` / `file://` Origin 时放行
  （`evaluation_auth.validate_browser_origin`），cookie 不带 `secure`，
  CORS 使用 `allow_origin_regex=".*"`（仅桌面模式）。
- 桌面入口 `backend/desktop_entry.py`：固定 127.0.0.1:18321，数据库指向
  `DATASHIELD_DATA_DIR`，默认 `LLM_PROVIDER=mock`、`EMBEDDING_PROVIDER=local`，离线可跑。
