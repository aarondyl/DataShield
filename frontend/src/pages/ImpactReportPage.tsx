import { useParams, Link } from 'react-router-dom';
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

const confidenceLabel: Record<string, string> = {
  high: '高 High',
  medium: '中 Medium',
  low: '低 Low',
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
  const { id } = useParams();
  const numId = Number(id);
  const { data, loading, error, reload } = useAnalysis(numId);

  if (loading) return <Spinner text="加载报告中…" />;
  if (error || !data) return <ErrorBox message={error ?? '报告不存在'} onRetry={reload} />;

  return (
    <div>
      <div className="mb-4">
        <Link to="/" className="text-sm text-indigo-600 hover:underline">
          ← 返回 Dashboard
        </Link>
      </div>
      <PageHeader
        title={`Impact Report #${data.id}`}
        desc={`生成时间:${new Date(data.created_at).toLocaleString('zh-CN')} · LLM Mode: ${data.llm_mode}`}
      />

      {data.status === 'degraded' && (
        <div className="mb-4 bg-yellow-50 border border-yellow-200 text-yellow-800 text-sm rounded-lg px-4 py-3">
          提示:本次分析为降级(degraded)结果 —— LLM 服务不可用,以下内容基于规则/检索降级生成,仅供参考。
        </div>
      )}
      {data.status === 'failed' && (
        <div className="mb-4 bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-4 py-3">
          本次分析失败(failed),以下数据可能不完整。
        </div>
      )}

      <div className="space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Section title="Risk Level 风险等级">
            <div className="flex items-center gap-3">
              <RiskBadge level={data.risk_level} />
              {data.confidence && (
                <span className="text-sm text-gray-500">置信度 Confidence:{confidenceLabel[data.confidence]}</span>
              )}
            </div>
          </Section>
          <Section title="Relevant 是否相关">
            <span
              className={`inline-block px-3 py-1 text-sm font-medium border rounded ${
                data.relevant === true
                  ? 'bg-indigo-50 text-indigo-700 border-indigo-200'
                  : data.relevant === false
                    ? 'bg-gray-100 text-gray-600 border-gray-200'
                    : 'bg-gray-50 text-gray-500 border-gray-200'
              }`}
            >
              {data.relevant === null ? '不确定' : data.relevant ? 'YES' : 'NO'}
            </span>
          </Section>
        </div>

        <Section title="Why 分析结论">
          <p className="text-sm text-gray-700 whitespace-pre-wrap">{data.summary || '无摘要'}</p>
          {data.reasoning_summary && (
            <div className="mt-3 pt-3 border-t border-gray-100">
              <div className="text-xs text-gray-400 mb-1">Reasoning Summary 推理摘要</div>
              <p className="text-sm text-gray-600 whitespace-pre-wrap">{data.reasoning_summary}</p>
            </div>
          )}
        </Section>

        <Section title="Affected Areas 受影响领域">
          {data.affected_areas.length === 0 && data.affected_products.length === 0 ? (
            <span className="text-sm text-gray-400">无</span>
          ) : (
            <div>
              {data.affected_products.length > 0 && (
                <div className="mb-2">
                  <span className="text-xs text-gray-400 mr-2">受影响产品:</span>
                  {data.affected_products.map((p) => (
                    <Tag key={p}>{p}</Tag>
                  ))}
                </div>
              )}
              <div>
                <span className="text-xs text-gray-400 mr-2">受影响领域:</span>
                {data.affected_areas.map((a) => (
                  <Tag key={a}>{a}</Tag>
                ))}
              </div>
            </div>
          )}
        </Section>

        <Section title={`Evidence 证据条款(${data.evidence.length})`}>
          {data.evidence.length === 0 ? (
            <span className="text-sm text-gray-400">无证据条款</span>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-gray-50 text-left text-gray-500 border-b border-gray-200">
                    <th className="px-3 py-2 font-medium">法规</th>
                    <th className="px-3 py-2 font-medium">条款</th>
                    <th className="px-3 py-2 font-medium">原文摘要</th>
                    <th className="px-3 py-2 font-medium">Reason</th>
                    <th className="px-3 py-2 font-medium">Source</th>
                    <th className="px-3 py-2 font-medium">Verified</th>
                  </tr>
                </thead>
                <tbody>
                  {data.evidence.map((ev, i) => (
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
                            链接
                          </a>
                        ) : (
                          <span className="text-gray-300">-</span>
                        )}
                      </td>
                      <td className="px-3 py-2">
                        {ev.verified ? (
                          <span className="text-green-700 text-xs font-medium">✓ 已验证</span>
                        ) : (
                          <span className="text-gray-400 text-xs">未验证</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Section>

        <Section title={`Recommended Actions 建议行动(${data.actions.length})`}>
          {data.actions.length === 0 ? (
            <span className="text-sm text-gray-400">无建议行动</span>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-gray-50 text-left text-gray-500 border-b border-gray-200">
                    <th className="px-3 py-2 font-medium">Priority</th>
                    <th className="px-3 py-2 font-medium">Department</th>
                    <th className="px-3 py-2 font-medium">Title</th>
                    <th className="px-3 py-2 font-medium">Description</th>
                    <th className="px-3 py-2 font-medium">关联条款</th>
                  </tr>
                </thead>
                <tbody>
                  {data.actions.map((a, i) => (
                    <tr key={i} className="border-b border-gray-100 last:border-0 align-top">
                      <td className="px-3 py-2">
                        <span
                          className={`inline-block px-2 py-0.5 text-xs font-medium border rounded ${
                            priorityStyles[a.priority] ?? 'bg-gray-100 text-gray-600 border-gray-200'
                          }`}
                        >
                          {a.priority.toUpperCase()}
                        </span>
                      </td>
                      <td className="px-3 py-2 text-gray-700">{a.department}</td>
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
