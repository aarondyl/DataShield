import { Link } from 'react-router-dom';
import { useCompanies, useProducts, useAnalysisRuns, useActions } from '../hooks';
import StatCard from '../components/StatCard';
import RiskBadge from '../components/RiskBadge';
import PageHeader from '../components/PageHeader';
import Spinner from '../components/Spinner';
import EmptyState from '../components/EmptyState';
import ErrorBox from '../components/ErrorBox';

function fmtTime(s: string) {
  if (!s) return '-';
  const d = new Date(s);
  return Number.isNaN(d.getTime()) ? s : d.toLocaleString('zh-CN');
}

export default function DashboardPage() {
  const companies = useCompanies();
  const products = useProducts();
  const runs = useAnalysisRuns();
  const actions = useActions();

  const loading = companies.loading || products.loading || runs.loading || actions.loading;
  const error = companies.error || products.error || runs.error || actions.error;

  if (loading) return <Spinner />;
  if (error) {
    return (
      <ErrorBox
        message={error}
        onRetry={() => {
          companies.reload();
          products.reload();
          runs.reload();
          actions.reload();
        }}
      />
    );
  }

  const companyList = companies.data ?? [];
  const runList = runs.data ?? [];
  const actionList = actions.data ?? [];
  const highRiskCount = runList.filter((r) => r.risk_level === 'high').length;
  const recent = runList.slice(0, 5);

  return (
    <div>
      <PageHeader title="DataShield 总览" desc="从企业与产品档案出发，完成规则自查、法规影响分析和整改闭环" />
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
        <StatCard label="企业 Company" value={companyList[0]?.name ?? '未创建'} hint={companyList[0]?.industry} />
        <StatCard label="产品数量 Products" value={products.data?.length ?? 0} />
        <StatCard label="历史分析 Analyses" value={runList.length} />
        <StatCard label="High Risk" value={highRiskCount} />
        <StatCard label="Pending Actions" value={actionList.length} />
      </div>

      <div className="mt-8 grid grid-cols-1 md:grid-cols-2 gap-4">
        <Link to="/assessment" className="block bg-indigo-600 text-white rounded-xl p-5 hover:bg-indigo-700">
          <div className="font-semibold">开始合规自查</div>
          <div className="text-sm text-indigo-100 mt-1">使用 DataShield 35 条规则生成评分、风险与整改路线图</div>
        </Link>
        <Link to="/analyze" className="block bg-slate-900 text-white rounded-xl p-5 hover:bg-slate-800">
          <div className="font-semibold">运行法规影响分析</div>
          <div className="text-sm text-slate-300 mt-1">使用法规库、RAG 检索和 Agent 判断产品受到的法规影响</div>
        </Link>
      </div>

      <h2 className="mt-8 mb-3 text-base font-semibold text-slate-900">最近法规影响分析</h2>
      {recent.length === 0 ? (
        <EmptyState message="暂无分析记录,请前往 Analyze 页面发起分析" />
      ) : (
        <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50 text-left text-gray-500 border-b border-gray-200">
                <th className="px-4 py-2.5 font-medium">产品</th>
                <th className="px-4 py-2.5 font-medium">企业</th>
                <th className="px-4 py-2.5 font-medium">Risk Level</th>
                <th className="px-4 py-2.5 font-medium">相关性</th>
                <th className="px-4 py-2.5 font-medium">状态</th>
                <th className="px-4 py-2.5 font-medium">时间</th>
              </tr>
            </thead>
            <tbody>
              {recent.map((r) => (
                <tr key={r.id} className="border-b border-gray-100 last:border-0 hover:bg-gray-50">
                  <td className="px-4 py-2.5">
                    <Link to={`/report/${r.id}`} className="text-indigo-600 hover:underline">
                      {r.product_name}
                    </Link>
                  </td>
                  <td className="px-4 py-2.5 text-gray-600">{r.company_name}</td>
                  <td className="px-4 py-2.5">
                    <RiskBadge level={r.risk_level} />
                  </td>
                  <td className="px-4 py-2.5 text-gray-600">
                    {r.relevant === null ? '不确定' : r.relevant ? 'YES' : 'NO'}
                  </td>
                  <td className="px-4 py-2.5 text-gray-600">{r.status}</td>
                  <td className="px-4 py-2.5 text-gray-500">{fmtTime(r.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
