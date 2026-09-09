import { BrowserRouter, Outlet, Route, Routes, useLocation } from "react-router-dom";

import { AppShell } from "./layouts/AppShell";
import { DashboardPage } from "./pages/DashboardPage";
import { NotFoundPage } from "./pages/NotFoundPage";
import { PatientDetailPage } from "./pages/PatientDetailPage";
import { PatientFormPage } from "./pages/PatientFormPage";
import { PatientsPage } from "./pages/PatientsPage";
import { PlaceholderPage } from "./pages/PlaceholderPage";

const pageTitles: Record<string, string> = {
  "/": "Dashboard",
  "/dashboard": "Dashboard",
  "/patients": "Patienten",
  "/invoices": "Rechnungen",
  "/payments": "Zahlungen",
  "/reminders": "Mahnwesen",
  "/services": "Leistungen / Produkte",
  "/business-profiles": "Betriebe / Standorte",
  "/settings": "Einstellungen",
};

function RoutedAppShell() {
  const { pathname } = useLocation();
  const pageTitle = pathname.startsWith("/patients/") ? "Patienten" : pageTitles[pathname] ?? "Seite nicht gefunden";

  return (
    <AppShell pageTitle={pageTitle}>
      <Outlet />
    </AppShell>
  );
}

export function AppRouter() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<RoutedAppShell />}>
          <Route index element={<DashboardPage />} />
          <Route path="dashboard" element={<DashboardPage />} />
          <Route path="patients">
            <Route index element={<PatientsPage />} />
            <Route path="new" element={<PatientFormPage mode="create" />} />
            <Route path=":patientId" element={<PatientDetailPage />} />
            <Route path=":patientId/edit" element={<PatientFormPage mode="edit" />} />
          </Route>
          <Route path="invoices" element={<PlaceholderPage title="Rechnungen" />} />
          <Route path="payments" element={<PlaceholderPage title="Zahlungen" />} />
          <Route path="reminders" element={<PlaceholderPage title="Mahnwesen" />} />
          <Route path="services" element={<PlaceholderPage title="Leistungen / Produkte" />} />
          <Route path="business-profiles" element={<PlaceholderPage title="Betriebe / Standorte" />} />
          <Route path="settings" element={<PlaceholderPage title="Einstellungen" />} />
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
