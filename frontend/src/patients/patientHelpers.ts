import type { Patient, PatientInput } from "../api/types";

export const patientColumnStorageKey = "ki-rechnungsassistent.patient-table-columns";

export type PatientColumnId = "address" | "home" | "name" | "patientNr" | "room" | "status";

export type PatientColumnLayout = {
  order: PatientColumnId[];
  visibility: Record<PatientColumnId, boolean>;
};

export const patientColumns: Array<{ id: PatientColumnId; label: string }> = [
  { id: "patientNr", label: "Patientennummer" },
  { id: "name", label: "Name" },
  { id: "address", label: "Adresse" },
  { id: "home", label: "Heim / Einrichtung" },
  { id: "room", label: "Zimmer" },
  { id: "status", label: "Status" },
];

export function defaultPatientColumns(): Record<PatientColumnId, boolean> {
  return Object.fromEntries(patientColumns.map((column) => [column.id, true])) as Record<PatientColumnId, boolean>;
}

export function defaultPatientColumnLayout(): PatientColumnLayout {
  return { order: patientColumns.map((column) => column.id), visibility: defaultPatientColumns() };
}

export function loadPatientColumns(): Record<PatientColumnId, boolean> {
  return loadPatientColumnLayout().visibility;
}

export function loadPatientColumnLayout(): PatientColumnLayout {
  try {
    const saved = window.localStorage.getItem(patientColumnStorageKey);
    if (saved === null) {
      return defaultPatientColumnLayout();
    }
    const parsed = JSON.parse(saved) as Record<string, unknown>;
    const visibilitySource = typeof parsed.visibility === "object" && parsed.visibility !== null
      ? parsed.visibility as Record<string, unknown>
      : parsed;
    const suppliedOrder = Array.isArray(parsed.order) ? parsed.order.filter((column): column is PatientColumnId => patientColumns.some(({ id }) => id === column)) : [];
    const order = [...suppliedOrder, ...patientColumns.map((column) => column.id).filter((id) => !suppliedOrder.includes(id))];
    const visibility = Object.fromEntries(
      patientColumns.map((column) => [column.id, typeof visibilitySource[column.id] === "boolean" ? visibilitySource[column.id] : true]),
    ) as Record<PatientColumnId, boolean>;
    return { order, visibility };
  } catch {
    return defaultPatientColumnLayout();
  }
}

export function savePatientColumns(columns: Record<PatientColumnId, boolean>): void {
  savePatientColumnLayout({ order: patientColumns.map((column) => column.id), visibility: columns });
}

export function savePatientColumnLayout(layout: PatientColumnLayout): void {
  try {
    window.localStorage.setItem(patientColumnStorageKey, JSON.stringify(layout));
  } catch {
    // Table preferences remain optional when browser storage is unavailable.
  }
}

export function patientAddress(patient: Patient): string {
  return [patient.street, [patient.zip, patient.city].filter(Boolean).join(" ")].filter(Boolean).join(", ") || "–";
}

export function patientStatus(patient: Patient): string {
  if (patient.deceased) {
    return "Verstorben";
  }
  return patient.active ? "Aktiv" : "Inaktiv";
}

export function emptyPatientInput(): PatientInput {
  return {
    first_name: "",
    last_name: "",
    birth_date: null,
    deceased: false,
    death_date: null,
    street: null,
    zip: null,
    city: null,
    invoice_name: null,
    invoice_street: null,
    invoice_zip: null,
    invoice_city: null,
    home_name: null,
    room: null,
  };
}

export function patientToInput(patient: Patient): PatientInput {
  const { id: _id, patient_nr: _patientNr, active: _active, created_at: _createdAt, updated_at: _updatedAt, ...input } = patient;
  return input;
}

export function normalizePatientInput(input: PatientInput): PatientInput {
  const normalize = (value: string | null) => value?.trim() || null;
  return {
    ...input,
    first_name: input.first_name.trim(),
    last_name: input.last_name.trim(),
    birth_date: normalize(input.birth_date),
    death_date: input.deceased ? normalize(input.death_date) : null,
    street: normalize(input.street),
    zip: normalize(input.zip),
    city: normalize(input.city),
    invoice_name: normalize(input.invoice_name),
    invoice_street: normalize(input.invoice_street),
    invoice_zip: normalize(input.invoice_zip),
    invoice_city: normalize(input.invoice_city),
    home_name: normalize(input.home_name),
    room: normalize(input.room),
  };
}
