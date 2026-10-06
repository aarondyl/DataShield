import client from './client'; import {readSetup} from '../features/onboarding/state';
export type AttentionItem={id:string;type:string;title:string;summary:string;severity?:string;status:string;product_id:number;created_at?:string;target_route:string;target:Record<string,unknown>}; export type TodayData={needs_review:AttentionItem[];waiting_for_you:AttentionItem[];recently_completed:AttentionItem[]};
export const workspaceScope=()=>{const s=readSetup();return s?{tenant_id:s.companyId,product_id:s.productId}:null};
export const getToday=()=>{const scope=workspaceScope();if(!scope)return Promise.resolve<TodayData>({needs_review:[],waiting_for_you:[],recently_completed:[]});return client.get<TodayData>('/v1/today',{params:scope}).then(r=>r.data)};
