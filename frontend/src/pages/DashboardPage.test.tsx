import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { dashboardLayoutStorageKey } from "../dashboard/dashboardLayout";
import { getDashboardData } from "../dashboard/dashboardData";
import { DashboardPage } from "./DashboardPage";

vi.mock("../dashboard/dashboardData", () => ({ getDashboardData: vi.fn() }));

const mockedGetDashboardData = vi.mocked(getDashboardData);

const dashboardData = {
  activePatients: 124,
  openInvoices: 7,
  overdueInvoices: 2,
  draftInvoices: 4,
  openReminders: 3,
  aiReviewRequired: 1,
};

afterEach(() => {
  vi.clearAllMocks();
});

describe("DashboardPage", () => {
  it("shows a loading state without dashboard values", () => {
    mockedGetDashboardData.mockReturnValue(new Promise(() => undefined));

    render(<DashboardPage />);

    expect(screen.getByRole("status")).toHaveTextContent("Dashboard-Daten werden geladen");
    expect(screen.queryByText("124")).not.toBeInTheDocument();
  });

  it("renders all dashboard metrics after loading", async () => {
    mockedGetDashboardData.mockResolvedValue(dashboardData);

    render(<DashboardPage />);

    await waitFor(() => expect(screen.getByRole("article", { name: "Aktive Patienten" })).toHaveTextContent("124"));
    expect(screen.getByRole("article", { name: "Offene Rechnungen" })).toHaveTextContent("7");
    expect(screen.getByRole("article", { name: "Überfällige Rechnungen" })).toHaveTextContent("2");
    expect(screen.getByRole("article", { name: "Rechnungsentwürfe" })).toHaveTextContent("4");
    expect(screen.getByRole("article", { name: "Offene Mahnungen" })).toHaveTextContent("3");
    expect(screen.getByRole("article", { name: "KI-Prüfung erforderlich" })).toHaveTextContent("1");
  });

  it("hides a widget, persists the choice, and allows restoring it", async () => {
    mockedGetDashboardData.mockResolvedValue(dashboardData);
    const { unmount } = render(<DashboardPage />);

    await waitFor(() => expect(screen.getByRole("article", { name: "Aktive Patienten" })).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Dashboard anpassen" }));
    fireEvent.click(screen.getByRole("checkbox", { name: "KI-Prüfung erforderlich" }));

    expect(screen.queryByRole("article", { name: "KI-Prüfung erforderlich" })).not.toBeInTheDocument();
    expect(window.localStorage.getItem(dashboardLayoutStorageKey)).toContain("ai-review-required");
    unmount();

    render(<DashboardPage />);
    await waitFor(() => expect(screen.getByRole("article", { name: "Aktive Patienten" })).toBeInTheDocument());
    expect(screen.queryByRole("article", { name: "KI-Prüfung erforderlich" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Dashboard anpassen" }));
    fireEvent.click(screen.getByRole("checkbox", { name: "KI-Prüfung erforderlich" }));
    expect(screen.getByRole("article", { name: "KI-Prüfung erforderlich" })).toBeInTheDocument();
  });

  it("updates and persists the widget order", async () => {
    mockedGetDashboardData.mockResolvedValue(dashboardData);
    render(<DashboardPage />);

    await waitFor(() => expect(screen.getByRole("article", { name: "Aktive Patienten" })).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Dashboard anpassen" }));
    fireEvent.click(screen.getByRole("button", { name: "Überfällige Rechnungen nach oben" }));

    expect(screen.getAllByRole("article").slice(0, 3).map((widget) => within(widget).getByRole("heading").textContent)).toEqual([
      "Aktive Patienten",
      "Überfällige Rechnungen",
      "Offene Rechnungen",
    ]);
    expect(window.localStorage.getItem(dashboardLayoutStorageKey)).toContain('"overdue-invoices","open-invoices"');
  });

  it("restores the standard layout", async () => {
    window.localStorage.setItem(
      dashboardLayoutStorageKey,
      JSON.stringify({
        order: ["open-invoices", "active-patients"],
        visibility: { "open-invoices": true, "active-patients": false },
      }),
    );
    mockedGetDashboardData.mockResolvedValue(dashboardData);
    render(<DashboardPage />);

    await waitFor(() => expect(screen.getByRole("article", { name: "Offene Rechnungen" })).toBeInTheDocument());
    expect(screen.queryByRole("article", { name: "Aktive Patienten" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Dashboard anpassen" }));
    fireEvent.click(screen.getByRole("button", { name: "Standard wiederherstellen" }));

    expect(screen.getByRole("article", { name: "Aktive Patienten" })).toBeInTheDocument();
    expect(window.localStorage.getItem(dashboardLayoutStorageKey)).toContain("active-patients");
  });

  it("keeps at least one widget visible", async () => {
    mockedGetDashboardData.mockResolvedValue(dashboardData);
    render(<DashboardPage />);

    await waitFor(() => expect(screen.getByRole("article", { name: "Aktive Patienten" })).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Dashboard anpassen" }));

    for (const label of [
      "Offene Rechnungen",
      "Überfällige Rechnungen",
      "Rechnungsentwürfe",
      "Offene Mahnungen",
      "KI-Prüfung erforderlich",
    ]) {
      fireEvent.click(screen.getByRole("checkbox", { name: label }));
    }

    expect(screen.getByRole("checkbox", { name: "Aktive Patienten" })).toBeDisabled();
    expect(screen.getAllByRole("article")).toHaveLength(1);
  });

  it("shows an error state and retries loading", async () => {
    mockedGetDashboardData.mockRejectedValueOnce(new Error("Network error")).mockResolvedValueOnce(dashboardData);

    render(<DashboardPage />);

    await waitFor(() => expect(screen.getByText("Dashboard-Daten konnten nicht geladen werden.")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Wiederholen" }));

    await waitFor(() => expect(screen.getByRole("article", { name: "Aktive Patienten" })).toHaveTextContent("124"));
    expect(mockedGetDashboardData).toHaveBeenCalledTimes(2);
  });
});
