import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import LanguageDetector from 'i18next-browser-languagedetector';
import zh from './locales/zh';
import en from './locales/en';

const htmlLang = (lng?: string) => (lng && lng.toLowerCase().startsWith('zh') ? 'zh-CN' : 'en');

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources: {
      zh: { translation: zh },
      en: { translation: en },
    },
    fallbackLng: 'zh',
    supportedLngs: ['zh', 'en'],
    nonExplicitSupportedLngs: true,
    detection: {
      order: ['localStorage', 'navigator'],
      lookupLocalStorage: 'datashield.lang',
      caches: ['localStorage'],
    },
    interpolation: { escapeValue: false },
  });

document.documentElement.lang = htmlLang(i18n.language);
i18n.on('languageChanged', (lng) => {
  document.documentElement.lang = htmlLang(lng);
});

export default i18n;
