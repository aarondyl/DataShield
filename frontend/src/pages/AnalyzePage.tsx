import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useCompanies, useProducts, useRegulations } from '../hooks';
import { runAnalysis } from '../api';
import PageHeader from '../components/PageHeader';
import Spinner from '../components/Spinner';
import ErrorBox from '../components/ErrorBox';

const DEFAULT_QUERY = '请分析该法规是否对我的产品产生影响。';

const inputCls =
  'w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500';

export default function AnalyzePage() {
  const navigate = useNavigate();
  const companies = useCompanies();
  const regulations = useRegulations();

  const [companyId, setCompanyId] = useState<number | ''>('');
  const [productId, setProductId] = useState<number | ''>('');
  const [regulationId, setRegulationId] = useState<number | ''>('');
  const [query, setQuery] = useState(DEFAULT_QUERY);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const products = useProducts(companyId === '' ? undefined : companyId);

  useEffect(() => {
    setProductId('');
  }, [companyId]);

  const loading = companies.loading || regulations.loading;
  const error = companies.error || regulations.error;

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (companyId === '' || productId === '') {
      setSubmitError('请选择企业与产品');
      return;
    }
    setSubmitting(true);
    setSubmitError(null);
    try {
      const result = await runAnalysis({
        company_id: companyId,
        product_id: productId,
        regulation_id: regulationId === '' ? null : regulationId,
        query: query.trim() || DEFAULT_QUERY,
      });
      navigate(`/report/${result.id}`);
    } catch (err: any) {
      setSubmitError(err?.response?.data?.detail ?? err?.message ?? '分析请求失败');
      setSubmitting(false);
    }
  };

  return (
    <div>
      <PageHeader title="发起法规影响分析" desc="选择企业与产品，系统将检索相关法规条款并评估影响" />
      {loading ? (
        <Spinner />
      ) : error ? (
        <ErrorBox
          message={error}
          onRetry={() => {
            companies.reload();
            regulations.reload();
          }}
        />
      ) : submitting ? (
        <div className="bg-white border border-gray-200 rounded-lg py-20">
          <Spinner text="分析中，大模型正在评估法规影响，请稍候…" />
        </div>
      ) : (
        <form onSubmit={onSubmit} className="max-w-2xl bg-white border border-gray-200 rounded-lg p-6">
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-slate-900 mb-1">企业 *</label>
              <select
                required
                className={inputCls}
                value={companyId}
                onChange={(e) => setCompanyId(e.target.value ? Number(e.target.value) : '')}
              >
                <option value="">请选择企业</option>
                {(companies.data ?? []).map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-900 mb-1">产品 *</label>
              <select
                required
                className={inputCls}
                value={productId}
                disabled={companyId === ''}
                onChange={(e) => setProductId(e.target.value ? Number(e.target.value) : '')}
              >
                <option value="">{companyId === '' ? '请先选择企业' : '请选择产品'}</option>
                {(products.data ?? []).map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
              {companyId !== '' && !products.loading && (products.data ?? []).length === 0 && (
                <p className="mt-1 text-xs text-gray-400">该企业暂无产品,请先在 产品合规护照页面创建</p>
              )}
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-900 mb-1">
                法规 <span className="text-xs text-gray-400 font-normal">(可选,不选则检索全部法规)</span>
              </label>
              <select
                className={inputCls}
                value={regulationId}
                onChange={(e) => setRegulationId(e.target.value ? Number(e.target.value) : '')}
              >
                <option value="">全部法规</option>
                {(regulations.data ?? []).map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.name}({r.jurisdiction})
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-900 mb-1">分析问题</label>
              <textarea
                className={inputCls}
                rows={4}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
            </div>
          </div>
          {submitError && <div className="mt-4 text-sm text-red-600">{submitError}</div>}
          <button
            type="submit"
            className="mt-6 px-5 py-2.5 bg-indigo-600 text-white text-sm font-medium rounded-md hover:bg-indigo-700"
          >
            开始影响分析
          </button>
        </form>
      )}
    </div>
  );
}
