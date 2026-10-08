import { useEffect, useMemo, useState } from 'react';

export type Locale = 'zh-CN' | 'en-US';

const preferenceKey = 'datashield.desktop.locale';

export const zh = {
  understanding: { retry: '重试', title: '接入与理解产品', description: '补充产品描述（可选）', url: '公开网站 URL', website: '分析网站', select: '选择本地代码仓库文件夹', repository: '扫描已选择的本地仓库', privacy: '仓库扫描在本机执行，不上传仓库内容。网站分析只访问公开页面。仅扫描您通过原生选择器授权的目录，跳过密钥、数据库与依赖目录。', selectionError: '无法选择或授权该目录，请选择有效的代码仓库文件夹。', pending: '正在理解产品，请稍候…', failed: '分析失败，请检查网站可访问性或重新选择仓库后重试。', error: '产品分析请求未完成，请检查本地智能体后重试。', features: '识别到的产品能力', evidence: '分析证据与来源', review: '静态线索不证明实际运行行为。未知不是否定，未检测到不代表不存在。确认导入将创建新的产品画像版本，保留旧版本；导入后仍可审核每项事实。', attach: '确认导入产品画像' },
  feedback: { title: '纠正产品信息与重新分析', boundary: '确认仅表示您认可修正候选。应用后才写入新的产品画像版本，并仅重新检查关联的法规要求。旧画像与旧发现保留。未知不等于否定，未检测到不等于不存在。', mock: '当前解释由本地确定性模拟模型生成，请仔细审核候选内容。', input: '您认为哪些产品事实不准确？', interpret: '解释纠正意见', original: '原始反馈', explanation: '系统理解与修正候选', clarify: '提交澄清', confirm: '确认修正候选', reject: '拒绝候选', confirmed: '候选已确认。请应用修正并重新检查；确认本身不会更新产品画像。', apply: '应用修正并重新分析', retry: '重试关联法规分析', version: '修正后的产品画像版本', run: '关联检查记录', failed: '重新分析未完成，可重试。已写入的画像版本将保留。', applied: '新画像版本和关联分析已完成，历史记录保留。可返回合规发现与今日待办查看结果。', error: '反馈操作未完成，请检查连接后重试。', states: { PROPOSED: '待确认', NEEDS_CLARIFICATION: '需要澄清', CONFIRMED: '已确认，待完成应用', APPLIED: '已应用并完成分析', REJECTED: '已拒绝' } },
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
  today: { title: '今日待办', empty: '工作区准备就绪后，您需要处理的合规事项会显示在这里。', setup: '请先创建产品工作区。', error: '无法读取今日待办，请重试。', loading: '正在读取本地待办…', noSync: '尚未成功同步法规，请先连接法规服务。', noRun: '尚未运行合规检查；暂无发现不代表已合规。', lastRun: '最近一次检查', failed: '分析失败，请重新运行检查', context: '需要补充产品信息', completed: '检查完成', running: '检查进行中', mock: '使用本地模拟模型', review: '需要关注的合规发现', waiting: '等待您处理', feedback: '审核产品纠正意见', recent: '最近已处理事项', clear: '当前没有需要您处理的事项。这不构成合规认证。', changes: '最近的法规变化', changeBoundary: '法规变化与产品合规发现分别记录。' },
  monitor: { title: '法规动态', body: '法规变化先同步到本机缓存；只有本地智能体完成适用性分析后才可能形成合规发现。', empty: '本地缓存中尚无法规变更。', offline: 'Cloud 法规服务暂不可用，以下内容来自本地缓存。', lastSync: '上次成功同步', scope: '同步范围', status: '同步状态', never: '尚未成功同步', loading: '正在读取本地同步状态…', sync: '手动同步法规', syncing: '正在同步…' },
  findings: { risk: '风险等级', analysisTime: '分析时间', officialSource: '查看官方来源', regulationVersion: '法规版本', legalUnit: '法规条款', unavailable: '暂无记录', mock: '当前分析使用确定性模拟模型，并非真实 AI 合规判断。结果仅用于验证业务流程。', risks: { LOW: '低', MEDIUM: '中', HIGH: '高', CRITICAL: '严重' }, states: { OPEN: '待处理', DISMISSED: '已忽略', RESOLVED: '已解决' }, title: '合规发现', body: '只显示基于本地产品画像和适用法规要求的分析记录；法规变化本身不是合规发现。', empty: '尚未运行合规检查。', run: '运行本地合规检查', running: '正在分析…', requirements: '法规要求', evidence: '证据', twin: '产品画像', applicability: '适用性结论', gap: '差距分析', runRef: '分析记录', noEvidence: '暂无可验证证据', done: '分析完成。', needsContext: '分析需要更多产品上下文。', noApplicable: '未发现适用的合规缺口。', noRequirements: '请先同步法规，再运行检查。', runError: '无法完成本地合规检查。', loadError: '无法读取合规发现。' },
  actions: { title: '整改事项', empty: '暂无整改事项，请选择合规发现生成建议。', setup: '请先创建本地产品工作区。', boundary: '批准仅表示接受建议，不会执行代码变更、发布文档或将合规发现标为已解决。', finding: '关联的合规发现', choose: '请选择待处理的合规发现', type: '整改类型', document: '文档整改', code: '代码整改', documentType: '文档类型（例如：隐私声明）', create: '生成整改建议', loading: '正在处理…', error: '整改操作未完成，请检查本地智能体连接或稍后重试。', content: '具体整改内容', draft: '文档草案，需要人工审核后才能使用。', criteria: '验收标准', requirements: '关联法规要求', evidence: '依据与证据', source: '查看官方来源', unavailable: '暂无版本记录', note: '审核意见（可选）', approve: '批准建议', reject: '拒绝建议', back: '返回原合规发现', mock: '当前建议由本地确定性模拟模型生成，需人工审核；尚未连接真实 AI 服务。', states: { PROPOSED: '待人工审核', APPROVED: '已批准建议（尚未执行）', REJECTED: '已拒绝' } },
  twin: { confirm: '确认此事实', version: '当前画像版本', history: '历史版本', error: '无法读取或更新产品画像，请重试。', boundary: '确认事实将追加新的画像版本，历史版本不会被覆盖。', groups: { features: '产品能力', controls: '合规控制', market_clues: '目标市场', subject_types: '法律主体角色' }, states: { PRESENT: '存在', ABSENT: '明确不存在', UNKNOWN: '未知', NOT_DETECTED: '未检测到' }, decisions: { CONFIRMED: '已确认', UNREVIEWED: '待确认', CORRECTED: '已更正，保留历史' }, title: '产品画像', empty: '添加网站、选择代码仓库或手动描述产品后，可在这里确认产品画像。', loading: '正在读取本地产品画像…' },
  settings: { cloud: 'Cloud 法规服务地址', cloudHelp: '请输入已部署的公开 HTTPS 法规服务地址，不包含 API Key。已有缓存后不得直接切换来源。', save: '保存同步配置', saved: '配置已保存，可前往法规动态同步。', error: '无法保存，请检查 HTTPS 地址；已有缓存时不能切换来源。', aiBoundary: '当前为本地确定性模拟模式，不是真实 AI 服务。默认 Cloud AI Gateway、安全 BYOK 和 Ollama 设置尚未提供；安装包不包含共享 API Key。', privacyBody: '产品画像、证据与反馈保存在本机 SQLite。仓库扫描仅限原生选择器授权目录；Cloud 只提供公开法规。', updateBody: '自动更新尚未启用。请仅安装经批准的 GitHub Release 安装包并验证 SHA256。', title: '设置', language: '语言', ai: 'AI 服务提供方', privacy: '数据与隐私', update: '安装与更新提醒' },
  labels: { chinese: '简体中文', english: 'English', retry: '重新检查', demo: '开发预览' },
} as const;

