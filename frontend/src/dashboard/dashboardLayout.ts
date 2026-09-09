import { dashboardWidgets, type DashboardWidgetId } from "./dashboardWidgets";

export const dashboardLayoutStorageKey = "ki-rechnungsassistent.dashboard-layout";

export type DashboardLayout = {
  order: DashboardWidgetId[];
  visibility: Record<DashboardWidgetId, boolean>;
};

const widgetIds = dashboardWidgets.map((widget) => widget.id);

export function createDefaultDashboardLayout(): DashboardLayout {
  return {
    order: [...widgetIds],
    visibility: Object.fromEntries(widgetIds.map((id) => [id, true])) as Record<DashboardWidgetId, boolean>,
  };
}

export function normalizeDashboardLayout(value: unknown): DashboardLayout {
  if (typeof value !== "object" || value === null || !Array.isArray((value as { order?: unknown }).order)) {
    return createDefaultDashboardLayout();
  }

  const storedLayout = value as { order: unknown[]; visibility?: unknown };
  const storedIds = storedLayout.order.filter(
    (id): id is DashboardWidgetId => typeof id === "string" && widgetIds.includes(id as DashboardWidgetId),
  );
  const order = [...new Set(storedIds), ...widgetIds.filter((id) => !storedIds.includes(id))];
  const storedVisibility = typeof storedLayout.visibility === "object" && storedLayout.visibility !== null
    ? storedLayout.visibility as Record<string, unknown>
    : {};
  const visibility = Object.fromEntries(
    widgetIds.map((id) => [id, typeof storedVisibility[id] === "boolean" ? storedVisibility[id] : true]),
  ) as Record<DashboardWidgetId, boolean>;

  return Object.values(visibility).some(Boolean) ? { order, visibility } : createDefaultDashboardLayout();
}

export function loadDashboardLayout(): DashboardLayout {
  try {
    const storedLayout = window.localStorage.getItem(dashboardLayoutStorageKey);
    return storedLayout === null ? createDefaultDashboardLayout() : normalizeDashboardLayout(JSON.parse(storedLayout));
  } catch {
    return createDefaultDashboardLayout();
  }
}

export function saveDashboardLayout(layout: DashboardLayout): void {
  try {
    window.localStorage.setItem(dashboardLayoutStorageKey, JSON.stringify(layout));
  } catch {
    // Local dashboard preferences are optional when browser storage is unavailable.
  }
}

export function resetDashboardLayout(): DashboardLayout {
  try {
    window.localStorage.removeItem(dashboardLayoutStorageKey);
  } catch {
    // Local dashboard preferences are optional when browser storage is unavailable.
  }

  return createDefaultDashboardLayout();
}
