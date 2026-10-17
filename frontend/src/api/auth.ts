import client from './client';
import type {Edition} from '../features/auth/session';

export type RegisterInput={email:string;password:string;name:string;company_name:string;edition:Edition};
export type AuthUser={user_id:number;email:string;company_id:number;edition:Edition;email_verified:boolean};
export type EvaluationMe={session:'evaluation';company_id:number;edition:string};
export type MeResponse=AuthUser|EvaluationMe;
export function parseMeResponse(value:unknown):MeResponse {
  if(!value||typeof value!=='object'||Array.isArray(value))throw new Error('身份服务返回了无效响应，请检查服务地址或稍后重试。');
  const record=value as Record<string,unknown>;
  if(typeof record.user_id==='number'&&typeof record.email==='string'&&typeof record.company_id==='number'&&typeof record.edition==='string'&&typeof record.email_verified==='boolean')return record as AuthUser;
  if(record.session==='evaluation'&&typeof record.company_id==='number'&&typeof record.edition==='string')return record as EvaluationMe;
  throw new Error('身份服务返回了无法识别的响应，请检查服务地址或稍后重试。');
}
export const register=(input:RegisterInput)=>client.post('/v1/auth/register',input).then(r=>r.data as AuthUser);
export const login=(input:{email:string;password:string})=>client.post('/v1/auth/login',input).then(r=>r.data as AuthUser);
export const logout=()=>client.post('/v1/auth/logout').then(r=>r.data as {signed_out:boolean});
export const fetchMe=()=>client.get<unknown>('/v1/auth/me').then(r=>parseMeResponse(r.data));
