import { useTranslation } from 'react-i18next';
export default function RoutePlaceholder({ eyebrow, title, description }: { eyebrow: string; title: string; description: string }) {
  const { t } = useTranslation();
  return <div className="ds-page"><header className="ds-page-header"><span className="ds-eyebrow">{eyebrow}</span><h1>{title}</h1><p>{description}</p></header><section className="ds-empty"><div className="ds-empty-mark">D</div><h2>{t('appnew.routePlaceholder.title')}</h2><p>{t('appnew.routePlaceholder.body')}</p></section></div>;
}
