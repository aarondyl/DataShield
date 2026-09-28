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
