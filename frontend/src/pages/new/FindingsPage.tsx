import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { getFinding, getFindings } from '../../api/intelligence';
import FeedbackCorrection from '../../components/FeedbackCorrection';

const lower = (s: unknown) => String(s ?? '').toLowerCase();
const sevLabel = (t: any, s: string) => t(`appnew.findings.severity.${s}`, { defaultValue: s });
const gapLabel = (t: any, s: string = '') => t(`appnew.findings.gapStatus.${s}`, { defaultValue: s });
const fieldLabel = (t: any, s: string = '') =>
  t(`appnew.findings.factFields.${s.replace(/\./g, '_')}`, {
    defaultValue: t(`appnew.findings.factFields.${s.split('.')[0]}`, { defaultValue: s }),
  });

// 兼容旧数据：后端文本里的系统术语统一换成人话；英文旧原文保持原样显示。
const humanize = (t: any, s: string = '') =>
  s
    .replace(/Product\s*Twin\s*状态\s*[:：]\s*NOT_DETECTED/gi, t('appnew.findings.humanize.twinStatusNotDetected'))
    .replace(/Product\s*Twin/gi, t('appnew.findings.humanize.productTwin'))
    .replace(/NOT_DETECTED\s?/g, t('appnew.findings.humanize.notDetected'))
    .replace(/[Rr]equirements?\b/g, t('appnew.findings.humanize.requirement'));

const regName = (t: any, name: string = '') => t(`appnew.findings.regulationNames.${name}`, { defaultValue: name });

const articleLabel = (t: any, article: string = '') => {
  const m = /^\s*Article\s+(.+?)\s*$/i.exec(article);
  return m ? t('appnew.findings.articleLabel', { n: m[1] }) : article;
};

// 触发条件的取值：EU→欧盟、provider→服务提供方；未收录的值原样显示。
const factValue = (t: any, v: unknown): string => {
  if (Array.isArray(v)) return v.map((x) => factValue(t, x)).join(t('appnew.findings.listSeparator'));
  return t(`appnew.product.factNames.${String(v ?? '').toLowerCase()}`, { defaultValue: String(v ?? '') });
};

const applicabilityText = (t: any, app: any) => {
  if (!app) return '';
  if (app.applies === true) return t('appnew.findings.applicabilityMet');
  if (app.applies === false) return t('appnew.findings.applicabilityNotMet');
  return t('appnew.findings.applicabilityUnknown');
};

