// @vitest-environment jsdom
import { render, screen, cleanup } from '@testing-library/react';
import { afterEach, expect, it } from 'vitest';
import { FindingDetail, type FindingDetailData } from './FindingDetail';
import { zh } from './i18n';
afterEach(cleanup);
it('renders the immutable evidence chain, official source and actual Twin version', () => {
  const d: FindingDetailData = { finding: { id: 1, title: '需要补充说明', status: 'OPEN', impact_level: 'HIGH', applicability_summary: '适用', gap_summary: '缺少说明', created_at: '2026-10-08T00:00:00Z' }, agent_run: { id: 9, created_at: '', status: 'COMPLETED', model_provider: 'mock' }, product_twin_version: { id: 17, version_number: 3 }, requirements: [{ id: 5, summary: '向用户提供说明', regulation_name: '测试法规', regulation_id: 1, version_id: 2, regulation_version: 4, legal_unit_id: 6, source_url: 'https://example.org/official' }], legal_evidence: [], evidence_snapshots: [{ id: 1, requirement_id: 5, snapshot: { legal_unit_id: 6, regulation_id: 1, regulation_name: '测试法规', version_id: 2, version: 4, article: '第六条', heading: '说明义务', content: '真实保存的条文证据', source_url: 'https://example.org/official', requirement_ids: [5] } }] };
  render(<FindingDetail copy={zh} detail={d} />);
  expect(screen.getByText('真实保存的条文证据')).toBeTruthy();
  expect(screen.getByText(/v3 \(#17\)/)).toBeTruthy();
  expect(screen.getAllByRole('link')[0].getAttribute('href')).toBe('https://example.org/official');
  expect(screen.getByRole('note').textContent).toContain('模拟模型');
});
it('does not invent missing evidence', () => {
  const d = { finding: { title: '待补充', created_at: '', status: 'OPEN', impact_level: 'LOW' }, agent_run: { id: 1, model_provider: 'mock' }, requirements: [], legal_evidence: [], evidence_snapshots: [] } as unknown as FindingDetailData;
  render(<FindingDetail copy={zh} detail={d} />);
  expect(screen.getAllByText('暂无可验证证据')).toHaveLength(2);
  expect(screen.queryByRole('link')).toBeNull();
});
