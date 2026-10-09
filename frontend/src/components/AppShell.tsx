import { useEffect, useState } from 'react';
import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { fetchMe, type MeResponse } from '../api/auth';
import { readSession, writeSession, type LocalSession } from '../features/auth/session'; import { readSetup } from '../features/onboarding/state';
import { listCompanies, listProducts } from '../api';
import type { Company, Product } from '../types';
import Spinner from './Spinner';
import LanguageSwitcher from './LanguageSwitcher';
import BrandLogo from './BrandLogo';
import ErrorBoundary from './ErrorBoundary';

const nav = [
  { to: '/app/today', labelKey: 'today', icon: 'sun' },
  { to: '/app/workspaces', labelKey: 'workspaces', icon: 'workspaces' },
  { to: '/app/monitor', labelKey: 'monitor', icon: 'pulse' },
  { to: '/app/regulations', labelKey: 'regulations', icon: 'book' },
  { to: '/app/findings', labelKey: 'findings', icon: 'finding' },
  { to: '/app/actions', labelKey: 'actions', icon: 'check' },
  { to: '/app/product', labelKey: 'product', icon: 'cube' },
];

function Icon({ name }: { name: string }) {
  const paths: Record<string, React.ReactNode> = {
    sun: <><circle cx="12" cy="12" r="3.5"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></>,
    pulse: <path d="M3 12h4l2-5 4 10 2-5h6"/>,
    finding: <><circle cx="11" cy="11" r="7"/><path d="m16 16 5 5M11 8v4M11 15h.01"/></>,
    check: <><rect x="3" y="3" width="18" height="18" rx="4"/><path d="m8 12 2.5 2.5L16 9"/></>,
    cube: <><path d="m12 2 9 5-9 5-9-5 9-5Z"/><path d="m3 7 9 5 9-5M12 12v10M3 7v10l9 5 9-5V7"/></>,
    workspaces: <><rect x="3" y="3" width="8" height="8" rx="1"/><rect x="13" y="3" width="8" height="5" rx="1"/><rect x="13" y="10" width="8" height="11" rx="1"/><rect x="3" y="13" width="8" height="8" rx="1"/></>,
    book: <><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2Z"/></>,
  };
  return <svg viewBox="0 0 24 24" aria-hidden="true">{paths[name]}</svg>;
}

