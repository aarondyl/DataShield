import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useCompanies, useProducts } from '../hooks';
import { createCompany, createProduct, updateProduct } from '../api';
import type { Product, ProductPayload } from '../types';
import PageHeader from '../components/PageHeader';
import Spinner from '../components/Spinner';
import EmptyState from '../components/EmptyState';
import ErrorBox from '../components/ErrorBox';
import Tag from '../components/Tag';

const boolFields: { key: keyof ProductPayload; labelKey: string }[] = [
  { key: 'collects_personal_data', labelKey: 'collectsPersonalData' },
  { key: 'collects_sensitive_data', labelKey: 'collectsSensitiveData' },
  { key: 'collects_health_data', labelKey: 'collectsHealthData' },
  { key: 'collects_location_data', labelKey: 'collectsLocationData' },
  { key: 'children_related', labelKey: 'childrenRelated' },
  { key: 'third_party_data_sharing', labelKey: 'thirdPartyDataSharing' },
  { key: 'uses_third_party_sdk', labelKey: 'usesThirdPartySdk' },
  { key: 'has_privacy_policy', labelKey: 'hasPrivacyPolicy' },
  { key: 'cross_border_data_transfer', labelKey: 'crossBorderDataTransfer' },
];

interface FormState {
  company_id: number | '';
  name: string;
  category: string;
  target_markets: string;
  description: string;
  third_party_sdks: string;
  flags: Record<string, boolean>;
}

const emptyForm = (companyId: number | '' = ''): FormState => ({
  company_id: companyId,
  name: '',
  category: '',
  target_markets: '',
  description: '',
  third_party_sdks: '',
  flags: Object.fromEntries(boolFields.map((f) => [f.key, false])),
});

const inputCls =
  'w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500';

