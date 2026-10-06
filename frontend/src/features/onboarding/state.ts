export type SetupState={companyId:number;productId:number;productName:string;markets:string[];method:'website'|'repository'|'manual';analysisId?:string;analysisKind?:'website'|'repository'};
const KEY='datashield.setup.v1';
export const readSetup=():SetupState|null=>{try{return JSON.parse(sessionStorage.getItem(KEY)||'null')}catch{return null}};
export const writeSetup=(value:SetupState)=>sessionStorage.setItem(KEY,JSON.stringify(value));
