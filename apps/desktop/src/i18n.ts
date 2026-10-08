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
  intake: { eyebrow: '产品接入', title: '先确认一项产品能力', body: '这会写入仅保存在本机 SQLite 的产品画像。稍后可继续补充、修正或从网站和代码仓库理解产品。', fact: '产品能力或处理活动', placeholder: '例如：用户可上传文档', continue: '保存并查看产品画像', saving: '正在保存…', error: '无法保存产品信息，请确认本地智能体已连接。' },
  today: { title: '今日待办', empty: '工作区准备就绪后，您需要处理的合规事项会显示在这里。' },
  monitor: { title: '法规动态', body: '法规变化先同步到本机缓存；只有本地智能体完成适用性分析后才可能形成合规发现。', empty: '本地缓存中尚无法规变更。', offline: 'Cloud 法规服务暂不可用，以下内容来自本地缓存。', lastSync: '上次成功同步', scope: '同步范围', status: '同步状态', never: '尚未成功同步', loading: '正在读取本地同步状态…', sync: '手动同步法规', syncing: '正在同步…' },
  findings: { title: '合规发现', body: '只显示基于本地产品画像和适用 Requirement 的真实分析结果；法规变化本身不是 Finding。', empty: '尚未运行合规检查。', run: '运行本地合规检查', running: '正在分析…', requirements: '法规要求', evidence: '证据', twin: '产品画像', done: '分析完成。', needsContext: '分析需要更多产品上下文。', noApplicable: '未发现适用的合规缺口。', noRequirements: '请先同步法规，再运行检查。', runError: '无法完成本地合规检查。', loadError: '无法读取合规发现。' },
  actions: { title: '整改事项', empty: '确认合规发现后，整改建议会显示在这里。' },
  twin: { title: '产品画像', empty: '添加网站、选择代码仓库或手动描述产品后，可在这里确认产品画像。', loading: '正在读取本地产品画像…' },
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
  intake: { eyebrow: 'Product intake', title: 'Confirm one product capability', body: 'This is saved to the Product Twin in local SQLite only. You can later add, correct, or derive details from a website and repository.', fact: 'Capability or processing activity', placeholder: 'For example: users can upload documents', continue: 'Save and view Product Twin', saving: 'Saving…', error: 'Could not save product information. Check that the Local Agent is connected.' },
  today: { title: 'Today', empty: 'Once the workspace is ready, compliance work that needs your attention appears here.' },
  monitor: { title: 'Monitor', body: 'Regulatory changes first sync to the local cache; they may become findings only after Local Agent applicability analysis.', empty: 'No regulatory changes are in the local cache yet.', offline: 'Cloud RegIntel is unavailable; the content below is from the local cache.', lastSync: 'Last successful sync', scope: 'Sync scope', status: 'Sync status', never: 'No successful sync yet', loading: 'Loading local sync status…', sync: 'Sync regulations', syncing: 'Syncing…' },
  findings: { title: 'Findings', body: 'Only real analysis results based on the local Product Twin and applicable Requirements appear here; a regulatory change is not itself a Finding.', empty: 'No compliance assessment has run yet.', run: 'Run local compliance check', running: 'Analyzing…', requirements: 'Requirements', evidence: 'Evidence', twin: 'Product Twin', done: 'Analysis completed.', needsContext: 'The analysis needs more product context.', noApplicable: 'No applicable compliance gap was found.', noRequirements: 'Sync regulations before running a check.', runError: 'The local compliance check could not be completed.', loadError: 'Could not load findings.' },
  actions: { title: 'Actions', empty: 'Remediation suggestions appear here after you confirm a finding.' },
  twin: { title: 'Product Twin', empty: 'Add a website, select a code repository, or describe the product to confirm its Product Twin here.', loading: 'Loading the local Product Twin…' },
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
