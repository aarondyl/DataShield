# i18n 多语言规范（DataShield Frontend）

基础设施：`react-i18next` + `i18next-browser-languagedetector`，入口 `src/i18n/index.ts`（已在 `main.tsx` 顶部 `import './i18n'`）。语言偏好存 localStorage key `datashield.lang`，检测顺序 `localStorage` → `navigator`，fallback 为 `zh`；切换语言时自动同步 `<html lang>`（zh-CN / en）。切换组件：`src/components/LanguageSwitcher.tsx`。

## 目录结构与片段归属

单一命名空间 `translation`，资源按组合并（`locales/zh.ts` / `locales/en.ts` 已完成合并，**不要改这两个文件**）：

| 片段文件（zh/en 各一份） | key 前缀 | 负责范围 |
|---|---|---|
| `locales/{zh,en}/common.ts` | `common.*` | 通用：按钮（保存/取消/返回）、状态枚举、时间、表单项 |
| `locales/{zh,en}/appnew.ts` | `appnew.*` | `pages/new/` 下的新 UI（landing、auth、onboarding、app shell 等） |
| `locales/{zh,en}/business.ts` | `business.*` | 企业版业务页面（findings、actions、monitor、product 等） |
| `locales/{zh,en}/developer.ts` | `developer.*` | 开发者版页面（status、issues、scan、ship 等） |
| `locales/{zh,en}/misc.ts` | `misc.*` | 其余散落文案、兜底 |

**每个并行代理只写自己负责的片段文件**（如 `locales/zh/appnew.ts` 和 `locales/en/appnew.ts`），并保持两个文件 key 完全对齐。片段文件导出该组前缀**之内**的对象，例如 `appnew.ts` 里写 `landing: { title: '...' }`，使用方写 `t('appnew.landing.title')`。

## Key 规范

- key 一律 **camelCase**，按页面/组件层级组织：`appnew.landing.title`、`common.actions.save`。
- 值中需要插值时用双花括号：`t('common.greeting', { name })` 对应 `'你好，{{name}}'`。不要字符串拼接句子。
- 组件中统一用法：
  ```tsx
  import { useTranslation } from 'react-i18next';
  const { t } = useTranslation();
  <h1>{t('appnew.landing.title')}</h1>
  ```
- **HTML 属性同样要抽取**：`title`、`placeholder`、`aria-label`、`alt` 等，例如 `placeholder={t('common.form.emailPlaceholder')}`。
- 后端枚举/状态码映射用动态 key 模式：
  ```tsx
  t(`common.status.${code}`)   // 片段中准备 common.status.confirmed / unknown / not_detected 等
  ```
  注意为未知枚举留兜底（如 `t('common.status.unknown')` 或 i18next 的 `defaultValue`）。
- 复数用 i18next 内置 `_one` / `_other` 后缀；不要在代码里写 `count > 1 ? 's' : ''`。
- 品牌名 "DataShield" 等不翻译内容可复用 `misc.appTitle`。
