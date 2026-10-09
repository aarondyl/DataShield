import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import CompanyPage from '../CompanyPage';
import ProductsPage from '../ProductsPage';

export default function WorkspaceHubPage() {
  const { t } = useTranslation();
  const [section, setSection] = useState<'companies' | 'products'>('products');
  return <div className="ds-page ds-workspace-hub">
    <header className="ds-page-header"><span className="ds-eyebrow">{t('appnew.workspaceHub.eyebrow')}</span><h1>{t('appnew.workspaceHub.title')}</h1><p>{t('appnew.workspaceHub.subtitle')}</p></header>
    <div className="ds-workspace-tabs" role="tablist" aria-label={t('appnew.workspaceHub.title')}>
      <button role="tab" aria-selected={section === 'products'} className={section === 'products' ? 'active' : ''} onClick={() => setSection('products')}>{t('appnew.workspaceHub.products')}</button>
      <button role="tab" aria-selected={section === 'companies'} className={section === 'companies' ? 'active' : ''} onClick={() => setSection('companies')}>{t('appnew.workspaceHub.companies')}</button>
    </div>
    {section === 'products' ? <ProductsPage mode="business" /> : <CompanyPage />}
  </div>;
}
