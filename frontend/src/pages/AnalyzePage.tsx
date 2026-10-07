import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useCompanies, useProducts, useRegulations } from '../hooks';
import { runAnalysis } from '../api';
import PageHeader from '../components/PageHeader';
import Spinner from '../components/Spinner';
import ErrorBox from '../components/ErrorBox';

const inputCls =
  'w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500';

export default function AnalyzePage() {
  const { t } = useTranslation();
  const DEFAULT_QUERY = t('business.analyze.defaultQuery');
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
      setSubmitError(t('business.analyze.selectCompanyProduct'));
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
      setSubmitError(err?.response?.data?.detail ?? err?.message ?? t('business.analyze.requestFailed'));
      setSubmitting(false);
    }
  };

  return (
    <div>
      <PageHeader title={t('business.analyze.title')} desc={t('business.analyze.desc')} />
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
          <Spinner text={t('business.analyze.running')} />
        </div>
      ) : (
        <form onSubmit={onSubmit} className="max-w-2xl bg-white border border-gray-200 rounded-lg p-6">
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-slate-900 mb-1">{t('business.analyze.companyLabel')}</label>
              <select
                required
                className={inputCls}
                value={companyId}
                onChange={(e) => setCompanyId(e.target.value ? Number(e.target.value) : '')}
              >
                <option value="">{t('business.analyze.selectCompany')}</option>
                {(companies.data ?? []).map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-900 mb-1">{t('business.analyze.productLabel')}</label>
              <select
                required
                className={inputCls}
                value={productId}
                disabled={companyId === ''}
                onChange={(e) => setProductId(e.target.value ? Number(e.target.value) : '')}
              >
                <option value="">{companyId === '' ? t('business.analyze.selectCompanyFirst') : t('business.analyze.selectProduct')}</option>
                {(products.data ?? []).map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
              {companyId !== '' && !products.loading && (products.data ?? []).length === 0 && (
                <p className="mt-1 text-xs text-gray-400">{t('business.analyze.noProducts')}</p>
              )}
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-900 mb-1">
                {t('business.analyze.regulationLabel')} <span className="text-xs text-gray-400 font-normal">{t('business.analyze.regulationOptional')}</span>
              </label>
              <select
                className={inputCls}
                value={regulationId}
                onChange={(e) => setRegulationId(e.target.value ? Number(e.target.value) : '')}
              >
                <option value="">{t('business.analyze.allRegulations')}</option>
                {(regulations.data ?? []).map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.name}({r.jurisdiction})
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-900 mb-1">{t('business.analyze.questionLabel')}</label>
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
            {t('business.analyze.submit')}
          </button>
        </form>
      )}
    </div>
  );
}
