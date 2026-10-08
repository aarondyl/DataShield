// @vitest-environment jsdom
import React from 'react';
import { afterEach, expect, test, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { RemediationPage } from './RemediationPage';
import { zh, en } from './i18n';
import { localApiRequest } from './local-api';
vi.mock('./local-api', () => ({ localApiRequest: vi.fn() }));
afterEach(() => { cleanup(); vi.resetAllMocks(); });

for (const copy of [zh, en]) test(`${copy.actions.title}: create document, review evidence, approve, return to Finding`, async () => {
  const calls: { path: string; body?: unknown }[] = [];
  let status = 'PROPOSED';
  let created = false;
  const detail = () => ({ remediation: { id: 8, finding_id: 3, title: 'Disclosure', summary: 'Review disclosure', status, remediation_type: 'DOCUMENT_CHANGE', model_provider: 'mock', plan: { draft_text: 'Actual draft', acceptance_criteria: ['Review'] } }, requirements: [{ id: 9, summary: 'Transparency requirement' }], legal_evidence: [{ legal_unit_id: 7, regulation_name: 'Regulation', article: '50', content: 'Legal text', source_url: 'https://example.org/legal' }], product_twin_version: { id: 12, version_number: 2 } });
  vi.mocked(localApiRequest).mockImplementation(async (path, method, body) => {
    calls.push({ path, body });
    if (path.includes('/approve')) { status = 'APPROVED'; return detail() as never; }
    if (path.includes('/remediations') && method === 'POST') { created = true; return detail() as never; }
    if (path.startsWith('/api/v1/remediations/')) return detail() as never;
    if (path.includes('/remediations?')) return (created ? [detail().remediation] : []) as never;
    return [{ id: 3, title: 'Finding', status: 'OPEN' }] as never;
  });
  const back = vi.fn();
  render(<RemediationPage copy={copy} workspace={{ companyId: 2, productId: 4 }} initialFinding={3} onFinding={back} />);
  await screen.findByRole('option', { name: 'Finding' });
  fireEvent.change(screen.getByLabelText(copy.actions.documentType), { target: { value: 'Privacy notice' } });
  await waitFor(() => expect(screen.getByRole('button', { name: copy.actions.create }).hasAttribute('disabled')).toBe(false));
  fireEvent.click(screen.getByRole('button', { name: copy.actions.create }));
  await screen.findByText('Actual draft');
  expect(screen.getByText('Legal text')).toBeTruthy();
  expect(screen.getByRole('link', { name: copy.actions.source }).getAttribute('href')).toBe('https://example.org/legal');
  expect(calls.find(x => x.path.endsWith('/3/remediations'))?.body).toEqual({ tenant_id: 2, remediation_type: 'DOCUMENT_CHANGE', document_type: 'Privacy notice' });
  await waitFor(() => expect(screen.getByRole('button', { name: copy.actions.approve }).hasAttribute('disabled')).toBe(false));
  fireEvent.click(screen.getByRole('button', { name: copy.actions.approve }));
  await waitFor(() => expect(screen.queryByRole('button', { name: copy.actions.approve })).toBeNull());
  expect(screen.getAllByText(copy.actions.states.APPROVED, { exact: false }).length).toBeGreaterThan(0);
  fireEvent.click(screen.getByRole('button', { name: copy.actions.back }));
  expect(back).toHaveBeenCalledWith(3);
});

test('code proposal rejects without executing or hiding failure', async () => {
  let fail = true;
  const detail = { remediation: { id: 8, finding_id: 3, title: 'Code plan', summary: 'Summary', status: 'PROPOSED', remediation_type: 'CODE_CHANGE', plan: { coding_prompt: 'Instructions only' } }, requirements: [], legal_evidence: [] };
  vi.mocked(localApiRequest).mockImplementation(async (path, method, body) => {
    if (path.endsWith('/reject')) return { ...detail, remediation: { ...detail.remediation, status: 'REJECTED' } } as never;
    if (method === 'POST') { expect(body).toEqual({ tenant_id: 2, remediation_type: 'CODE_CHANGE' }); if (fail) { fail = false; throw new Error('provider unavailable'); } return detail as never; }
    if (path.includes('/remediations?')) return [] as never;
    return [{ id: 3, title: 'Finding', status: 'OPEN' }] as never;
  });
  render(<RemediationPage copy={zh} workspace={{ companyId: 2, productId: 4 }} initialFinding={3} onFinding={vi.fn()} />);
  await screen.findByRole('option', { name: 'Finding' });
  fireEvent.change(screen.getByLabelText(zh.actions.type), { target: { value: 'CODE_CHANGE' } });
  await waitFor(() => expect(screen.getByRole('button', { name: zh.actions.create }).hasAttribute('disabled')).toBe(false));
  fireEvent.click(screen.getByRole('button', { name: zh.actions.create }));
  await screen.findByRole('alert');
  fireEvent.click(screen.getByRole('button', { name: zh.actions.create }));
  await screen.findByText('Instructions only');
  await waitFor(() => expect(screen.getByRole('button', { name: zh.actions.reject }).hasAttribute('disabled')).toBe(false));
  fireEvent.click(screen.getByRole('button', { name: zh.actions.reject }));
  await screen.findByText(zh.actions.states.REJECTED, { exact: false });
  expect(screen.queryByRole('button', { name: zh.actions.approve })).toBeNull();
});
