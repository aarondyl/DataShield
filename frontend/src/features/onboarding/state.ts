export type SetupState={companyId:number;productId:number;productName:string;markets:string[];method:'website'|'repository'|'manual';analysisId?:string;analysisKind?:'website'|'repository'};
const KEY='datashield.setup.v1';
const store=()=>window.datashieldDesktop?localStorage:sessionStorage;
export const readSetup=():SetupState|null=>{try{return JSON.parse(store().getItem(KEY)||'null')}catch{return null}};
export const writeSetup=(value:SetupState)=>{const target=store();const encoded=JSON.stringify(value);target.setItem(KEY,encoded);if(window.datashieldDesktop)target.setItem(`datashield.setup.company.${value.companyId}`,encoded)};
export const clearSetup=()=>store().removeItem(KEY);