// Keep the key tree inferred from the Chinese-first source while widening leaf
// values to strings. `en` therefore cannot omit a Chinese UI key.
type TranslationShape<T> = T extends readonly unknown[]
  ? readonly string[]
  : T extends object
    ? { [K in keyof T]: TranslationShape<T[K]> }
    : string;
export type Copy = TranslationShape<typeof zh>;

export const en: Copy = {
  understanding: { retry: 'Retry', title: 'Connect and understand a product', description: 'Additional product description (optional)', url: 'Public website URL', website: 'Analyze website', select: 'Select local repository folder', repository: 'Scan selected local repository', privacy: 'Repository scanning runs locally without uploading repository content. Website analysis accesses public pages only. Only folders authorized through the native picker are scanned; secrets, databases, and dependency directories are excluded.', selectionError: 'Could not select or authorize this folder. Choose a valid repository folder.', pending: 'Understanding the product…', failed: 'Analysis failed. Check website availability or select the repository again and retry.', error: 'The analysis request could not be completed. Check the Local Agent and retry.', features: 'Detected capabilities', evidence: 'Analysis evidence and sources', review: 'Static clues do not prove runtime behavior. Unknown is not false; not detected is not absent. Confirming import creates a new Twin version and retains history. Individual facts remain reviewable.', attach: 'Confirm import to Product Twin' },
  feedback: { title: 'Correct product facts and reanalyze', boundary: 'Confirmation accepts a proposed correction. Applying it creates a new Product Twin version and checks only linked requirements. Historical versions and findings remain. Unknown does not mean false; not detected does not mean absent.', mock: 'Interpretation currently uses a local deterministic mock model. Review proposals carefully.', input: 'Which product facts are inaccurate?', interpret: 'Interpret correction', original: 'Original feedback', explanation: 'Interpretation and proposed correction', clarify: 'Submit clarification', confirm: 'Confirm proposal', reject: 'Reject proposal', confirmed: 'The proposal is confirmed. Apply it and recheck; confirmation alone does not update the Product Twin.', apply: 'Apply correction and reanalyze', retry: 'Retry scoped analysis', version: 'Corrected Product Twin version', run: 'Linked analysis record', failed: 'Reanalysis did not complete. Retry is available; the written Twin version is retained.', applied: 'The new Twin version and scoped analysis are complete. History is retained. Return to Findings and Today for results.', error: 'The feedback operation could not be completed. Check the connection and retry.', states: { PROPOSED: 'Awaiting confirmation', NEEDS_CLARIFICATION: 'Needs clarification', CONFIRMED: 'Confirmed, application pending', APPLIED: 'Applied and analyzed', REJECTED: 'Rejected' } },
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
  today: { title: 'Today', empty: 'Once the workspace is ready, compliance work that needs your attention appears here.', setup: 'Create a product workspace first.', error: 'Could not load Today. Retry.', loading: 'Loading local tasks…', noSync: 'Regulations have not synced successfully. Connect the regulation service first.', noRun: 'No check has run. No findings does not mean compliance.', lastRun: 'Latest check', failed: 'Analysis failed. Run the check again', context: 'More product context is needed', completed: 'Check completed', running: 'Check in progress', mock: 'Local mock model', review: 'Findings needing attention', waiting: 'Waiting for your input', feedback: 'Review product correction', recent: 'Recently handled', clear: 'Nothing currently needs your attention. This is not compliance certification.', changes: 'Recent regulatory changes', changeBoundary: 'Regulatory changes are recorded separately from product findings.' },
  monitor: { title: 'Monitor', body: 'Regulatory changes first sync to the local cache; they may become findings only after Local Agent applicability analysis.', empty: 'No regulatory changes are in the local cache yet.', offline: 'Cloud RegIntel is unavailable; the content below is from the local cache.', lastSync: 'Last successful sync', scope: 'Sync scope', status: 'Sync status', never: 'No successful sync yet', loading: 'Loading local sync status…', sync: 'Sync regulations', syncing: 'Syncing…' },
  findings: { risk: 'Risk level', analysisTime: 'Analysis time', officialSource: 'View official source', regulationVersion: 'Regulation version', legalUnit: 'Legal provision', unavailable: 'Not recorded', mock: 'This analysis uses a deterministic mock model, not a real AI compliance judgment. Results validate the workflow only.', risks: { LOW: 'Low', MEDIUM: 'Medium', HIGH: 'High', CRITICAL: 'Critical' }, states: { OPEN: 'Open', DISMISSED: 'Dismissed', RESOLVED: 'Resolved' }, title: 'Findings', body: 'Only real analysis results based on the local Product Twin and applicable Requirements appear here; a regulatory change is not itself a Finding.', empty: 'No compliance assessment has run yet.', run: 'Run local compliance check', running: 'Analyzing…', requirements: 'Requirements', evidence: 'Evidence', twin: 'Product Twin', applicability: 'Applicability conclusion', gap: 'Gap analysis', runRef: 'Analysis record', noEvidence: 'No verifiable evidence is available', done: 'Analysis completed.', needsContext: 'The analysis needs more product context.', noApplicable: 'No applicable compliance gap was found.', noRequirements: 'Sync regulations before running a check.', runError: 'The local compliance check could not be completed.', loadError: 'Could not load findings.' },
  actions: { title: 'Actions', empty: 'No actions yet. Select a finding to generate a recommendation.', setup: 'Create a local product workspace first.', boundary: 'Approval accepts the recommendation. It does not execute code changes, publish documents, or resolve the finding.', finding: 'Linked finding', choose: 'Select an open finding', type: 'Action type', document: 'Document change', code: 'Code change', documentType: 'Document type (for example: privacy notice)', create: 'Generate recommendation', loading: 'Processing…', error: 'The action could not be completed. Check the Local Agent connection or retry later.', content: 'Proposed changes', draft: 'Document draft. Human review is required before use.', criteria: 'Acceptance criteria', requirements: 'Linked requirements', evidence: 'Grounding and evidence', source: 'View official source', unavailable: 'No version reference available', note: 'Review note (optional)', approve: 'Approve recommendation', reject: 'Reject recommendation', back: 'Return to original finding', mock: 'This recommendation was generated by a local deterministic mock model and requires human review. A real AI service is not connected.', states: { PROPOSED: 'Awaiting review', APPROVED: 'Recommendation approved (not executed)', REJECTED: 'Rejected' } },
  twin: { confirm: 'Confirm this fact', version: 'Current Twin version', history: 'Version history', error: 'Could not load or update the Product Twin. Retry.', boundary: 'Confirming facts appends a new Twin version without overwriting history.', groups: { features: 'Capabilities', controls: 'Compliance controls', market_clues: 'Target markets', subject_types: 'Legal subject roles' }, states: { PRESENT: 'Present', ABSENT: 'Explicitly absent', UNKNOWN: 'Unknown', NOT_DETECTED: 'Not detected' }, decisions: { CONFIRMED: 'Confirmed', UNREVIEWED: 'Awaiting confirmation', CORRECTED: 'Corrected, history retained' }, title: 'Product Twin', empty: 'Add a website, select a code repository, or describe the product to confirm its Product Twin here.', loading: 'Loading the local Product Twin…' },
  settings: { cloud: 'Cloud regulation service URL', cloudHelp: 'Enter the deployed public HTTPS regulation service URL without API keys. Existing cache cannot be switched to another upstream.', save: 'Save sync configuration', saved: 'Configuration saved. Open Monitor to sync.', error: 'Could not save. Check the HTTPS URL; cached data cannot be switched to another upstream.', aiBoundary: 'Currently using a local deterministic mock, not a real AI service. Cloud AI Gateway, secure BYOK and Ollama settings are unavailable. No shared API key is bundled.', privacyBody: 'Product Twin, evidence and feedback stay in local SQLite. Repository scans require native folder authorization; Cloud serves public regulations only.', updateBody: 'Automatic updates are not enabled. Install only approved GitHub Release installers and verify SHA256.', title: 'Settings', language: 'Language', ai: 'AI provider', privacy: 'Data and privacy', update: 'Install and update notifications' },
  labels: { chinese: '简体中文', english: 'English', retry: 'Check again', demo: 'Development preview' },
};

function initialLocale(): Locale {
  const saved = window.localStorage.getItem(preferenceKey);
  if (saved === 'zh-CN' || saved === 'en-US') return saved;
  return 'zh-CN';
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
