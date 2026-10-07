import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { listAssessments, listDeveloperIssues } from '../api';
import { useProducts } from '../hooks';
import type { Assessment, DeveloperIssue } from '../types';

export default function DeveloperHomePage() {
  const { t } = useTranslation();
  const products = useProducts(); const product = products.data?.[0];
  const [assessment,setAssessment]=useState<Assessment|null>(null); const [issues,setIssues]=useState<DeveloperIssue[]>([]);
  useEffect(()=>{if(!product)return; listAssessments(product.id).then((items)=>setAssessment(items[0]??null)); listDeveloperIssues(product.id).then(setIssues).catch(()=>setIssues([]));},[product?.id]);
  const open=useMemo(()=>issues.filter((item)=>item.status!=='resolved'),[issues]); const high=open.filter((item)=>item.risk_level==='high').length;
  const statusRows=[['privacyPolicy',product?.has_privacy_policy?'passed':'needsAttention'],['thirdPartySdk',product?.uses_third_party_sdk?'reviewRequired':'passed'],['userRights',assessment?.answers?.right_delete&&assessment?.answers?.right_withdraw?'passed':'needsAttention'],['dataTransfer',product?.cross_border_data_transfer?'reviewRequired':'passed']];
  return <div className="developer-dashboard"><section className="developer-status-hero"><span className="eyebrow">DATASHIELD STATUS / {product?.name??t('developer.home.noProduct')}</span><div className="status-hero-grid"><div><h1>{open.length}<small> {t('developer.home.issues')}</small></h1><p>{t('developer.home.heroSummary',{high,open:open.length})}</p></div><Link className="primary-link" to={product?'/developer/check':'/developer/product'}>{product?t('developer.home.checkCta'):t('developer.home.createCta')} <span>→</span></Link></div></section>
    <section className="status-list">{statusRows.map(([label,status])=><article key={label as string}><span>{t(`developer.home.checks.${label}`)}</span><strong className={status==='passed'?'low':status==='needsAttention'?'high':'medium'}>{t(`developer.home.checkStatus.${status}`)}</strong></article>)}</section>
    <section className="journey-actions">{[['01','Check','check','/developer/check'],['02','Fix','fix','/developer/issues'],['03','Ship','ship','/developer/ready']].map(([n,en,id,to])=><Link to={to} key={en}><b>{n}</b><span className="eyebrow">{en}</span><h2>{t(`developer.home.journey.${id}.title`)}</h2><p>{t(`developer.home.journey.${id}.copy`)}</p><i>{t('developer.home.continue')}</i></Link>)}</section>
  </div>;
}
