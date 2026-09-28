import { BrowserRouter, Route, Routes } from 'react-router-dom';
import Layout from './components/Layout';
import DashboardPage from './pages/DashboardPage';
import CompanyPage from './pages/CompanyPage';
import ProductsPage from './pages/ProductsPage';
import RegulationsPage from './pages/RegulationsPage';
import AnalyzePage from './pages/AnalyzePage';
import ImpactReportPage from './pages/ImpactReportPage';

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/company" element={<CompanyPage />} />
          <Route path="/products" element={<ProductsPage />} />
          <Route path="/regulations" element={<RegulationsPage />} />
          <Route path="/analyze" element={<AnalyzePage />} />
          <Route path="/report/:id" element={<ImpactReportPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
