import type { DashboardData } from "./dashboardData";

export type DashboardWidgetId =
  | "active-patients"
  | "open-invoices"
  | "overdue-invoices"
  | "draft-invoices"
  | "open-reminders"
  | "ai-review-required";

export type DashboardWidgetDefinition = {
  description: string;
  id: DashboardWidgetId;
  status: "info" | "warning" | "danger";
  statusLabel: string;
  title: string;
  value: (data: DashboardData) => number;
};

export const dashboardWidgets: DashboardWidgetDefinition[] = [
  {
    id: "active-patients",
    title: "Aktive Patienten",
    description: "Aktuell aktive Patienten",
    status: "info",
    statusLabel: "Aktuell",
    value: (data) => data.activePatients,
  },
  {
    id: "open-invoices",
    title: "Offene Rechnungen",
    description: "Noch nicht vollständig bezahlt",
    status: "info",
    statusLabel: "Offen",
    value: (data) => data.openInvoices,
  },
  {
    id: "overdue-invoices",
    title: "Überfällige Rechnungen",
    description: "Fälligkeit bereits überschritten",
    status: "danger",
    statusLabel: "Überfällig",
    value: (data) => data.overdueInvoices,
  },
  {
    id: "draft-invoices",
    title: "Rechnungsentwürfe",
    description: "Noch nicht finalisierte Rechnungen",
    status: "info",
    statusLabel: "Entwurf",
    value: (data) => data.draftInvoices,
  },
  {
    id: "open-reminders",
    title: "Offene Mahnungen",
    description: "Entwurf oder bereits versendet",
    status: "warning",
    statusLabel: "Offen",
    value: (data) => data.openReminders,
  },
  {
    id: "ai-review-required",
    title: "KI-Prüfung erforderlich",
    description: "Entwurf benötigt weitere Prüfung",
    status: "warning",
    statusLabel: "Prüfung",
    value: (data) => data.aiReviewRequired,
  },
];
