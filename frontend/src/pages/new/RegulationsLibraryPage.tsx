import { useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import client from '../../api/client';
import { listRegulations, getRegulation } from '../../api';
import type { Regulation, RegulationArticle, RegulationDetail } from '../../types';
import Spinner from '../../components/Spinner';
import ErrorBox from '../../components/ErrorBox';

const COLLAPSE_AT = 300;

interface ArticleSection {
  number: string;
  title: string;
  text: string;
}

interface SearchHit {
  key: string;
  regulation: string;
  article: string;
  title: string;
  text: string;
}

function groupSections(articles: RegulationArticle[]): ArticleSection[] {
  const map = new Map<string, { number: string; title: string; parts: string[] }>();
  for (const a of articles) {
    let s = map.get(a.article_number);
    if (!s) {
      s = { number: a.article_number, title: a.title, parts: [] };
      map.set(a.article_number, s);
    }
    const body = a.content.startsWith(a.title) ? a.content.slice(a.title.length).trim() : a.content;
    s.parts.push(body);
  }
  return [...map.values()].map(({ parts, ...rest }) => ({ ...rest, text: parts.filter(Boolean).join('\n') }));
}

function highlight(text: string, query: string) {
  const q = query.trim();
  if (!q) return text;
  const parts = text.split(new RegExp(`(${q.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi'));
  return parts.map((p, i) => (i % 2 === 1 ? <mark key={i}>{p}</mark> : p));
}

function ArticleText({ text, query }: { text: string; query?: string }) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const long = text.length > COLLAPSE_AT;
  const shown = open || !long ? text : `${text.slice(0, COLLAPSE_AT)}…`;
  return (
    <div className="ds-reg-text">
      <p>{highlight(shown, query ?? '')}</p>
      {long && (
        <button className="ds-reg-toggle" onClick={() => setOpen(!open)}>
          {open ? t('appnew.regulations.collapse') : t('appnew.regulations.expandFull')}
        </button>
      )}
    </div>
  );
}

export default function RegulationsLibraryPage() {
  const { t, i18n } = useTranslation();
  const [regs, setRegs] = useState<Regulation[] | null>(null);
  const [error, setError] = useState('');

  const [openId, setOpenId] = useState<number | null>(null);
  const [details, setDetails] = useState<Record<number, RegulationDetail>>({});
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState('');
  const detailsRef = useRef<Record<number, RegulationDetail>>({});

  const [query, setQuery] = useState('');
  const [hits, setHits] = useState<SearchHit[] | null>(null);
  const [searching, setSearching] = useState(false);
  const [localMode, setLocalMode] = useState(false);

  const load = () => {
    setError('');
    setRegs(null);
    listRegulations()
      .then(setRegs)
      .catch((e: any) => setError(e?.response?.data?.detail || e.message));
  };
  useEffect(load, []);

  const loadDetail = async (id: number) => {
    if (detailsRef.current[id]) return detailsRef.current[id];
    const d = await getRegulation(id);
    detailsRef.current = { ...detailsRef.current, [id]: d };
    setDetails(detailsRef.current);
    return d;
  };

  const fetchDetail = async (id: number) => {
    setDetailError('');
    setDetailLoading(true);
    try {
      await loadDetail(id);
    } catch (e: any) {
      setDetailError(e?.response?.data?.detail || e.message);
    } finally {
      setDetailLoading(false);
    }
  };

  const toggle = (r: Regulation) => {
    if (openId === r.id) {
      setOpenId(null);
      return;
    }
    setOpenId(r.id);
    if (!details[r.id]) fetchDetail(r.id);
  };

  useEffect(() => {
    const q = query.trim();
    if (!q) {
      setHits(null);
      setSearching(false);
      setLocalMode(false);
      return;
    }
    let cancelled = false;
    setSearching(true);
    const timer = setTimeout(async () => {
      try {
        const { data } = await client.post('/v1/legal-search', { query: q, top_k: 20 });
        if (cancelled) return;
        setLocalMode(false);
        setHits(
          (data.results ?? []).map((r: any) => ({
            key: String(r.chunk_id),
            regulation: r.regulation_name,
            article: r.article,
            title: r.summary || '',
            text: r.content.startsWith(r.article) ? r.content.slice(r.article.length).trim() : r.content,
          }))
        );
        setSearching(false);
      } catch {
        try {
          const all = await Promise.all((regs ?? []).map((r) => loadDetail(r.id)));
          if (cancelled) return;
          const lower = q.toLowerCase();
          const local: SearchHit[] = [];
          for (const d of all) {
            for (const s of groupSections(d.articles ?? [])) {
              if (`${s.number} ${s.title} ${s.text}`.toLowerCase().includes(lower)) {
                local.push({ key: `${d.id}:${s.number}`, regulation: d.name, article: s.number, title: s.title, text: s.text });
              }
            }
          }
          setLocalMode(true);
          setHits(local);
          setSearching(false);
        } catch {
          if (!cancelled) {
            setHits([]);
            setSearching(false);
          }
        }
      }
    }, 300);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query, regs]);

  const hitGroups = useMemo(() => {
    if (!hits) return null;
    const m = new Map<string, SearchHit[]>();
    for (const h of hits) {
      const arr = m.get(h.regulation) ?? [];
      arr.push(h);
      m.set(h.regulation, arr);
    }
    return [...m.entries()];
  }, [hits]);

  const fmtDate = (s: string | null) => {
    if (!s) return '';
    const d = new Date(s);
    return Number.isNaN(d.getTime())
      ? s
      : d.toLocaleDateString(i18n.language === 'zh' ? 'zh-CN' : 'en', { year: 'numeric', month: 'short', day: 'numeric' });
  };

  const q = query.trim();

  return (
    <div className="ds-page">
      <header className="ds-page-header">
        <span className="ds-eyebrow">{t('appnew.regulations.eyebrow')}</span>
        <h1>{t('appnew.regulations.title')}</h1>
        <p>{t('appnew.regulations.subtitle')}</p>
      </header>

      <div className="ds-reg-search">
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <circle cx="11" cy="11" r="7" />
          <path d="m16 16 5 5" />
        </svg>
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={t('appnew.regulations.searchPlaceholder')}
          aria-label={t('appnew.regulations.searchPlaceholder')}
        />
        {query && <button onClick={() => setQuery('')}>{t('appnew.regulations.clearSearch')}</button>}
      </div>

      {error ? (
        <ErrorBox message={t('appnew.regulations.loadError')} onRetry={load} />
      ) : !regs ? (
        <Spinner text={t('appnew.regulations.loading')} />
      ) : q ? (
        <>
          {localMode && !searching && <p className="ds-reg-note">{t('appnew.regulations.localModeNote')}</p>}
          {searching ? (
            <Spinner text={t('appnew.regulations.searching')} />
          ) : !hitGroups || hitGroups.length === 0 ? (
            <div className="ds-empty">
              <span className="ds-empty-mark">?</span>
              <h2>{t('appnew.regulations.noResultsTitle')}</h2>
              <p>{t('appnew.regulations.noResultsBody')}</p>
            </div>
          ) : (
            <div className="ds-reg-hits">
              {hitGroups.map(([name, group]) => (
                <section className="ds-reg-hitgroup" key={name}>
                  <header>
                    <h2>{name}</h2>
                    <span>{t('appnew.regulations.hits', { count: group.length })}</span>
                  </header>
                  {group.map((h) => (
                    <article className="ds-reg-article" key={h.key}>
                      <h3>
                        {highlight(h.article, q)}
                        {h.title && h.title !== h.article && <small>{highlight(h.title, q)}</small>}
                      </h3>
                      <ArticleText text={h.text} query={q} />
                    </article>
                  ))}
                </section>
              ))}
            </div>
          )}
        </>
      ) : regs.length === 0 ? (
        <div className="ds-empty">
          <span className="ds-empty-mark">§</span>
          <h2>{t('appnew.regulations.emptyTitle')}</h2>
          <p>{t('appnew.regulations.emptyBody')}</p>
        </div>
      ) : (
        <div className="ds-reg-list">
          {regs.map((r) => (
            <article className={`ds-reg-card${openId === r.id ? ' open' : ''}`} key={r.id}>
              <button className="ds-reg-head" onClick={() => toggle(r)} aria-expanded={openId === r.id}>
                <div>
                  <div className="ds-reg-title-row">
                    <h2>{r.name}</h2>
                    <span className="ds-reg-tag">{r.jurisdiction}</span>
                  </div>
                  <div className="ds-reg-meta">
                    <span>
                      {r.effective_at
                        ? t('appnew.regulations.effective', { date: fmtDate(r.effective_at) })
                        : t('appnew.regulations.effectiveUnknown')}
                    </span>
                    <span>{t('appnew.regulations.articleCount', { count: r.article_count })}</span>
                  </div>
                  {r.description && <p>{r.description}</p>}
                  {r.source_url && <span className="ds-reg-src">{r.source_url}</span>}
                </div>
                <span className="ds-reg-chevron">
                  {openId === r.id ? t('appnew.regulations.collapseArticles') : t('appnew.regulations.expandArticles')}
                </span>
              </button>
              {openId === r.id && (
                <div className="ds-reg-articles">
                  {detailLoading ? (
                    <Spinner text={t('appnew.regulations.loadingArticles')} />
                  ) : detailError ? (
                    <ErrorBox message={t('appnew.regulations.articlesLoadError')} onRetry={() => fetchDetail(r.id)} />
                  ) : (details[r.id]?.articles?.length ?? 0) === 0 ? (
                    <div className="ds-reg-noart">{t('appnew.regulations.noArticles')}</div>
                  ) : (
                    groupSections(details[r.id].articles).map((s) => {
                      const heading = s.title && s.title.startsWith(s.number) ? s.title : `${s.number} ${s.title}`.trim();
                      return (
                        <section className="ds-reg-article" key={s.number}>
                          <h3>{heading}</h3>
                          <ArticleText text={s.text} />
                        </section>
                      );
                    })
                  )}
                </div>
              )}
            </article>
          ))}
        </div>
      )}
    </div>
  );
}
