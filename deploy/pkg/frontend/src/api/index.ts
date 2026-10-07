import client from './client';
import type {
  ActionItem,
  AnalysisRequest,
  AnalysisResult,
  AnalysisRunListItem,
  Company,
  CompanyPayload,
  HealthStatus,
  Product,
  ProductPayload,
  Regulation,
  RegulationDetail,
  RegulationUploadResult,
  Assessment,
  PolicyCheckResult,
  Questionnaire,
  DeveloperIssue,
  IssueStatus,
  SdkScanResult,
} from '../types';

export const getHealth = () => client.get<HealthStatus>('/health').then((r) => r.data);

// Companies
export const listCompanies = () => client.get<Company[]>('/companies').then((r) => r.data);
export const getCompany = (id: number) => client.get<Company>(`/companies/${id}`).then((r) => r.data);
export const createCompany = (data: CompanyPayload) =>
  client.post<Company>('/companies', data).then((r) => r.data);
export const updateCompany = (id: number, data: CompanyPayload) =>
  client.put<Company>(`/companies/${id}`, data).then((r) => r.data);

// Products
export const listProducts = (companyId?: number) =>
  client
    .get<Product[]>('/products', { params: companyId ? { company_id: companyId } : undefined })
    .then((r) => r.data);
export const getProduct = (id: number) => client.get<Product>(`/products/${id}`).then((r) => r.data);
export const createProduct = (data: ProductPayload) =>
  client.post<Product>('/products', data).then((r) => r.data);
export const updateProduct = (id: number, data: ProductPayload) =>
  client.put<Product>(`/products/${id}`, data).then((r) => r.data);

// Regulations
export const listRegulations = () => client.get<Regulation[]>('/regulations').then((r) => r.data);
export const getRegulation = (id: number) =>
  client.get<RegulationDetail>(`/regulations/${id}`).then((r) => r.data);
export const uploadRegulation = (form: FormData) =>
  client
    .post<RegulationUploadResult>('/regulations/upload', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    .then((r) => r.data);

// Analysis
export const runAnalysis = (data: AnalysisRequest) =>
  client.post<AnalysisResult>('/analysis', data).then((r) => r.data);
export const listAnalysisRuns = () =>
  client.get<AnalysisRunListItem[]>('/analysis').then((r) => r.data);
export const getAnalysis = (id: number) =>
  client.get<AnalysisResult>(`/analysis/${id}`).then((r) => r.data);

// Actions
export const listActions = () => client.get<ActionItem[]>('/actions').then((r) => r.data);
export const listDeveloperIssues = (productId?: number) => client.get<DeveloperIssue[]>('/developer/issues', {params:productId?{product_id:productId}:undefined}).then((r)=>r.data);
export const updateDeveloperIssue = (id:number,status:IssueStatus) => client.patch<DeveloperIssue>(`/developer/issues/${id}`,{status}).then((r)=>r.data);
export const scanSdkPermissions = (data:{product_id:number;content:string;filename:string}) => client.post<SdkScanResult>('/developer/sdk-scan',data).then((r)=>r.data);

// Deterministic compliance assessment and privacy tools
export const getQuestionnaire = () =>
  client.get<Questionnaire>('/compliance/questionnaire').then((r) => r.data);
export const runAssessment = (productId: number, answers: Record<string, unknown>) =>
  client.post<Assessment>('/compliance/assessments', { product_id: productId, answers }).then((r) => r.data);
export const listAssessments = (productId?: number) =>
  client.get<Assessment[]>('/compliance/assessments', { params: productId ? { product_id: productId } : undefined }).then((r) => r.data);
export const generatePolicy = (data: {
  answers: Record<string, unknown>;
  product_name: string;
  company_name: string;
  contact: string;
}) => client.post<{ text: string }>('/compliance/policy/generate', data).then((r) => r.data);
export const checkPolicy = (text: string, productId?:number) =>
  client.post<PolicyCheckResult>('/compliance/policy/check', { text, product_id:productId }).then((r) => r.data);
export const analyzeDocument = (text: string) =>
  client.post<{ suggestions: Record<string, unknown>; note: string }>('/compliance/documents/analyze', { text }).then((r) => r.data);
export const uploadComplianceDocument = (file: File) => {
  const form = new FormData();
  form.append('file', file);
  return client.post<{ suggestions: Record<string, unknown>; note: string }>('/compliance/documents/upload', form).then((r) => r.data);
};
