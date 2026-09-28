import { useState } from 'react';
import { useRegulations } from '../hooks';
import { getRegulation, uploadRegulation } from '../api';
import type { Regulation, RegulationDetail } from '../types';
import PageHeader from '../components/PageHeader';
import Spinner from '../components/Spinner';
import EmptyState from '../components/EmptyState';
import ErrorBox from '../components/ErrorBox';
import Tag from '../components/Tag';

const inputCls =
  'w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500';

function fmtDate(s: string | null) {
  if (!s) return '-';
  const d = new Date(s);
  return Number.isNaN(d.getTime()) ? s : d.toLocaleDateString('zh-CN');
}

export default function RegulationsPage() {
  const { data, loading, error, reload } = useRegulations();
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [detail, setDetail] = useState<RegulationDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const [file, setFile] = useState<File | null>(null);
  const [upForm, setUpForm] = useState({ name: '', jurisdiction: '', description: '', source_url: '' });
  const [uploading, setUploading] = useState(false);
  const [uploadMsg, setUploadMsg] = useState<string | null>(null);

  const toggleDetail = async (r: Regulation) => {
    if (expandedId === r.id) {
      setExpandedId(null);
      setDetail(null);
      return;
    }
    setExpandedId(r.id);
    setDetail(null);
    setDetailLoading(true);
    try {
      setDetail(await getRegulation(r.id));
    } catch {
      setDetail(null);
    } finally {
      setDetailLoading(false);
    }
  };

  const onUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) {
      setUploadMsg('请选择文件(.txt / .md / .pdf)');
      return;
    }
    setUploading(true);
    setUploadMsg(null);
    const fd = new FormData();
    fd.append('file', file);
    fd.append('name', upForm.name.trim());
    fd.append('jurisdiction', upForm.jurisdiction.trim());
    fd.append('description', upForm.description.trim());
    fd.append('source_url', upForm.source_url.trim());
    try {
      const res = await uploadRegulation(fd);
      setUploadMsg(`上传成功:${res.name},已导入 ${res.articles_ingested} 条条款`);
      setFile(null);
      setUpForm({ name: '', jurisdiction: '', description: '', source_url: '' });
      reload();
    } catch (err: any) {
      setUploadMsg(`上传失败:${err?.response?.data?.detail ?? err?.message ?? '未知错误'}`);
    } finally {
      setUploading(false);
    }
  };

  return (
    <div>
      <PageHeader title="法规情报中心" desc="查看法规与条款明细,或上传新的法规文件" />
      {loading ? (
        <Spinner />
      ) : error ? (
        <ErrorBox message={error} onRetry={reload} />
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 space-y-4">
            {(data ?? []).length === 0 ? (
              <EmptyState message="法规库为空,请在右侧上传法规文件" />
            ) : (
              (data ?? []).map((r) => (
                <div key={r.id} className="bg-white border border-gray-200 rounded-lg">
                  <button
                    onClick={() => toggleDetail(r)}
                    className="w-full text-left p-5 hover:bg-gray-50 rounded-lg"
                  >
                    <div className="flex items-center justify-between">
                      <div className="text-base font-semibold text-slate-900">{r.name}</div>
                      <span className="text-xs text-gray-400">{expandedId === r.id ? '收起 ▲' : '查看条款 ▼'}</span>
                    </div>
                    <div className="mt-1 text-sm text-gray-500">
                      <Tag>{r.jurisdiction}</Tag>
                      <span className="ml-1">{r.article_count} 条条款</span>
                      <span className="ml-3">生效:{fmtDate(r.effective_at)}</span>
                    </div>
                    {r.description && <p className="mt-2 text-sm text-gray-600">{r.description}</p>}
                    {r.source_url && (
                      <span className="mt-1 inline-block text-xs text-indigo-600">{r.source_url}</span>
                    )}
                  </button>
                  {expandedId === r.id && (
                    <div className="border-t border-gray-200 px-5 py-4">
                      {detailLoading ? (
                        <Spinner text="加载条款中…" />
                      ) : !detail || detail.articles.length === 0 ? (
                        <div className="text-sm text-gray-400 py-2">无条款数据</div>
                      ) : (
                        <div className="space-y-3 max-h-96 overflow-auto pr-2">
                          {detail.articles.map((a) => (
                            <div key={a.id} className="border border-gray-100 rounded-md p-3 bg-gray-50">
                              <div className="text-sm font-medium text-slate-900">
                                {a.article_number} {a.title}
                                {a.topic && <span className="ml-2 text-xs text-gray-400">[{a.topic}]</span>}
                              </div>
                              <p className="mt-1 text-xs text-gray-600 whitespace-pre-wrap">{a.content}</p>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              ))
            )}
          </div>

          <form onSubmit={onUpload} className="bg-white border border-gray-200 rounded-lg p-5 h-fit">
            <div className="text-sm font-semibold text-slate-900 mb-4">上传法规</div>
            <div className="space-y-3">
              <div>
                <label className="block text-xs text-gray-500 mb-1">法规文件 * (.txt / .md / .pdf)</label>
                <input
                  type="file"
                  accept=".txt,.md,.pdf"
                  className="w-full text-sm text-gray-600 file:mr-3 file:px-3 file:py-1.5 file:border file:border-gray-300 file:rounded-md file:text-sm file:bg-gray-50 file:text-gray-700"
                  onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">法规名称 *</label>
                <input
                  required
                  className={inputCls}
                  value={upForm.name}
                  onChange={(e) => setUpForm({ ...upForm, name: e.target.value })}
                />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">适用地区 *</label>
                <input
                  required
                  className={inputCls}
                  value={upForm.jurisdiction}
                  onChange={(e) => setUpForm({ ...upForm, jurisdiction: e.target.value })}
                  placeholder="如 EU / US-CA / CN"
                />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">简介</label>
                <textarea
                  className={inputCls}
                  rows={2}
                  value={upForm.description}
                  onChange={(e) => setUpForm({ ...upForm, description: e.target.value })}
                />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">来源网址</label>
                <input
                  className={inputCls}
                  value={upForm.source_url}
                  onChange={(e) => setUpForm({ ...upForm, source_url: e.target.value })}
                  placeholder="https://…"
                />
              </div>
            </div>
            {uploadMsg && (
              <div className={`mt-3 text-xs ${uploadMsg.startsWith('上传成功') ? 'text-green-700' : 'text-red-600'}`}>
                {uploadMsg}
              </div>
            )}
            <button
              type="submit"
              disabled={uploading}
              className="mt-4 px-4 py-2 bg-indigo-600 text-white text-sm rounded-md hover:bg-indigo-700 disabled:opacity-50"
            >
              {uploading ? '上传中…' : '上传'}
            </button>
          </form>
        </div>
      )}
    </div>
  );
}
