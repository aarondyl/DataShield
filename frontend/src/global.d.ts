export {};

declare global {
  interface Window {
    /** Tauri 模式标记。渲染层不持有本地服务地址或运行时令牌。 */
    datashieldDesktop?: boolean;
  }
}
