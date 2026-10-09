export type Edition='developer'|'enterprise';
export type LocalSession={name:string;email:string;edition:Edition;companyName?:string;companyId:number};
const KEY='datashield.local-session.v1';
const store=()=>window.datashieldDesktop?localStorage:sessionStorage;
export const readSession=():LocalSession|null=>{try{return JSON.parse(store().getItem(KEY)||'null')}catch{return null}};
export const writeSession=(value:LocalSession)=>store().setItem(KEY,JSON.stringify(value));
export const clearSession=()=>store().removeItem(KEY);
export const readEdition=():Edition=>(store().getItem('datashield.edition') as Edition)||'developer';
export const writeEdition=(value:Edition)=>store().setItem('datashield.edition',value);
