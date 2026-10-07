// 向渲染进程暴露桌面端信息：API 根地址 + 运行时 token 获取通道。
// 开发/生产模式后端都监听 127.0.0.1:18321，保持一致。
// getToken 经 IPC 向主进程取本次启动的随机 token，前端给 /api 请求加 X-Runtime-Token。
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('datashieldDesktop', {
  apiBase: process.env.DESKTOP_DEV_API || 'http://127.0.0.1:18321/api',
  getToken: () => ipcRenderer.invoke('datashield:runtime-token'),
});
