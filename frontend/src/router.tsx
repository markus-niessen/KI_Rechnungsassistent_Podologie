import { BrowserRouter, Outlet, Route, Routes, useLocation } from "react-router-dom";

import { AppShell } from "./layouts/AppShell";
import { DashboardPage } from "./pages/DashboardPage";
import { NotFoundPage } from "./pages/NotFoundPage";
import { PatientDetailPage } from "./pages/PatientDetailPage";
import { PatientFormPage } from "./pages/PatientFormPage";
import { PatientsPage } from "./pages/PatientsPage";
import { PlaceholderPage } from "./pages/PlaceholderPage";
import { BusinessProfileDetailPage } from "./pages/BusinessProfileDetailPage";
import { BusinessProfileFormPage } from "./pages/BusinessProfileFormPage";
import { BusinessProfilesPage } from "./pages/BusinessProfilesPage";
import { ServiceDetailPage } from "./pages/ServiceDetailPage";
import { ServiceFormPage } from "./pages/ServiceFormPage";
import { ServicesPage } from "./pages/ServicesPage";

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
  const pageTitle = pathname.startsWith("/patients/") ? "Patienten" : pathname.startsWith("/services/") ? "Leistungen / Produkte" : pathname.startsWith("/business-profiles/") ? "Betriebe / Standorte" : pageTitles[pathname] ?? "Seite nicht gefunden";

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
          <Route path="services">
            <Route index element={<ServicesPage />} />
            <Route path="new" element={<ServiceFormPage mode="create" />} />
            <Route path=":serviceId" element={<ServiceDetailPage />} />
            <Route path=":serviceId/edit" element={<ServiceFormPage mode="edit" />} />
          </Route>
          <Route path="business-profiles">
            <Route index element={<BusinessProfilesPage />} />
            <Route path="new" element={<BusinessProfileFormPage mode="create" />} />
            <Route path=":profileId" element={<BusinessProfileDetailPage />} />
            <Route path=":profileId/edit" element={<BusinessProfileFormPage mode="edit" />} />
          </Route>
          <Route path="settings" element={<PlaceholderPage title="Einstellungen" />} />
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
