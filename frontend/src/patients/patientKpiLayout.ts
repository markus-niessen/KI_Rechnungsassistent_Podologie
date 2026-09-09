export const patientKpiLayoutStorageKey = "ki-rechnungsassistent.patient-detail-kpi-layout";

export type PatientKpiId = "not-due" | "open" | "overdue" | "paid-total";

export type PatientKpiLayout = {
  order: PatientKpiId[];
  visibility: Record<PatientKpiId, boolean>;
};

export const patientKpis: Array<{ id: PatientKpiId; label: string }> = [
  { id: "not-due", label: "Noch nicht fällig" },
  { id: "open", label: "Offen" },
  { id: "overdue", label: "Überfällig" },
  { id: "paid-total", label: "Bezahlt gesamt" },
];

const patientKpiIds = patientKpis.map((widget) => widget.id);

export function createDefaultPatientKpiLayout(): PatientKpiLayout {
  return {
    order: [...patientKpiIds],
    visibility: Object.fromEntries(patientKpiIds.map((id) => [id, true])) as Record<PatientKpiId, boolean>,
  };
}

export function normalizePatientKpiLayout(value: unknown): PatientKpiLayout {
  if (typeof value !== "object" || value === null) return createDefaultPatientKpiLayout();
  const stored = value as { order?: unknown; visibility?: unknown };
  const suppliedOrder = Array.isArray(stored.order)
    ? stored.order.filter((id): id is PatientKpiId => typeof id === "string" && patientKpiIds.includes(id as PatientKpiId))
    : [];
  const visibilitySource = typeof stored.visibility === "object" && stored.visibility !== null
    ? stored.visibility as Record<string, unknown>
    : {};
  return {
    order: [...suppliedOrder, ...patientKpiIds.filter((id) => !suppliedOrder.includes(id))],
    visibility: Object.fromEntries(patientKpiIds.map((id) => [id, typeof visibilitySource[id] === "boolean" ? visibilitySource[id] : true])) as Record<PatientKpiId, boolean>,
  };
}

export function loadPatientKpiLayout(): PatientKpiLayout {
  try {
    const stored = window.localStorage.getItem(patientKpiLayoutStorageKey);
    return stored === null ? createDefaultPatientKpiLayout() : normalizePatientKpiLayout(JSON.parse(stored));
  } catch {
    return createDefaultPatientKpiLayout();
  }
}

export function savePatientKpiLayout(layout: PatientKpiLayout): void {
  try {
    window.localStorage.setItem(patientKpiLayoutStorageKey, JSON.stringify(layout));
  } catch {
    // Dashboard preferences remain optional when browser storage is unavailable.
  }
}
