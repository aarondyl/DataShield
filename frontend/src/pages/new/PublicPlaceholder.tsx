import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import BrandLogo from '../../components/BrandLogo';
export default function PublicPlaceholder({ title, description, action='/choose' }: { title: string; description: string; action?: string }) {
  const { t } = useTranslation();
  return <main className="ds-public"><nav><Link to="/" className="ds-brand"><BrandLogo size={30}/><span>DataShield</span></Link><Link to="/login" className="ds-text-link">{t('appnew.auth.logIn')}</Link></nav><section><span className="ds-eyebrow">{t('appnew.landing.eyebrow')}</span><h1>{title}</h1><p>{description}</p><Link className="ds-button primary" to={action}>{t('appnew.publicPlaceholder.getStarted')} <span>→</span></Link></section></main>;
}