export function FindingsPage() {
  const { t } = useTranslation();
  const [rows, setRows] = useState<any[] | null>(null);
  const [error, setError] = useState('');
  useEffect(() => {
    getFindings().then(setRows).catch((e) => setError(e.message));
  }, []);
  return (
    <div className="ds-page">
      <header className="ds-page-header">
        <span className="ds-eyebrow">{t('appnew.findings.eyebrow')}</span>
        <h1>{t('appnew.findings.title')}</h1>
        <p>{t('appnew.findings.subtitle')}</p>
      </header>
      {error ? (
        <State title={t('appnew.findings.loadError')} text={error} />
      ) : !rows ? (
        <State title={t('appnew.findings.loading')} />
      ) : rows.length === 0 ? (
        <State title={t('appnew.findings.emptyTitle')} text={t('appnew.findings.emptyBody')} />
      ) : (
        <div className="ds-finding-list">
          {rows.map((f) => (
            <Link to={`/app/findings/${f.id}`} key={f.id}>
              <span className={`ds-severity ${lower(f.impact_level)}`}>{sevLabel(t, f.impact_level)}</span>
              <div>
                <h2>{f.title}</h2>
                <p>{humanize(t, f.gap_summary)}</p>
                <small>
                  {gapLabel(t, f.gap_status)} · {t('appnew.findings.confidence', { percent: Math.round((f.confidence ?? 0) * 100) })}
                </small>
              </div>
              <b>→</b>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

export function FindingDetailPage() {
  const { t } = useTranslation();
  const { id = '' } = useParams();
  const [d, setD] = useState<any>(null);
  const [error, setError] = useState('');
  useEffect(() => {
    getFinding(id).then(setD).catch((e) => setError(e.message));
  }, [id]);
  if (error) return <div className="ds-page"><State title={t('appnew.findings.detailLoadError')} text={error} /></div>;
  if (!d) return <div className="ds-page"><State title={t('appnew.findings.loadingEvidence')} /></div>;

  const f = d.finding ?? {};
  const app = d.applicability?.[0];
  const gap = d.gap?.[0];
  const requirements = Array.isArray(d.requirements) ? d.requirements : [];
  const legalEvidence = Array.isArray(d.legal_evidence) ? d.legal_evidence : [];
  const req = requirements[0];
  const actionLink = `/app/actions?finding=${f.id}`;
  const basisName = req?.regulation_name || legalEvidence[0]?.regulation_name || '';
  const basisArticle = legalEvidence.find((e: any) => e.legal_unit_id === req?.legal_unit_id)?.article || legalEvidence[0]?.article || '';

  return (
    <div className="ds-page ds-finding-detail">
      <Link className="ds-back" to="/app/findings">{t('appnew.findings.back')}</Link>
      <header>
        <div>
          <span className={`ds-severity ${lower(f.impact_level)}`}>{t('appnew.findings.impact', { level: sevLabel(t, f.impact_level) })}</span>
          <h1>{f.title}</h1>
        </div>
        <Link className="ds-button quiet" to={actionLink}>{t('appnew.findings.reviewAction')}</Link>
      </header>

      <Section n="01" title={t('appnew.findings.whatIsIt')}>
        <p>{humanize(t, f.gap_summary)}</p>
      </Section>

      <Section n="02" title={t('appnew.findings.legalBasis')}>
        {req || legalEvidence.length > 0 ? (
          <>
            <div className="ds-legal-basis">
              <b>{regName(t, basisName)}</b>
              {basisArticle && <span>{articleLabel(t, basisArticle)}</span>}
            </div>
            {req?.jurisdiction && (
              <p className="ds-legal-meta">{fieldLabel(t, 'jurisdiction')}{t('appnew.findings.fieldSeparator')}{factValue(t, req.jurisdiction)}</p>
            )}
            {req?.summary ? <p>{humanize(t, req.summary)}</p> : null}
            {legalEvidence.length > 0 && (
              <details>
                <summary>{t('appnew.findings.originalText')}</summary>
                {legalEvidence.map((e: any) => (
                  <article key={e.legal_unit_id}>
                    <b>{e.regulation_name} · {e.article}</b>
                    {e.heading && <small>{e.heading}</small>}
                    <p>{e.content}</p>
                    {e.source_url && (
                      <a href={e.source_url} target="_blank" rel="noreferrer">{t('appnew.findings.officialSource')}</a>
                    )}
                  </article>
                ))}
              </details>
            )}
          </>
        ) : (
          <p>{t('appnew.findings.noRequirement')}</p>
        )}
      </Section>

      <Section n="03" title={t('appnew.findings.whyApplies')}>
        <p>{applicabilityText(t, app) || humanize(t, f.applicability_summary)}</p>
        {(app?.matched_facts || []).length > 0 && (
          <div className="ds-proof-flow">
            {app.matched_facts.map((x: any) => (
              <span key={x.field}>{fieldLabel(t, x.field)}{t('appnew.findings.fieldSeparator')}{factValue(t, x.value)}</span>
            ))}
          </div>
        )}
      </Section>

      <Section n="04" title={t('appnew.findings.currentVsGap')}>
        <dl>
          <div>
            <dt>{t('appnew.findings.currentState')}</dt>
            <dd>{humanize(t, gap?.current_state || f.gap_summary)}</dd>
          </div>
          <div>
            <dt>{t('appnew.findings.requiredState')}</dt>
            <dd>{humanize(t, gap?.required_state || req?.summary || t('appnew.findings.reviewLinkedRequirement'))}</dd>
          </div>
          <div>
            <dt>{t('appnew.findings.evidenceStatus')}</dt>
            <dd>{gapLabel(t, f.gap_status)}</dd>
          </div>
        </dl>
      </Section>

      <FeedbackCorrection findingId={f.id} />

      <Section n="05" title={t('appnew.findings.whatToDo')}>
        <h3>{t('appnew.findings.recommendationTitle')}</h3>
        <p>{t('appnew.findings.recommendationBody')}</p>
        <Link className="ds-button primary" to={actionLink}>{t('appnew.findings.generateRecommendation')}</Link>
      </Section>
    </div>
  );
}

function Section({ n, title, children }: { n: string; title: string; children: React.ReactNode }) {
  return (
    <section className="ds-detail-section">
      <span>{n}</span>
      <div>
        <h2>{title}</h2>
        {children}
      </div>
    </section>
  );
}

function State({ title, text }: { title: string; text?: string }) {
  return (
    <div className="ds-state">
      <h2>{title}</h2>
      {text && <p>{text}</p>}
    </div>
  );
}
