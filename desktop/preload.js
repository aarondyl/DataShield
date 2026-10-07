// 向渲染进程暴露桌面端信息：API 根地址。
// 开发/生产模式后端都监听 127.0.0.1:18321，保持一致。
const { contextBridge } = require('electron');

contextBridge.exposeInMainWorld('datashieldDesktop', {
  apiBase: process.env.DESKTOP_DEV_API || 'http://127.0.0.1:18321/api',
});
