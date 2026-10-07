import { useParams, Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAnalysis } from '../hooks';
import RiskBadge from '../components/RiskBadge';
import Tag from '../components/Tag';
import Spinner from '../components/Spinner';
import ErrorBox from '../components/ErrorBox';
import PageHeader from '../components/PageHeader';

const priorityStyles: Record<string, string> = {
  high: 'bg-red-100 text-red-800 border-red-200',
  medium: 'bg-yellow-100 text-yellow-800 border-yellow-200',
  low: 'bg-green-100 text-green-800 border-green-200',
};

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="bg-white border border-gray-200 rounded-lg p-5">
      <h2 className="text-sm font-semibold text-slate-900 mb-4">{title}</h2>
      {children}
    </section>
  );
}

export default function ImpactReportPage() {
  const { t, i18n } = useTranslation();
  const { id } = useParams();
  const numId = Number(id);
  const { data, loading, error, reload } = useAnalysis(numId);

  const confidenceLabel: Record<string, string> = {
    high: t('misc.impactReport.confidenceLevel.high'),
    medium: t('misc.impactReport.confidenceLevel.medium'),
    low: t('misc.impactReport.confidenceLevel.low'),
  };

  const priorityLabel: Record<string, string> = {
    high: t('misc.impactReport.priority.high'),
    medium: t('misc.impactReport.priority.medium'),
    low: t('misc.impactReport.priority.low'),
  };

  const modelModeLabel: Record<string, string> = {
    api: t('misc.impactReport.modelMode.api'),
    mock: t('misc.impactReport.modelMode.mock'),
  };

  const departmentLabel: Record<string, string> = {
    Legal: t('misc.impactReport.department.legal'),
    Product: t('misc.impactReport.department.product'),
    Engineering: t('misc.impactReport.department.engineering'),
    Security: t('misc.impactReport.department.security'),
    Operations: t('misc.impactReport.department.operations'),
    'Supply Chain': t('misc.impactReport.department.supplyChain'),
    Management: t('misc.impactReport.department.management'),
  };

  if (loading) return <Spinner text={t('misc.impactReport.loading')} />;
  if (error || !data) return <ErrorBox message={error ?? t('misc.impactReport.notFound')} onRetry={reload} />;

  const affectedAreas = data.affected_areas ?? [];
  const affectedProducts = data.affected_products ?? [];
  const evidence = data.evidence ?? [];
  const actions = data.actions ?? [];

  return (
    <div>
      <div className="mb-4">
        <Link to="/" className="text-sm text-indigo-600 hover:underline">
          {t('misc.impactReport.backToOverview')}
        </Link>
      </div>
      <PageHeader
        title={t('misc.impactReport.title', { id: data.id })}
        desc={t('misc.impactReport.meta', {
          time: new Date(data.created_at).toLocaleString(i18n.language),
          mode: modelModeLabel[data.llm_mode] ?? t('misc.impactReport.modelMode.custom'),
        })}
      />

      {data.status === 'degraded' && (
        <div className="mb-4 bg-yellow-50 border border-yellow-200 text-yellow-800 text-sm rounded-lg px-4 py-3">
          {t('misc.impactReport.degradedNotice')}
        </div>
      )}
      {data.status === 'failed' && (
        <div className="mb-4 bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-4 py-3">
          {t('misc.impactReport.failedNotice')}
        </div>
      )}

      <div className="space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Section title={t('misc.impactReport.riskLevel')}>
            <div className="flex items-center gap-3">
              <RiskBadge level={data.risk_level} />
              {data.confidence && (
                <span className="text-sm text-gray-500">{t('misc.impactReport.confidence', { label: confidenceLabel[data.confidence] })}</span>
              )}
            </div>
          </Section>
          <Section title={t('misc.impactReport.relevance')}>
            <span
              className={`inline-block px-3 py-1 text-sm font-medium border rounded ${
                data.relevant === true
                  ? 'bg-indigo-50 text-indigo-700 border-indigo-200'
                  : data.relevant === false
                    ? 'bg-gray-100 text-gray-600 border-gray-200'
                    : 'bg-gray-50 text-gray-500 border-gray-200'
              }`}
            >
              {data.relevant === null ? t('misc.impactReport.relevantUncertain') : data.relevant ? t('misc.impactReport.relevantYes') : t('misc.impactReport.relevantNo')}
            </span>
          </Section>
        </div>

        <Section title={t('misc.impactReport.conclusion')}>
          <p className="text-sm text-gray-700 whitespace-pre-wrap">{data.summary || t('misc.impactReport.noSummary')}</p>
          {data.reasoning_summary && (
            <div className="mt-3 pt-3 border-t border-gray-100">
              <div className="text-xs text-gray-400 mb-1">{t('misc.impactReport.reasoning')}</div>
              <p className="text-sm text-gray-600 whitespace-pre-wrap">{data.reasoning_summary}</p>
            </div>
          )}
        </Section>

        <Section title={t('misc.impactReport.affectedScope')}>
          {affectedAreas.length === 0 && affectedProducts.length === 0 ? (
            <span className="text-sm text-gray-400">{t('misc.impactReport.none')}</span>
          ) : (
            <div>
              {affectedProducts.length > 0 && (
                <div className="mb-2">
                  <span className="text-xs text-gray-400 mr-2">{t('misc.impactReport.affectedProducts')}</span>
                  {affectedProducts.map((p) => (
                    <Tag key={p}>{p}</Tag>
                  ))}
                </div>
              )}
              <div>
                <span className="text-xs text-gray-400 mr-2">{t('misc.impactReport.affectedAreas')}</span>
                {affectedAreas.map((a) => (
                  <Tag key={a}>{a}</Tag>
                ))}
              </div>
            </div>
          )}
        </Section>

        <Section title={t('misc.impactReport.evidenceTitle', { count: evidence.length })}>
          {evidence.length === 0 ? (
            <span className="text-sm text-gray-400">{t('misc.impactReport.noEvidence')}</span>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-gray-50 text-left text-gray-500 border-b border-gray-200">
                    <th className="px-3 py-2 font-medium">{t('misc.impactReport.table.regulation')}</th>
                    <th className="px-3 py-2 font-medium">{t('misc.impactReport.table.article')}</th>
                    <th className="px-3 py-2 font-medium">{t('misc.impactReport.table.excerpt')}</th>
                    <th className="px-3 py-2 font-medium">{t('misc.impactReport.table.reason')}</th>
                    <th className="px-3 py-2 font-medium">{t('misc.impactReport.table.source')}</th>
                    <th className="px-3 py-2 font-medium">{t('misc.impactReport.table.verification')}</th>
                  </tr>
                </thead>
                <tbody>
                  {evidence.map((ev, i) => (
                    <tr key={i} className="border-b border-gray-100 last:border-0 align-top">
                      <td className="px-3 py-2 text-gray-700">{ev.regulation}</td>
                      <td className="px-3 py-2 text-gray-700 whitespace-nowrap">{ev.article}</td>
                      <td className="px-3 py-2 text-gray-600 max-w-md">
                        <div className="line-clamp-3" title={ev.content}>
                          {ev.content}
                        </div>
                      </td>
                      <td className="px-3 py-2 text-gray-600 max-w-xs">{ev.reason}</td>
                      <td className="px-3 py-2">
                        {ev.source_url ? (
                          <a
                            href={ev.source_url}
                            target="_blank"
                            rel="noreferrer"
                            className="text-indigo-600 hover:underline text-xs break-all"
                          >
                            {t('misc.impactReport.link')}
                          </a>
                        ) : (
                          <span className="text-gray-300">-</span>
                        )}
                      </td>
                      <td className="px-3 py-2">
                        {ev.verified ? (
                          <span className="text-green-700 text-xs font-medium">{t('misc.impactReport.verified')}</span>
                        ) : (
                          <span className="text-gray-400 text-xs">{t('misc.impactReport.unverified')}</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Section>

        <Section title={t('misc.impactReport.actionsTitle', { count: actions.length })}>
          {actions.length === 0 ? (
            <span className="text-sm text-gray-400">{t('misc.impactReport.noActions')}</span>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-gray-50 text-left text-gray-500 border-b border-gray-200">
                    <th className="px-3 py-2 font-medium">{t('misc.impactReport.actionTable.priority')}</th>
                    <th className="px-3 py-2 font-medium">{t('misc.impactReport.actionTable.department')}</th>
                    <th className="px-3 py-2 font-medium">{t('misc.impactReport.actionTable.taskTitle')}</th>
                    <th className="px-3 py-2 font-medium">{t('misc.impactReport.actionTable.description')}</th>
                    <th className="px-3 py-2 font-medium">{t('misc.impactReport.actionTable.relatedClause')}</th>
                  </tr>
                </thead>
                <tbody>
                  {actions.map((a, i) => (
                    <tr key={i} className="border-b border-gray-100 last:border-0 align-top">
                      <td className="px-3 py-2">
                        <span
                          className={`inline-block px-2 py-0.5 text-xs font-medium border rounded ${
                            priorityStyles[a.priority] ?? 'bg-gray-100 text-gray-600 border-gray-200'
                          }`}
                        >
                          {priorityLabel[a.priority] ?? t('misc.impactReport.priority.unrated')}
                        </span>
                      </td>
                      <td className="px-3 py-2 text-gray-700">{departmentLabel[a.department] ?? a.department}</td>
                      <td className="px-3 py-2 text-slate-900 font-medium">{a.title}</td>
                      <td className="px-3 py-2 text-gray-600 max-w-md">{a.description}</td>
                      <td className="px-3 py-2 text-xs text-gray-500">
                        {a.evidence?.regulation || a.evidence?.article
                          ? `${a.evidence.regulation} ${a.evidence.article}`
                          : '-'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Section>
      </div>
    </div>
  );
}
