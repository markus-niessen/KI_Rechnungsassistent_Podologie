import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { App } from "./App";

vi.mock("./dashboard/dashboardData", () => ({
  getDashboardData: vi.fn().mockResolvedValue({
    activePatients: 0,
    openInvoices: 0,
    overdueInvoices: 0,
    draftInvoices: 0,
    openReminders: 0,
    aiReviewRequired: 0,
  }),
}));

vi.mock("./api/patients", () => ({
  getPatients: vi.fn().mockResolvedValue([]),
  activatePatient: vi.fn(),
  deactivatePatient: vi.fn(),
  getPatient: vi.fn(),
  getPatientInvoices: vi.fn(),
  createPatient: vi.fn(),
  updatePatient: vi.fn(),
}));

function renderAt(path: string) {
  window.history.pushState({}, "", path);
  return render(<App />);
}

describe("App", () => {
  it("renders the frontend workspace", () => {
    renderAt("/");

    expect(screen.getByRole("heading", { name: "Dashboard" })).toBeInTheDocument();
  });

  it("renders the dashboard at both dashboard routes", () => {
    const { unmount } = renderAt("/");
    expect(screen.getByRole("heading", { name: "Dashboard" })).toBeInTheDocument();
    unmount();

    renderAt("/dashboard");
    expect(screen.getByRole("heading", { name: "Dashboard" })).toBeInTheDocument();
  });

  it("renders each planned main area and marks the matching navigation item active", () => {
    const routes = [
      ["/patients", "Patienten"],
      ["/invoices", "Rechnungen"],
      ["/payments", "Zahlungen"],
      ["/reminders", "Mahnwesen"],
      ["/services", "Leistungen / Produkte"],
      ["/business-profiles", "Betriebe / Standorte"],
      ["/settings", "Einstellungen"],
    ];

    for (const [path, label] of routes) {
      const { unmount } = renderAt(path);
      expect(screen.getByRole("heading", { level: 1, name: label })).toBeInTheDocument();
      expect(screen.getByRole("link", { name: label })).toHaveAttribute("aria-current", "page");
      unmount();
    }
  });

  it("shows a 404 page for an unknown route", () => {
    renderAt("/unbekannt");

    expect(screen.getByRole("heading", { level: 1, name: "Seite nicht gefunden" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Heimtag" })).not.toBeInTheDocument();
  });

  it("navigates to a main area through the sidebar", () => {
    renderAt("/dashboard");

    fireEvent.click(screen.getByRole("link", { name: "Patienten" }));

    expect(screen.getByRole("heading", { level: 1, name: "Patienten" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Patienten" })).toHaveAttribute("aria-current", "page");
  });

  it("opens and closes the navigation drawer from the header", () => {
    renderAt("/dashboard");

    const menuButton = screen.getByRole("button", { name: "Navigation öffnen" });
    fireEvent.click(menuButton);

    expect(menuButton).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("button", { name: "Navigation durch Klick außerhalb schließen" })).toBeInTheDocument();

    fireEvent.click(menuButton);

    expect(menuButton).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByRole("button", { name: "Navigation durch Klick außerhalb schließen" })).not.toBeInTheDocument();
  });

  it("closes the navigation drawer with the overlay and Escape", () => {
    renderAt("/dashboard");

    const menuButton = screen.getByRole("button", { name: "Navigation öffnen" });
    fireEvent.click(menuButton);
    fireEvent.click(screen.getByRole("button", { name: "Navigation durch Klick außerhalb schließen" }));
    expect(menuButton).toHaveAttribute("aria-expanded", "false");

    fireEvent.click(menuButton);
    fireEvent.keyDown(document, { key: "Escape" });

    expect(menuButton).toHaveAttribute("aria-expanded", "false");
  });
});
