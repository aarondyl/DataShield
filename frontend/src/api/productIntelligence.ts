import client from './client';
export type AnalysisJob={analysis_id:string;product_id:number;kind:'website'|'repository';status:'PENDING'|'RUNNING'|'COMPLETED'|'FAILED';error?:string};
export const analyzeWebsite=(data:{company_id:number;product_id:number;url:string;product_description?:string})=>client.post<AnalysisJob>('/v1/ui/understanding/website',data).then(r=>r.data);
export const analyzeRepository=(data:{company_id:number;product_id:number;repository_path:string;analysis_mode:string;product_description?:string})=>client.post<AnalysisJob>('/v1/ui/understanding/repository',data).then(r=>r.data);
export const getUnderstandingJob=(kind:string,id:string,companyId:number,productId:number)=>client.get<AnalysisJob>(`/v1/ui/understanding/analysis/${kind}/${id}`,{params:{company_id:companyId,product_id:productId}}).then(r=>r.data);
export const attachUnderstanding=(companyId:number,productId:number,analysisId:string,kind:string)=>client.post(`/v1/ui/understanding/products/${productId}/twin/analyses`,{company_id:companyId,analysis_id:analysisId,kind}).then(r=>r.data);
export const getTwin=(companyId:number,productId:number)=>client.get(`/v1/ui/understanding/products/${productId}/twin`,{params:{company_id:companyId}}).then(r=>r.data);
export const getTwinVersions=(companyId:number,productId:number)=>client.get<any[]>(`/v1/ui/understanding/products/${productId}/twin/versions`,{params:{company_id:companyId}}).then(r=>r.data);
export const addTwinFact=(companyId:number,productId:number,group:string,name:string,note:string)=>client.post(`/v1/ui/understanding/products/${productId}/twin/facts`,{company_id:companyId,group,fact:{name,status:'PRESENT',confidence:.7},note}).then(r=>r.data);
