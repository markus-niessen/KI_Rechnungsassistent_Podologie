import { describe, expect, it } from "vitest";

import {
  createDefaultDashboardLayout,
  dashboardLayoutStorageKey,
  loadDashboardLayout,
  normalizeDashboardLayout,
  saveDashboardLayout,
} from "./dashboardLayout";

describe("dashboard layout", () => {
  it("uses the default layout when localStorage contains invalid JSON", () => {
    window.localStorage.setItem(dashboardLayoutStorageKey, "{invalid");

    expect(loadDashboardLayout()).toEqual(createDefaultDashboardLayout());
  });

  it("ignores unknown IDs and appends newly missing widgets", () => {
    const layout = normalizeDashboardLayout({
      order: ["open-invoices", "unknown-widget"],
      visibility: { "open-invoices": false, "unknown-widget": false },
    });

    expect(layout.order.slice(0, 2)).toEqual(["open-invoices", "active-patients"]);
    expect(layout.order).not.toContain("unknown-widget");
    expect(layout.visibility).toMatchObject({ "open-invoices": false, "active-patients": true });
  });

  it("falls back to the default when no widget would remain visible", () => {
    const defaultLayout = createDefaultDashboardLayout();
    const visibility = Object.fromEntries(defaultLayout.order.map((id) => [id, false]));

    expect(normalizeDashboardLayout({ order: defaultLayout.order, visibility })).toEqual(defaultLayout);
  });

  it("saves and restores a valid layout", () => {
    const layout = createDefaultDashboardLayout();
    layout.order = ["open-invoices", ...layout.order.filter((id) => id !== "open-invoices")];
    layout.visibility["ai-review-required"] = false;

    saveDashboardLayout(layout);

    expect(loadDashboardLayout()).toEqual(layout);
  });
});
