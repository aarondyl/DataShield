// DataShield 桌面版 Electron 主进程。
//
// - 开发模式（DESKTOP_DEV=1）：连接 Vite dev server（http://localhost:5173），
//   后端由 `npm run dev:backend` 用系统 Python 启动（desktop_entry.py），
//   preload 注入的 apiBase 指向 http://127.0.0.1:18321/api（可用 DESKTOP_DEV_API 覆盖）。
// - 生产模式：spawn resources/datashield-backend/datashield-backend.exe
//   （env 带 DATASHIELD_DATA_DIR=userData），轮询 /api/health 就绪后加载
//   resources/frontend-dist/index.html；退出时杀掉后端进程树。

const { app, BrowserWindow } = require('electron');
const { spawn, exec } = require('child_process');
const path = require('path');
const http = require('http');

const BACKEND_PORT = 18321;
const HEALTH_URL = `http://127.0.0.1:${BACKEND_PORT}/api/health`;
const isDev = !!process.env.DESKTOP_DEV;

let mainWindow = null;
let backendProcess = null;

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
      const indexHtml = path.join(process.resourcesPath, 'frontend-dist', 'index.html');
      createWindow(null, indexHtml);
    })
    .catch((err) => {
      console.error('后端启动失败:', err);
      app.quit();
    });
}

function startBackend() {
  const exe = path.join(process.resourcesPath, 'datashield-backend', 'datashield-backend.exe');
  backendProcess = spawn(exe, [], {
    env: { ...process.env, DATASHIELD_DATA_DIR: app.getPath('userData') },
    stdio: 'ignore',
    windowsHide: true,
  });
  backendProcess.on('exit', (code) => {
    console.log(`后端进程退出，code=${code}`);
    backendProcess = null;
  });
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

function createWindow(url, file) {
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
  if (url) mainWindow.loadURL(url);
  else mainWindow.loadFile(file);
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
