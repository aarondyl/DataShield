export interface Company {
  id: number;
  name: string;
  industry: string;
  country: string;
  target_markets: string[];
  business_model: string;
  created_at: string;
}

export interface CompanyPayload {
  name: string;
  industry: string;
  country: string;
  target_markets: string[];
  business_model: string;
}

export interface Product {
  id: number;
  company_id: number;
  name: string;
  category: string;
  target_markets: string[];
  collects_personal_data: boolean;
  collects_sensitive_data: boolean;
  collects_health_data: boolean;
  collects_location_data: boolean;
  children_related: boolean;
  third_party_data_sharing: boolean;
  uses_third_party_sdk: boolean;
  third_party_sdks: string[];
  has_privacy_policy: boolean;
  privacy_policy_text: string;
  cross_border_data_transfer: boolean;
  description: string;
  created_at: string;
}

export type ProductPayload = Omit<Product, 'id' | 'created_at'>;

export interface Regulation {
  id: number;
  name: string;
  jurisdiction: string;
  description: string;
  source_url: string;
  article_count: number;
  published_at: string | null;
  effective_at: string | null;
}

export interface RegulationArticle {
  id: number;
  article_number: string;
  title: string;
  content: string;
  topic: string;
}

export interface RegulationDetail extends Regulation {
  articles: RegulationArticle[];
}

export interface RegulationUploadResult {
  id: number;
  name: string;
  articles_ingested: number;
}

export type RiskLevel = 'low' | 'medium' | 'high';
export type Confidence = 'high' | 'medium' | 'low';
export type AnalysisStatus = 'completed' | 'degraded' | 'failed';

export interface Evidence {
  regulation: string;
  article: string;
  content: string;
  source_url: string;
  reason: string;
  verified: boolean;
}

export interface RecommendedAction {
  title: string;
  priority: RiskLevel;
  department: string;
  description: string;
  evidence: { regulation: string; article: string };
}

export interface AnalysisResult {
  id: number;
  status: AnalysisStatus;
  relevant: boolean | null;
  risk_level: RiskLevel | null;
  affected_products: string[];
  affected_areas: string[];
  summary: string;
  reasoning_summary: string;
  confidence: Confidence | null;
  evidence: Evidence[];
  actions: RecommendedAction[];
  llm_mode: string;
  created_at: string;
}

export interface AnalysisRunListItem {
  id: number;
  company_name: string;
  product_name: string;
  relevant: boolean | null;
  risk_level: RiskLevel | null;
  status: AnalysisStatus;
  created_at: string;
}

export interface ActionItem {
  id: number;
  run_id: number;
  title: string;
  priority: RiskLevel;
  department: string;
  description: string;
  created_at: string;
}

export interface AnalysisRequest {
  company_id: number;
  product_id: number;
  regulation_id?: number | null;
  query: string;
}

export interface HealthStatus {
  status: string;
  db: string;
  llm_provider: string;
  embedding_provider: string;
}

export interface QuestionShowIf {
  key: string;
  equals: boolean | string;
}

export interface ComplianceQuestion {
  key: string;
  module: string;
  type: 'yesno' | 'select' | 'multiselect';
  text: string;
  options: string[];
  default: boolean | string | string[] | null;
  show_if: QuestionShowIf | null;
}

export interface Questionnaire {
  modules: string[];
  questions: ComplianceQuestion[];
  presets: Record<string, Record<string, unknown>>;
}

export interface RiskHit {
  rule_id: string;
  dimension: string;
  condition: string;
  level: '高' | '中' | '低';
  articles: string[];
  risk: string;
  advice: string;
}

export interface Assessment {
  id: number;
  product_id: number;
  answers: Record<string, unknown>;
  hits: RiskHit[];
  dimension_scores: Record<string, number>;
  score: number;
  rating: string;
  counts: Record<string, number>;
  roadmap: Record<string, RiskHit[]>;
  related_cases: { name: string; time: string; authority: string; fine: string; reason: string; dimensions: string[]; lesson: string }[];
  report_markdown: string;
  created_at: string;
}

export interface PolicyCheckResult {
  total: number;
  covered: number;
  coverage: number;
  items: { name: string; hint: string; covered: boolean; matched: string[] }[];
  mismatches: { key:string; title:string; product_behavior:string; policy:string; advice:string }[];
}

export type IssueStatus = 'pending' | 'in_progress' | 'resolved';
export interface DeveloperIssue { id:number; product_id:number; source:string; source_key:string; title:string; risk_level:RiskLevel; why:string; fix:string; recommended_text:string; placement:string; status:IssueStatus; created_at:string; }
export interface ScanFinding { key:string; name:string; kind:'sdk'|'permission'; risk_level:RiskLevel; data:string; why:string; fix:string; policy_disclosed:boolean; }
export interface SdkScanResult { id:number; product_id:number; filename:string; findings:ScanFinding[]; created_at:string; }
