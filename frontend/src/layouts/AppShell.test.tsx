import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { App } from "../App";

vi.mock("../dashboard/dashboardData", () => ({
  getDashboardData: vi.fn().mockResolvedValue({
    activePatients: 0,
    openInvoices: 0,
    overdueInvoices: 0,
    draftInvoices: 0,
    openReminders: 0,
    aiReviewRequired: 0,
  }),
}));

describe("AppShell", () => {
  it("renders the app structure with the planned main navigation", () => {
    window.history.pushState({}, "", "/dashboard");
    render(<App />);

    expect(screen.getByRole("navigation", { name: "Hauptnavigation" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Dashboard" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: "Patienten" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Heimtag" })).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 1, name: "Dashboard" })).toBeInTheDocument();
    expect(screen.getByLabelText("Darstellung")).toBeInTheDocument();
  });
});
