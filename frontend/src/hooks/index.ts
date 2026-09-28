import { useAsync } from './useAsync';
import { listCompanies, listProducts, listRegulations, listAnalysisRuns, listActions, getAnalysis } from '../api';

export const useCompanies = () => useAsync(listCompanies);
export const useProducts = (companyId?: number) => useAsync(() => listProducts(companyId), [companyId]);
export const useRegulations = () => useAsync(listRegulations);
export const useAnalysisRuns = () => useAsync(listAnalysisRuns);
export const useActions = () => useAsync(listActions);
export const useAnalysis = (id: number) => useAsync(() => getAnalysis(id), [id]);
