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

## 附录：统一术语表

以下术语在所有片段文件中保持一致；新增或修改文案时先查此表，不要自造译法。

| English | 中文 | 说明 |
|---|---|---|
| Finding | 合规发现 | 有证据支撑、适用于产品的差距；en 正文中作普通名词小写 `finding(s)` |
| Remediation Action | 整改行动 | 由 Finding 生成、待人工审阅的建议行动 |
| Product Twin | 产品画像 | 产品的事实模型；developer 旧页面中的 Product Profile 对应“产品档案” |
| Applicability | 适用性 | 某要求是否适用于产品 |
| Evidence | 证据 | 支撑结论的产品事实或法律条文 |
| Workspace | 工作区 | 独立的评估环境 |
| Regulation Intelligence | 法规智能 | 法规库、条文版本与官方来源；en 不用 Regulatory Intelligence |
| Impact Analysis | 影响分析 | 法规变化对产品的影响评估 |
| Self-Assessment | 合规自查 | 规则引擎逐项核对 |
| Remediation Roadmap | 整改路线图 | 排好优先级、可验证的整改计划 |
| Document Prefill | 文档预填 | 基于产品画像预填合规文档草稿 |
| Privacy Policy | 隐私政策 | 作为文档名可大写；en UI 标签中作普通名词小写 `privacy policy` |
| SDK Scan | SDK 扫描 | 依赖 / 权限清单扫描 |
| Ready to Ship | 发布就绪 | 上线前基础检查通过的状态 |
