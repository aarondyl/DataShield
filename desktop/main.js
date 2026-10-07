// DataShield 桌面版 Electron 主进程。
//
// - 开发模式（DESKTOP_DEV=1）：连接 Vite dev server（http://localhost:5173），
//   后端由 `npm run dev:backend` 用系统 Python 启动（desktop_entry.py），
//   preload 注入的 apiBase 指向 http://127.0.0.1:18321/api（可用 DESKTOP_DEV_API 覆盖）。
// - 生产模式：spawn resources/datashield-backend/datashield-backend.exe
//   （env 带 DATASHIELD_DATA_DIR=%APPDATA%/DataShield、DATASHIELD_FRONTEND_DIR=resources/frontend-dist、
//   DATASHIELD_RUNTIME_TOKEN=每次启动随机生成），轮询 /api/health 就绪后加载
//   http://127.0.0.1:18321/（后端同源提供前端静态文件，避免 file:// 下 ES module 被
//   CORS 拦截导致的白屏）；退出时杀掉后端进程树。
// - 运行时 token：后端仅接受带 X-Runtime-Token 的 /api 请求（/api/health 除外），
//   防止本机其他进程盗用 127.0.0.1:18321；渲染进程经 preload 的 IPC 拿 token。

const { app, BrowserWindow, ipcMain } = require('electron');
const { spawn, exec } = require('child_process');
const crypto = require('crypto');
const fs = require('fs');
const path = require('path');
const http = require('http');

const BACKEND_PORT = 18321;
const HEALTH_URL = `http://127.0.0.1:${BACKEND_PORT}/api/health`;
const isDev = !!process.env.DESKTOP_DEV;

// 每次启动随机生成，只存于主进程内存并走进程环境变量，不落盘
const runtimeToken = crypto.randomBytes(32).toString('hex');

let mainWindow = null;
let backendProcess = null;

ipcMain.handle('datashield:runtime-token', () => runtimeToken);

// 单例锁：重复启动时聚焦已有窗口
if (!app.requestSingleInstanceLock()) {
  app.quit();
} else {
  app.on('second-instance', () => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore();
      mainWindow.focus();
    }
  });
  app.whenReady().then(start);
}

function start() {
  if (isDev) {
    createWindow('http://localhost:5173');
    return;
  }
  startBackend();
  waitForBackend(120, 500)
    .then(() => {
      // 后端同源托管前端静态文件（DATASHIELD_FRONTEND_DIR），直接加载后端地址
      createWindow(`http://127.0.0.1:${BACKEND_PORT}/`);
    })
    .catch((err) => {
      console.error('后端启动失败:', err);
      app.quit();
    });
}

function startBackend() {
  const exe = path.join(process.resourcesPath, 'datashield-backend', 'datashield-backend.exe');
  backendProcess = spawn(exe, [], {
    env: {
      ...process.env,
      DATASHIELD_DATA_DIR: resolveDataDir(),
      DATASHIELD_FRONTEND_DIR: path.join(process.resourcesPath, 'frontend-dist'),
      DATASHIELD_RUNTIME_TOKEN: runtimeToken,
    },
    stdio: 'ignore',
    windowsHide: true,
  });
  backendProcess.on('exit', (code) => {
    console.log(`后端进程退出，code=${code}`);
    backendProcess = null;
  });
}

// 数据目录统一为 <appData>/DataShield（Windows 即 %APPDATA%/DataShield），不再跟随
// Electron 默认 userData（%APPDATA%/datashield-desktop）。旧目录里已有 datashield.db 时
// 首次启动把它移动过去（跨盘失败则复制），其余工作数据（data/ 法规副本等）由后端自行重建。
function resolveDataDir() {
  const newDir = path.join(app.getPath('appData'), 'DataShield');
  const oldDir = app.getPath('userData');
  try {
    const oldDb = path.join(oldDir, 'datashield.db');
    const newDb = path.join(newDir, 'datashield.db');
    if (oldDir !== newDir && fs.existsSync(oldDb) && !fs.existsSync(newDb)) {
      fs.mkdirSync(newDir, { recursive: true });
      try {
        fs.renameSync(oldDb, newDb);
      } catch {
        fs.copyFileSync(oldDb, newDb);
        fs.rmSync(oldDb, { force: true });
      }
    }
  } catch (err) {
    console.error('旧数据目录迁移失败（使用新目录重新初始化）:', err);
  }
  return newDir;
}

function waitForBackend(maxAttempts, intervalMs) {
  return new Promise((resolve, reject) => {
    let attempts = 0;
    const probe = () => {
      http
        .get(HEALTH_URL, (res) => {
          if (res.statusCode === 200) return resolve();
          retry();
        })
        .on('error', retry);
    };
    const retry = () => {
      if (++attempts >= maxAttempts) return reject(new Error('后端健康检查超时'));
      setTimeout(probe, intervalMs);
    };
    probe();
  });
}

function createWindow(url) {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    title: 'DataShield 数据合规',
    autoHideMenuBar: true,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });
  mainWindow.loadURL(url);
  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

function killBackend() {
  if (!backendProcess) return;
  const pid = backendProcess.pid;
  backendProcess = null;
  if (process.platform === 'win32') {
    // /T 连同子进程一起结束（uvicorn 可能派生 worker）
    exec(`taskkill /pid ${pid} /T /F`, () => {});
  } else {
    try {
      process.kill(pid, 'SIGTERM');
    } catch {}
  }
}

app.on('window-all-closed', () => {
  killBackend();
  app.quit();
});

app.on('before-quit', killBackend);
