export type Edition='developer'|'enterprise';
export type LocalSession={name:string;email:string;edition:Edition;companyName?:string};
const KEY='datashield.local-session.v1';
export const readSession=():LocalSession|null=>{try{return JSON.parse(sessionStorage.getItem(KEY)||'null')}catch{return null}};
export const writeSession=(value:LocalSession)=>sessionStorage.setItem(KEY,JSON.stringify(value));
export const clearSession=()=>sessionStorage.removeItem(KEY);
export const readEdition=():Edition=>(sessionStorage.getItem('datashield.edition') as Edition)||'developer';
export const writeEdition=(value:Edition)=>sessionStorage.setItem('datashield.edition',value);
