import type { BusinessProfile, BusinessProfileInput } from "../api/types";

export const businessColumnStorageKey = "ki-rechnungsassistent.business-profile-table-columns";
export const businessWidgetStorageKey = "ki-rechnungsassistent.business-profile-widgets";

export type BusinessColumnId = "business" | "city" | "createdAt" | "email" | "iban" | "ik" | "location" | "locationCode" | "phone" | "prefix" | "status" | "tax" | "updatedAt" | "vat";
export type BusinessColumnLayout = { order: BusinessColumnId[]; visibility: Record<BusinessColumnId, boolean> };
export type BusinessWidgetId = "active" | "businesses" | "inactive";
export type BusinessWidgetLayout = { order: BusinessWidgetId[]; visibility: Record<BusinessWidgetId, boolean> };

export const businessColumns: Array<{ id: BusinessColumnId; label: string; required?: boolean }> = [
  { id: "business", label: "Betrieb", required: true }, { id: "location", label: "Standort", required: true },
  { id: "city", label: "Ort", required: true }, { id: "locationCode", label: "Standortkürzel" },
  { id: "prefix", label: "Rechnungspräfix", required: true }, { id: "ik", label: "IK-Nummer" },
  { id: "phone", label: "Telefon" }, { id: "email", label: "E-Mail" }, { id: "tax", label: "Steuernummer" },
  { id: "vat", label: "USt-IdNr." }, { id: "iban", label: "IBAN" }, { id: "status", label: "Status" },
  { id: "createdAt", label: "Erstellt am" }, { id: "updatedAt", label: "Zuletzt geändert" },
];
export const businessWidgets: Array<{ id: BusinessWidgetId; label: string; description: string }> = [
  { id: "active", label: "Aktive Standorte", description: "Für neue Rechnungen verfügbar" },
  { id: "inactive", label: "Inaktive Standorte", description: "Derzeit nicht für neue Rechnungen verfügbar" },
  { id: "businesses", label: "Betriebe", description: "Eindeutige Betriebsnamen" },
];

function defaultLayout<T extends string>(ids: T[]): { order: T[]; visibility: Record<T, boolean> } { return { order: [...ids], visibility: Object.fromEntries(ids.map((id) => [id, true])) as Record<T, boolean> }; }
function loadLayout<T extends string>(key: string, ids: T[]): { order: T[]; visibility: Record<T, boolean> } { try { const parsed = JSON.parse(window.localStorage.getItem(key) ?? "null") as { order?: unknown; visibility?: unknown } | null; if (!parsed || typeof parsed !== "object") return defaultLayout(ids); const supplied = Array.isArray(parsed.order) ? parsed.order.filter((id): id is T => typeof id === "string" && ids.includes(id as T)) : []; const visibilitySource = typeof parsed.visibility === "object" && parsed.visibility !== null ? parsed.visibility as Record<string, unknown> : {}; const visibility = Object.fromEntries(ids.map((id) => [id, typeof visibilitySource[id] === "boolean" ? visibilitySource[id] : true])) as Record<T, boolean>; return Object.values(visibility).some(Boolean) ? { order: [...new Set(supplied), ...ids.filter((id) => !supplied.includes(id))], visibility } : defaultLayout(ids); } catch { return defaultLayout(ids); } }
function saveLayout<T extends string>(key: string, layout: { order: T[]; visibility: Record<T, boolean> }): void { try { window.localStorage.setItem(key, JSON.stringify(layout)); } catch { /* optional preferences */ } }

export function defaultBusinessColumnLayout(): BusinessColumnLayout { return defaultLayout(businessColumns.map((column) => column.id)); }
export function loadBusinessColumnLayout(): BusinessColumnLayout { return loadLayout(businessColumnStorageKey, businessColumns.map((column) => column.id)); }
export function saveBusinessColumnLayout(layout: BusinessColumnLayout): void { saveLayout(businessColumnStorageKey, layout); }
export function defaultBusinessWidgetLayout(): BusinessWidgetLayout { return defaultLayout(businessWidgets.map((widget) => widget.id)); }
export function loadBusinessWidgetLayout(): BusinessWidgetLayout { return loadLayout(businessWidgetStorageKey, businessWidgets.map((widget) => widget.id)); }
export function saveBusinessWidgetLayout(layout: BusinessWidgetLayout): void { saveLayout(businessWidgetStorageKey, layout); }

export function emptyBusinessProfileInput(): BusinessProfileInput { return { business_name: "", location_name: "", location_code: null, street: "", postal_code: "", city: "", phone: null, email: null, tax_number: null, vat_id: null, ik_number: null, iban: "", bic: null, bank_name: null, logo_path: null }; }
export function businessProfileToInput(profile: BusinessProfile): BusinessProfileInput { const { id: _id, invoice_prefix: _prefix, active: _active, created_at: _createdAt, updated_at: _updatedAt, ...input } = profile; return input; }
export function normalizeBusinessProfileInput(input: BusinessProfileInput): BusinessProfileInput { const optional = (value: string | null) => value?.trim() || null; return { ...input, business_name: input.business_name.trim(), location_name: input.location_name.trim(), street: input.street.trim(), postal_code: input.postal_code.trim(), city: input.city.trim(), iban: input.iban.trim().replaceAll(" ", ""), location_code: optional(input.location_code), phone: optional(input.phone), email: optional(input.email), tax_number: optional(input.tax_number), vat_id: optional(input.vat_id), ik_number: optional(input.ik_number), bic: optional(input.bic), bank_name: optional(input.bank_name), logo_path: optional(input.logo_path) }; }
export function maskIban(iban: string): string { return iban.length > 8 ? `${iban.slice(0, 4)}••••${iban.slice(-4)}` : iban; }
