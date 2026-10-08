import { useEffect, useMemo, useState } from 'react';

export type Locale = 'zh-CN' | 'en-US';

const preferenceKey = 'datashield.desktop.locale';

const zh = {
  productName: 'DataShield',
  nav: ['今日待办', '法规动态', '合规发现', '整改事项', '产品画像', '设置'],
  status: { connected: '本地智能体已连接', checking: '正在检查本地智能体…', offline: '本地智能体暂不可用' },
  welcome: {
    eyebrow: '本地优先的合规工作台',
    title: '欢迎使用 DataShield',
    body: '您的产品资料、证据和个性化合规分析默认保留在这台设备上。',
    create: '创建本地工作区',
    privacy: '查看数据与隐私说明',
  },
  workspace: {
    title: '创建本地工作区',
    body: '先选择使用场景；稍后可以在设置中调整。',
    developer: '开发者版',
    developerBody: '围绕单个软件产品完成产品理解、合规检查和整改。',
    enterprise: '企业版',
    enterpriseBody: '管理公司和多个产品的合规任务。协作与审批能力将在后续版本提供。',
    continue: '继续添加产品',
    workspaceName: '工作区或企业名称', productName: '产品名称', description: '产品描述（可选）', createError: '无法创建本地工作区，请确认本地智能体已连接。', creating: '正在创建…',
  },
  today: { title: '今日待办', empty: '工作区准备就绪后，您需要处理的合规事项会显示在这里。' },
  monitor: { title: '法规动态', empty: '连接 Cloud 法规服务后，最新法规变化会先同步到本地缓存，再由本地智能体评估。' },
  findings: { title: '合规发现', empty: '尚未运行合规检查。法规变化本身不会直接作为合规发现。' },
  actions: { title: '整改事项', empty: '确认合规发现后，整改建议会显示在这里。' },
  twin: { title: '产品画像', empty: '添加网站、选择代码仓库或手动描述产品后，可在这里确认产品画像。' },
  settings: { title: '设置', language: '语言', ai: 'AI 服务提供方', privacy: '数据与隐私', update: '安装与更新提醒' },
  labels: { chinese: '简体中文', english: 'English', retry: '重新检查', demo: '开发预览' },
} as const;

// Keep the key tree inferred from the Chinese-first source while widening leaf
// values to strings. `en` therefore cannot omit a Chinese UI key.
type TranslationShape<T> = T extends readonly unknown[]
  ? string[]
  : T extends object
    ? { [K in keyof T]: TranslationShape<T[K]> }
    : string;
export type Copy = TranslationShape<typeof zh>;

const en: Copy = {
  productName: 'DataShield',
  nav: ['Today', 'Monitor', 'Findings', 'Actions', 'Product Twin', 'Settings'],
  status: { connected: 'Local Agent connected', checking: 'Checking Local Agent…', offline: 'Local Agent is unavailable' },
  welcome: {
    eyebrow: 'A local-first compliance workspace',
    title: 'Welcome to DataShield',
    body: 'Your product data, evidence, and personalized compliance analysis stay on this device by default.',
    create: 'Create local workspace',
    privacy: 'View data and privacy',
  },
  workspace: {
    title: 'Create local workspace',
    body: 'Choose a starting scenario. You can change it later in Settings.',
    developer: 'Developer',
    developerBody: 'Understand one software product, assess compliance, and plan remediation.',
    enterprise: 'Enterprise',
    enterpriseBody: 'Track companies and multiple products. Collaboration and approval are planned for a later release.',
    continue: 'Continue to add a product',
    workspaceName: 'Workspace or company name', productName: 'Product name', description: 'Product description (optional)', createError: 'Could not create the local workspace. Check that the Local Agent is connected.', creating: 'Creating…',
  },
  today: { title: 'Today', empty: 'Once the workspace is ready, compliance work that needs your attention appears here.' },
  monitor: { title: 'Monitor', empty: 'After connecting to Cloud RegIntel, changes sync to the local cache before the Local Agent evaluates them.' },
  findings: { title: 'Findings', empty: 'No compliance assessment has run yet. A regulatory change is not itself a finding.' },
  actions: { title: 'Actions', empty: 'Remediation suggestions appear here after you confirm a finding.' },
  twin: { title: 'Product Twin', empty: 'Add a website, select a code repository, or describe the product to confirm its Product Twin here.' },
  settings: { title: 'Settings', language: 'Language', ai: 'AI provider', privacy: 'Data and privacy', update: 'Install and update notifications' },
  labels: { chinese: '简体中文', english: 'English', retry: 'Check again', demo: 'Development preview' },
};

function initialLocale(): Locale {
  const saved = window.localStorage.getItem(preferenceKey);
  if (saved === 'zh-CN' || saved === 'en-US') return saved;
  return navigator.language.toLowerCase().startsWith('zh') ? 'zh-CN' : 'en-US';
}

export function useLocale() {
  const [locale, setLocaleState] = useState<Locale>(initialLocale);
  const setLocale = (next: Locale) => {
    window.localStorage.setItem(preferenceKey, next);
    setLocaleState(next);
  };
  useEffect(() => { document.documentElement.lang = locale; }, [locale]);
  return useMemo(() => ({ locale, setLocale, copy: locale === 'zh-CN' ? zh : en }), [locale]);
}
