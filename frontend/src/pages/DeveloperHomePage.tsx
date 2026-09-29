import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { listAssessments, listDeveloperIssues } from '../api';
import { useProducts } from '../hooks';
import type { Assessment, DeveloperIssue } from '../types';

export default function DeveloperHomePage() {
  const products = useProducts(); const product = products.data?.[0];
  const [assessment,setAssessment]=useState<Assessment|null>(null); const [issues,setIssues]=useState<DeveloperIssue[]>([]);
  useEffect(()=>{if(!product)return; listAssessments(product.id).then((items)=>setAssessment(items[0]??null)); listDeveloperIssues(product.id).then(setIssues).catch(()=>setIssues([]));},[product?.id]);
  const open=useMemo(()=>issues.filter((item)=>item.status!=='resolved'),[issues]); const high=open.filter((item)=>item.risk_level==='high').length;
  const statusRows=[['Privacy Policy',product?.has_privacy_policy?'Passed':'Needs Attention'],['Third-party SDK',product?.uses_third_party_sdk?'Review Required':'Passed'],['User Rights',assessment?.answers?.right_delete&&assessment?.answers?.right_withdraw?'Passed':'Needs Attention'],['Data Transfer',product?.cross_border_data_transfer?'Review Required':'Passed']];
  return <div className="developer-dashboard"><section className="developer-status-hero"><span className="eyebrow">DATASHIELD STATUS / {product?.name??'尚未创建产品'}</span><div className="status-hero-grid"><div><h1>{open.length}<small> Issues</small></h1><p>{high} High Risk · {open.length} Pending Fixes</p></div><Link className="primary-link" to={product?'/developer/check':'/developer/product'}>{product?'检查我的产品':'先创建产品档案'} <span>→</span></Link></div></section>
    <section className="status-list">{statusRows.map(([label,status])=><article key={label as string}><span>{label}</span><strong className={status==='Passed'?'low':status==='Needs Attention'?'high':'medium'}>{status}</strong></article>)}</section>
    <section className="journey-actions">{[['01','Check','检查我的产品','扫描产品行为、SDK、权限和隐私政策。','/developer/check'],['02','Fix','修复发现的问题','查看 Why 与 Fix It，逐项完成整改。','/developer/issues'],['03','Ship','上线前确认','确认基础检查是否通过，准备上线。','/developer/ready']].map(([n,en,zh,copy,to])=><Link to={to} key={en}><b>{n}</b><span className="eyebrow">{en}</span><h2>{zh}</h2><p>{copy}</p><i>继续 →</i></Link>)}</section>
  </div>;
}