export default function AppShell() {
  const navigate=useNavigate();
  const { t } = useTranslation();
  const [session,setSession]=useState<LocalSession|null>(readSession());
  const [me,setMe]=useState<MeResponse|null>(null);
  const [checking,setChecking]=useState(true);
  const [companies,setCompanies]=useState<Company[]>([]);
  const [products,setProducts]=useState<Product[]>([]);
  const [setup,setSetup]=useState(readSetup());
  useEffect(()=>{let stopped=false;
    if(window.datashieldDesktop){const local=readSession();setMe({session:'evaluation',company_id:local?.companyId||0,edition:local?.edition||'developer'});setChecking(false);return()=>{stopped=true}}
    fetchMe().then(result=>{if(stopped)return;setMe(result);
      const previous=readSession();
      const next:LocalSession='user_id' in result
        ?{name:previous?.name||result.email.split('@')[0],email:result.email,edition:result.edition,companyName:previous?.companyName,companyId:result.company_id}
        :{name:previous?.name||'Demo',email:previous?.email||'demo@datashield.local',edition:previous?.edition||(result.edition==='enterprise'?'enterprise':'developer'),companyName:previous?.companyName||'Demo workspace',companyId:result.company_id};
      writeSession(next);setSession(next);
    }).catch(err=>{if(err?.response?.status===401)navigate('/login');
    }).finally(()=>{if(!stopped)setChecking(false)});
    return()=>{stopped=true}},[navigate]);
  useEffect(()=>{if(!window.datashieldDesktop)return;const refresh=()=>listCompanies().then(rows=>setCompanies(rows)).catch(()=>{});void refresh();window.addEventListener('datashield:workspaces-changed',refresh);return()=>window.removeEventListener('datashield:workspaces-changed',refresh)},[]);
  useEffect(()=>{if(!window.datashieldDesktop||!session?.companyId)return;const refresh=()=>listProducts(session.companyId).then(rows=>{
    setProducts(rows);
    let saved:ReturnType<typeof readSetup>=null;try{saved=JSON.parse(localStorage.getItem(`datashield.setup.company.${session.companyId}`)||'null')||readSetup()}catch{};if(saved?.companyId!==session.companyId)saved=null;
    const product=rows.find(item=>item.id===saved?.productId)||rows[0];
    if(product){const value=saved?.productId===product.id?saved:{companyId:session.companyId,productId:product.id,productName:product.name,markets:product.target_markets||[],method:'manual' as const};setSetup(value);localStorage.setItem(`datashield.setup.company.${session.companyId}`,JSON.stringify(value));localStorage.setItem('datashield.setup.v1',JSON.stringify(value))}
    else setProducts([]);
  }).catch(()=>setProducts([]));void refresh();window.addEventListener('datashield:products-changed',refresh);return()=>window.removeEventListener('datashield:products-changed',refresh)},[session?.companyId]);
  const changeCompany=(id:number)=>{const company=companies.find(item=>item.id===id);if(!company||!session)return;const next={...session,companyId:company.id,companyName:company.name};writeSession(next);setSession(next);setProducts([]);let saved:ReturnType<typeof readSetup>=null;try{saved=JSON.parse(localStorage.getItem(`datashield.setup.company.${company.id}`)||'null')}catch{};setSetup(saved);if(saved)localStorage.setItem('datashield.setup.v1',JSON.stringify(saved));else localStorage.removeItem('datashield.setup.v1')};
  const changeProduct=(id:number)=>{const product=products.find(item=>item.id===id);if(!product||!session)return;const value={companyId:session.companyId,productId:product.id,productName:product.name,markets:product.target_markets||[],method:'manual' as const};setSetup(value);localStorage.setItem(`datashield.setup.company.${session.companyId}`,JSON.stringify(value));localStorage.setItem('datashield.setup.v1',JSON.stringify(value))};
  const isDemo=!window.datashieldDesktop&&me!==null&&!('user_id' in me);
  if(checking)return <Spinner text={t('appnew.shell.loadingWorkspace')}/>;
  return <div className="ds-shell">
    <aside className="ds-sidebar">
      <NavLink to="/app/today" className="ds-brand"><BrandLogo size={30}/><span>DataShield</span></NavLink>
      <div className="ds-workspace"><span>{t('appnew.shell.workspace')}</span>{window.datashieldDesktop&&companies.length>0?<select aria-label={t('appnew.shell.selectWorkspace')} value={session?.companyId||''} onChange={e=>changeCompany(Number(e.target.value))}>{companies.map(company=><option key={company.id} value={company.id}>{company.name}</option>)}</select>:<strong>{setup?.productName||session?.companyName||t('appnew.shell.myProduct')}</strong>}{window.datashieldDesktop&&products.length>0&&<select aria-label={t('appnew.shell.selectProduct')} value={setup?.productId||''} onChange={e=>changeProduct(Number(e.target.value))}>{products.map(product=><option key={product.id} value={product.id}>{product.name}</option>)}</select>}<small>{session?.edition==='enterprise'?t('appnew.shell.enterpriseEdition'):t('appnew.shell.developerEdition')}</small></div>
      <nav aria-label={t('appnew.shell.primaryNav')}>{nav.filter(item=>item.labelKey!=='workspaces'||window.datashieldDesktop).map(item => <NavLink key={item.to} to={item.to} className={({isActive}) => `ds-nav-link${isActive ? ' active' : ''}`}><Icon name={item.icon}/><span>{t(`appnew.shell.nav.${item.labelKey}`)}</span></NavLink>)}</nav>
      <div className="ds-sidebar-bottom">
        <NavLink to="/app/settings" className="ds-nav-link"><Icon name="cube"/><span>{t('appnew.shell.settings')}</span></NavLink>
        <LanguageSwitcher/>
        <div className="ds-profile" title={session?.email||undefined}><span>{(session?.name||session?.email||'D')[0].toUpperCase()}</span><div><strong>{session?.name||session?.email||t('appnew.shell.demo')}</strong><small>{window.datashieldDesktop?t('appnew.auth.localMode.profile'):isDemo?t('appnew.shell.demoWorkspace'):session?.email||t('appnew.shell.localSession')}</small></div></div>
      </div>
    </aside>
    <main className="ds-main"><ErrorBoundary><Outlet/></ErrorBoundary></main>
  </div>;
}
