import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { DataProvider } from './hooks/useData';
import { AppLayout } from './layouts/AppLayout';
import { DashboardPage } from './pages/DashboardPage';
import { ArchitecturePage } from './pages/ArchitecturePage';
import { AssetsPage } from './pages/AssetsPage';
import { EquipmentDetailPage } from './pages/EquipmentDetailPage';
import { CheckInOutPage } from './pages/CheckInOutPage';
import { DataEntryPage } from './pages/DataEntryPage';
import { AnalyticsPage } from './pages/AnalyticsPage';
import { ForecastPage } from './pages/ForecastPage';
import { AnomaliesPage } from './pages/AnomaliesPage';
import { NotificationsPage } from './pages/NotificationsPage';
import { RentalsPage } from './pages/RentalsPage';
import { ReportsPage } from './pages/ReportsPage';
import { SettingsPage } from './pages/SettingsPage';

export default function App() {
  return (
    <DataProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<AppLayout />}>
            <Route index element={<DashboardPage />} />
            <Route path="architecture" element={<ArchitecturePage />} />
            <Route path="assets" element={<AssetsPage />} />
            <Route path="assets/:id" element={<EquipmentDetailPage />} />
            <Route path="check-in-out" element={<CheckInOutPage />} />
            <Route path="add-data" element={<DataEntryPage />} />
            <Route path="analytics" element={<AnalyticsPage />} />
            <Route path="forecast" element={<ForecastPage />} />
            <Route path="anomalies" element={<AnomaliesPage />} />
            <Route path="notifications" element={<NotificationsPage />} />
            <Route path="rentals" element={<RentalsPage />} />
            <Route path="reports" element={<ReportsPage />} />
            <Route path="settings" element={<SettingsPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </DataProvider>
  );
}
