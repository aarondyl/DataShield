import client from './client';
import type {Edition, LocalSession} from '../features/auth/session';
import {readSession} from '../features/auth/session';

export type EvaluationStart={name:string;email:string;company_name:string;edition:Edition};
export const startEvaluation=(input:EvaluationStart)=>client.post('/v1/evaluation/start',input).then(r=>r.data as {company_id:number;edition:Edition;expires_at:string});
export const currentEvaluation=()=>client.get('/v1/evaluation/me').then(r=>r.data);
export const createEvaluationProduct=(input:{name:string;description:string;markets:string[];category?:string})=>{
  if(window.datashieldDesktop){const session=readSession();if(!session)throw new Error('本地工作区已退出，请重新创建工作区');return client.post('/v1/evaluation/products',{...input,company_id:session.companyId}).then(r=>r.data)}
  return client.post('/v1/evaluation/products',input).then(r=>r.data);
};
export const signOutEvaluation=()=>client.post('/v1/evaluation/signout').then(r=>r.data);
export const createDemoWorkspace=()=>client.post('/v1/evaluation/demo').then(r=>r.data as {company_id:number;product_id:number;product_name:string;edition:Edition;finding_ids:number[]});
export const runInitialReview=async(productId:number)=>{
  if(window.datashieldDesktop){const session=readSession();if(!session)throw new Error('本地工作区已退出');const requirements=await client.get<Array<{id:number}>>('/v1/local-regulations/requirements').then(r=>r.data);if(!requirements.length)throw new Error('本地法规库暂无可分析条款，请先同步或导入法规资料。');return client.post<any>('/v1/tenant-agent/analyze',{tenant_id:session.companyId,product_id:productId,trigger_type:'MANUAL_SCAN',requirement_ids:requirements.map(item=>item.id)}).then(r=>({run_id:r.data.run_id,status:r.data.status,finding_ids:r.data.finding_ids||[],missing_context:r.data.missing_context||[]})) as Promise<{run_id:number;status:string;finding_ids:number[];missing_context:any[]}>}
  return client.post(`/v1/evaluation/products/${productId}/initial-review`).then(r=>r.data as {run_id:number;status:string;finding_ids:number[];missing_context:any[]});
};
export const beginSession=async(input:EvaluationStart):Promise<LocalSession>=>{const result=await startEvaluation(input);return{name:input.name,email:input.email,edition:result.edition,companyName:input.company_name,companyId:result.company_id}};
