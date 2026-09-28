import { useState } from 'react';
import { useCompanies } from '../hooks';
import { createCompany, updateCompany } from '../api';
import type { Company } from '../types';
import PageHeader from '../components/PageHeader';
import Spinner from '../components/Spinner';
import EmptyState from '../components/EmptyState';
import ErrorBox from '../components/ErrorBox';
import Tag from '../components/Tag';

interface FormState {
  name: string;
  industry: string;
  country: string;
  target_markets: string;
  business_model: string;
}

const emptyForm: FormState = { name: '', industry: '', country: '', target_markets: '', business_model: '' };

const inputCls =
  'w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500';

export default function CompanyPage() {
  const { data, loading, error, reload } = useCompanies();
  const [editing, setEditing] = useState<Company | null>(null);
  const [form, setForm] = useState<FormState>(emptyForm);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const startEdit = (c: Company) => {
    setEditing(c);
    setForm({
      name: c.name,
      industry: c.industry,
      country: c.country,
      target_markets: c.target_markets.join(', '),
      business_model: c.business_model,
    });
  };

  const resetForm = () => {
    setEditing(null);
    setForm(emptyForm);
    setSubmitError(null);
  };

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setSubmitError(null);
    const payload = {
      name: form.name.trim(),
      industry: form.industry.trim(),
      country: form.country.trim(),
      target_markets: form.target_markets
        .split(/[,，]/)
        .map((s) => s.trim())
        .filter(Boolean),
      business_model: form.business_model.trim(),
    };
    try {
      if (editing) {
        await updateCompany(editing.id, payload);
      } else {
        await createCompany(payload);
      }
      resetForm();
      reload();
    } catch (err: any) {
      setSubmitError(err?.response?.data?.detail ?? err?.message ?? '保存失败');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div>
      <PageHeader title="企业画像" desc="维护企业合规背景，分析代理将自动读取这些信息" />
      {loading ? (
        <Spinner />
      ) : error ? (
        <ErrorBox message={error} onRetry={reload} />
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 space-y-4">
            {(data ?? []).length === 0 ? (
              <EmptyState message="暂无企业,请在右侧创建" />
            ) : (
              (data ?? []).map((c) => (
                <div key={c.id} className="bg-white border border-gray-200 rounded-lg p-5">
                  <div className="flex items-start justify-between">
                    <div>
                      <div className="text-base font-semibold text-slate-900">{c.name}</div>
                      <div className="mt-1 text-sm text-gray-500">
                        {c.industry} · {c.country} · {c.business_model}
                      </div>
                      <div className="mt-2">
                        {c.target_markets.map((m) => (
                          <Tag key={m}>{m}</Tag>
                        ))}
                      </div>
                    </div>
                    <button
                      onClick={() => startEdit(c)}
                      className="text-sm text-indigo-600 hover:underline shrink-0"
                    >
                      编辑
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>

          <form onSubmit={onSubmit} className="bg-white border border-gray-200 rounded-lg p-5 h-fit">
            <div className="text-sm font-semibold text-slate-900 mb-4">
              {editing ? `编辑企业 #${editing.id}` : '创建企业'}
            </div>
            <div className="space-y-3">
              <div>
                <label className="block text-xs text-gray-500 mb-1">企业名称 *</label>
                <input
                  required
                  className={inputCls}
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">行业</label>
                <input
                  className={inputCls}
                  value={form.industry}
                  onChange={(e) => setForm({ ...form, industry: e.target.value })}
                  placeholder="如软件服务 / 电子商务 / 金融科技"
                />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">所在国家</label>
                <input
                  className={inputCls}
                  value={form.country}
                  onChange={(e) => setForm({ ...form, country: e.target.value })}
                />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">目标市场(逗号分隔)</label>
                <input
                  className={inputCls}
                  value={form.target_markets}
                  onChange={(e) => setForm({ ...form, target_markets: e.target.value })}
                  placeholder="EU, US, UK"
                />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">商业模式</label>
                <input
                  className={inputCls}
                  value={form.business_model}
                  onChange={(e) => setForm({ ...form, business_model: e.target.value })}
                  placeholder="如 B2B 订阅制"
                />
              </div>
            </div>
            {submitError && <div className="mt-3 text-xs text-red-600">{submitError}</div>}
            <div className="mt-4 flex gap-2">
              <button
                type="submit"
                disabled={submitting}
                className="px-4 py-2 bg-indigo-600 text-white text-sm rounded-md hover:bg-indigo-700 disabled:opacity-50"
              >
                {submitting ? '保存中…' : editing ? '保存修改' : '创建'}
              </button>
              {editing && (
                <button
                  type="button"
                  onClick={resetForm}
                  className="px-4 py-2 border border-gray-300 text-sm rounded-md text-gray-600 hover:bg-gray-50"
                >
                  取消
                </button>
              )}
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