export default function ProductsPage({ mode = 'business' }: { mode?: 'business' | 'developer' }) {
  const { t } = useTranslation();
  const isDeveloper = mode === 'developer';
  const companies = useCompanies();
  const products = useProducts();
  const [editing, setEditing] = useState<Product | null>(null);
  const [form, setForm] = useState<FormState>(emptyForm());
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const companyName = useMemo(() => {
    const map = new Map<number, string>();
    (companies.data ?? []).forEach((c) => map.set(c.id, c.name));
    return (id: number) => map.get(id) ?? `#${id}`;
  }, [companies.data]);

  const startEdit = (p: Product) => {
    setEditing(p);
    setForm({
      company_id: p.company_id,
      name: p.name,
      category: p.category,
      target_markets: p.target_markets.join(', '),
      description: p.description,
      third_party_sdks: p.third_party_sdks.join(', '),
      flags: Object.fromEntries(boolFields.map((f) => [f.key, Boolean(p[f.key as keyof Product])])),
    });
  };

  const resetForm = () => {
    setEditing(null);
    setForm(emptyForm());
    setSubmitError(null);
  };

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!isDeveloper && form.company_id === '') {
      setSubmitError(t('business.products.companyRequired'));
      return;
    }
    setSubmitting(true);
    setSubmitError(null);
    try {
      let companyId = form.company_id;
      if (isDeveloper && companyId === '') {
        companyId = companies.data?.[0]?.id ?? (await createCompany({
          name: '独立开发者',
          industry: '软件与互联网',
          country: '',
          target_markets: [],
          business_model: '独立开发',
        })).id;
      }
      const payload: ProductPayload = {
        company_id: companyId as number,
        name: form.name.trim(),
        category: form.category.trim(),
        target_markets: form.target_markets
          .split(/[,，]/)
          .map((s) => s.trim())
          .filter(Boolean),
        description: form.description.trim(),
        third_party_sdks: form.third_party_sdks.split(/[,，]/).map((s) => s.trim()).filter(Boolean),
        privacy_policy_text: editing?.privacy_policy_text ?? '',
        ...(form.flags as Record<string, boolean>),
      } as ProductPayload;
      if (editing) {
        await updateProduct(editing.id, payload);
      } else {
        await createProduct(payload);
      }
      resetForm();
      products.reload();
    } catch (err: any) {
      setSubmitError(err?.response?.data?.detail ?? err?.message ?? t('business.common.saveFailed'));
    } finally {
      setSubmitting(false);
    }
  };

  const loading = companies.loading || products.loading;
  const error = companies.error || products.error;

  return (
    <div>
      <PageHeader title={isDeveloper ? t('business.products.titleDev') : t('business.products.title')} desc={isDeveloper ? t('business.products.descDev') : t('business.products.desc')} />
      {loading ? (
        <Spinner />
      ) : error ? (
        <ErrorBox message={error} onRetry={products.reload} />
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2">
            {(products.data ?? []).length === 0 ? (
              <EmptyState message={isDeveloper ? t('business.products.emptyDev') : t('business.products.empty')} />
            ) : (
              <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="bg-gray-50 text-left text-gray-500 border-b border-gray-200">
                      <th className="px-4 py-2.5 font-medium">{isDeveloper ? t('business.products.headerNameDev') : t('business.products.headerName')}</th>
                      {!isDeveloper && <th className="px-4 py-2.5 font-medium">{t('business.products.headerCompany')}</th>}
                      <th className="px-4 py-2.5 font-medium">{t('business.products.headerCategory')}</th>
                      <th className="px-4 py-2.5 font-medium">{t('business.products.headerMarkets')}</th>
                      <th className="px-4 py-2.5 font-medium">{t('business.products.headerFlags')}</th>
                      <th className="px-4 py-2.5 font-medium"></th>
                    </tr>
                  </thead>
                  <tbody>
                    {(products.data ?? []).map((p) => (
                      <tr key={p.id} className="border-b border-gray-100 last:border-0 align-top">
                        <td className="px-4 py-2.5 font-medium text-slate-900">{p.name}</td>
                        {!isDeveloper && <td className="px-4 py-2.5 text-gray-600">{companyName(p.company_id)}</td>}
                        <td className="px-4 py-2.5 text-gray-600">{p.category || '-'}</td>
                        <td className="px-4 py-2.5 text-gray-600">{p.target_markets.join(', ') || '-'}</td>
                        <td className="px-4 py-2.5">
                          {boolFields
                            .filter((f) => p[f.key as keyof Product])
                            .map((f) => (
                              <Tag key={f.key}>{t(`business.products.flags.${f.labelKey}`)}</Tag>
                            ))}
                        </td>
                        <td className="px-4 py-2.5">
                          <button onClick={() => startEdit(p)} className="text-indigo-600 hover:underline">
                            {t('business.common.edit')}
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          <form onSubmit={onSubmit} className="bg-white border border-gray-200 rounded-lg p-5 h-fit">
            <div className="text-sm font-semibold text-slate-900 mb-4">
              {editing ? t('business.products.editTitle', { id: editing.id }) : t(isDeveloper ? 'business.products.createTitleDev' : 'business.products.createTitle')}
            </div>
            <div className="space-y-3">
              {!isDeveloper && <div>
                <label className="block text-xs text-gray-500 mb-1">{t('business.products.companyLabel')}</label>
                <select
                  required
                  className={inputCls}
                  value={form.company_id}
                  onChange={(e) => setForm({ ...form, company_id: e.target.value ? Number(e.target.value) : '' })}
                >
                  <option value="">{t('business.common.pleaseSelect')}</option>
                  {(companies.data ?? []).map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name}
                    </option>
                  ))}
                </select>
              </div>}
              <div>
                <label className="block text-xs text-gray-500 mb-1">{isDeveloper ? t('business.products.nameLabelDev') : t('business.products.nameLabel')} *</label>
                <input
                  required
                  className={inputCls}
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">{isDeveloper ? t('business.products.categoryLabelDev') : t('business.products.categoryLabel')}</label>
                {isDeveloper ? <select required className={inputCls} value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })}><option value="">{t('business.common.pleaseSelect')}</option>{['App','SaaS','Website','Mini Program','AI Product'].map((type)=><option key={type}>{type}</option>)}</select> : <input className={inputCls} value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })} placeholder={t('business.products.categoryPlaceholder')}/>}
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">{t('business.products.marketsLabel')}</label>
                <input
                  className={inputCls}
                  value={form.target_markets}
                  onChange={(e) => setForm({ ...form, target_markets: e.target.value })}
                  placeholder="EU, US"
                />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">{isDeveloper ? t('business.products.descLabelDev') : t('business.products.descLabel')}</label>
                <textarea
                  className={inputCls}
                  rows={3}
                  value={form.description}
                  onChange={(e) => setForm({ ...form, description: e.target.value })}
                />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-2">{t('business.products.flagsLabel')}</label>
                <div className="grid grid-cols-2 gap-2">
                  {boolFields.map((f) => (
                    <label key={f.key} className="flex items-center gap-2 text-sm text-gray-700">
                      <input
                        type="checkbox"
                        className="h-4 w-4 border-gray-300 rounded text-indigo-600"
                        checked={Boolean(form.flags[f.key])}
                        onChange={(e) => setForm({ ...form, flags: { ...form.flags, [f.key]: e.target.checked } })}
                      />
                      {t(`business.products.flags.${f.labelKey}`)}
                    </label>
                  ))}
                </div>
              </div>
              {isDeveloper && <div><label className="block text-xs text-gray-500 mb-1">{t('business.products.sdkLabel')}</label><input className={inputCls} value={form.third_party_sdks} onChange={(e)=>setForm({...form,third_party_sdks:e.target.value})} placeholder={t('business.products.sdkPlaceholder')}/></div>}
            </div>
            {submitError && <div className="mt-3 text-xs text-red-600">{submitError}</div>}
            <div className="mt-4 flex gap-2">
              <button
                type="submit"
                disabled={submitting}
                className="px-4 py-2 bg-indigo-600 text-white text-sm rounded-md hover:bg-indigo-700 disabled:opacity-50"
              >
                {submitting ? t('business.common.saving') : editing ? t('business.common.saveChanges') : t('business.common.create')}
              </button>
              {editing && (
                <button
                  type="button"
                  onClick={resetForm}
                  className="px-4 py-2 border border-gray-300 text-sm rounded-md text-gray-600 hover:bg-gray-50"
                >
                  {t('business.common.cancel')}
                </button>
              )}
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
