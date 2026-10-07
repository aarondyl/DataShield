import client from './client';
import type {Edition, LocalSession} from '../features/auth/session';

export type EvaluationStart={name:string;email:string;company_name:string;edition:Edition};
export const startEvaluation=(input:EvaluationStart)=>client.post('/v1/evaluation/start',input).then(r=>r.data as {company_id:number;edition:Edition;expires_at:string});
export const currentEvaluation=()=>client.get('/v1/evaluation/me').then(r=>r.data);
export const createEvaluationProduct=(input:{name:string;description:string;markets:string[];category?:string})=>client.post('/v1/evaluation/products',input).then(r=>r.data);
export const signOutEvaluation=()=>client.post('/v1/evaluation/signout').then(r=>r.data);
export const createDemoWorkspace=()=>client.post('/v1/evaluation/demo').then(r=>r.data as {company_id:number;product_id:number;product_name:string;edition:Edition;finding_ids:number[]});
export const runInitialReview=(productId:number)=>client.post(`/v1/evaluation/products/${productId}/initial-review`).then(r=>r.data as {run_id:number;status:string;finding_ids:number[];missing_context:any[]});
export const beginSession=async(input:EvaluationStart):Promise<LocalSession>=>{const result=await startEvaluation(input);return{name:input.name,email:input.email,edition:result.edition,companyName:input.company_name,companyId:result.company_id}};
