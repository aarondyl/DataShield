import { useTranslation } from 'react-i18next';

export default function LanguageSwitcher() {
  const { i18n } = useTranslation();
  const current = i18n.language?.toLowerCase().startsWith('zh') ? 'zh' : 'en';
  return (
    <div className="ds-lang-switch" role="group" aria-label="Language">
      <button type="button" className={current === 'zh' ? 'active' : ''} onClick={() => i18n.changeLanguage('zh')}>中</button>
      <button type="button" className={current === 'en' ? 'active' : ''} onClick={() => i18n.changeLanguage('en')}>EN</button>
    </div>
  );
}
