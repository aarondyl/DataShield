export {};

declare global {
  interface Window {
    /** 由 Electron preload 注入；浏览器环境下为 undefined。 */
    datashieldDesktop?: {
      /** 桌面模式下直连内嵌 FastAPI 的 API 根地址，如 http://127.0.0.1:18321/api */
      apiBase: string;
    };
  }
}
