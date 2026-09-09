import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

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

  it("shows an error state and retries loading", async () => {
    mockedGetDashboardData.mockRejectedValueOnce(new Error("Network error")).mockResolvedValueOnce(dashboardData);

    render(<DashboardPage />);

    await waitFor(() => expect(screen.getByText("Dashboard-Daten konnten nicht geladen werden.")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Wiederholen" }));

    await waitFor(() => expect(screen.getByRole("article", { name: "Aktive Patienten" })).toHaveTextContent("124"));
    expect(mockedGetDashboardData).toHaveBeenCalledTimes(2);
  });
});
