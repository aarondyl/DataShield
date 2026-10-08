export type Scope = { companyId: number; productId: number };
export type Finding = { id: number; title: string; status: string };
export type Remediation = { id: number; finding_id: number; title: string; summary: string; status: 'PROPOSED' | 'APPROVED' | 'REJECTED'; remediation_type: 'CODE_CHANGE' | 'DOCUMENT_CHANGE'; model_provider?: string; plan?: { draft_text?: string; coding_prompt?: string; acceptance_criteria?: string[]; requested_changes?: { target: string; change: string; rationale: string }[]; proposed_changes?: { section: string; change: string; rationale: string }[] } };
export type Detail = { remediation: Remediation; requirements: { id: number; summary: string }[]; legal_evidence: { legal_unit_id: number; regulation_name: string; article: string; content: string; source_url: string }[]; product_twin_version?: { id: number; version_number: number } | null };
export type Request = <T>(path: string, method?: string, body?: unknown) => Promise<T>;

// All operations use the injected Rust bridge; credentials never enter this adapter.
export function remediationApi(request: Request, scope: Scope) {
  return {
    findings: () => request<Finding[]>(`/api/v1/findings?tenant_id=${scope.companyId}&product_id=${scope.productId}`),
    list: (findingId: number) => request<Remediation[]>(`/api/v1/findings/${findingId}/remediations?tenant_id=${scope.companyId}`),
    detail: (id: number) => request<Detail>(`/api/v1/remediations/${id}?tenant_id=${scope.companyId}`),
    create: (findingId: number, type: Remediation['remediation_type'], documentType: string) => request<Detail>(`/api/v1/findings/${findingId}/remediations`, 'POST', { tenant_id: scope.companyId, remediation_type: type, ...(type === 'DOCUMENT_CHANGE' ? { document_type: documentType } : {}) }),
    decide: (id: number, decision: 'approve' | 'reject', note: string) => request<Detail>(`/api/v1/remediations/${id}/${decision}`, 'POST', { tenant_id: scope.companyId, note }),
  };
}
