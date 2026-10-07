import client from './client';
import type {Edition} from '../features/auth/session';

export type RegisterInput={email:string;password:string;name:string;company_name:string;edition:Edition};
export type AuthUser={user_id:number;email:string;company_id:number;edition:Edition;email_verified:boolean};
export type EvaluationMe={session:'evaluation';company_id:number;edition:string};
export type MeResponse=AuthUser|EvaluationMe;
export const register=(input:RegisterInput)=>client.post('/v1/auth/register',input).then(r=>r.data as AuthUser);
export const login=(input:{email:string;password:string})=>client.post('/v1/auth/login',input).then(r=>r.data as AuthUser);
export const logout=()=>client.post('/v1/auth/logout').then(r=>r.data as {signed_out:boolean});
export const fetchMe=()=>client.get('/v1/auth/me').then(r=>r.data as MeResponse);
