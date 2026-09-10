import type { Service, ServiceInput, ServiceType } from "../api/types";

export const serviceColumnStorageKey = "ki-rechnungsassistent.service-table-columns";

export type ServiceColumnId = "description" | "grossPrice" | "name" | "netPrice" | "status" | "type" | "vatRate";

export type ServiceColumnLayout = {
  order: ServiceColumnId[];
  visibility: Record<ServiceColumnId, boolean>;
};

export const serviceColumns: Array<{ id: ServiceColumnId; label: string; required?: boolean }> = [
  { id: "name", label: "Name", required: true },
  { id: "type", label: "Typ", required: true },
  { id: "description", label: "Beschreibung" },
  { id: "netPrice", label: "Nettopreis" },
  { id: "vatRate", label: "MwSt." },
  { id: "grossPrice", label: "Bruttopreis" },
  { id: "status", label: "Status" },
];

export const serviceTypeLabels: Record<ServiceType, string> = {
  SERVICE: "Leistung",
  ADDITIONAL_SERVICE: "Zusatzleistung",
  PRODUCT: "Produkt",
};

export function defaultServiceColumnLayout(): ServiceColumnLayout {
  return {
    order: serviceColumns.map((column) => column.id),
    visibility: Object.fromEntries(serviceColumns.map((column) => [column.id, true])) as Record<ServiceColumnId, boolean>,
  };
}

export function loadServiceColumnLayout(): ServiceColumnLayout {
  try {
    const parsed = JSON.parse(window.localStorage.getItem(serviceColumnStorageKey) ?? "null") as Record<string, unknown> | null;
    if (parsed === null || typeof parsed !== "object") return defaultServiceColumnLayout();
    const visibilitySource = typeof parsed.visibility === "object" && parsed.visibility !== null
      ? parsed.visibility as Record<string, unknown>
      : parsed;
    const savedOrder = Array.isArray(parsed.order)
      ? parsed.order.filter((id): id is ServiceColumnId => serviceColumns.some((column) => column.id === id))
      : [];
    const order = [...savedOrder, ...serviceColumns.map((column) => column.id).filter((id) => !savedOrder.includes(id))];
    const visibility = Object.fromEntries(serviceColumns.map((column) => [
      column.id,
      column.required || typeof visibilitySource[column.id] !== "boolean" ? true : visibilitySource[column.id],
    ])) as Record<ServiceColumnId, boolean>;
    return { order, visibility };
  } catch {
    return defaultServiceColumnLayout();
  }
}

export function saveServiceColumnLayout(layout: ServiceColumnLayout): void {
  try {
    window.localStorage.setItem(serviceColumnStorageKey, JSON.stringify(layout));
  } catch {
    // Table preferences are optional.
  }
}

export function serviceGrossPrice(service: Pick<Service, "net_price" | "vat_rate">): number {
  return Number(service.net_price) * (1 + Number(service.vat_rate) / 100);
}

export function formatCurrency(value: number | string): string {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? `${numeric.toFixed(2).replace(".", ",")} €` : "–";
}

export function emptyServiceInput(): ServiceInput {
  return { name: "", service_type: "SERVICE", description: null, net_price: "0.00", vat_rate: "19.00" };
}

export function serviceToInput(service: Service): ServiceInput {
  return {
    name: service.name,
    service_type: service.service_type,
    description: service.description,
    net_price: service.net_price,
    vat_rate: service.vat_rate,
  };
}

export function normalizeServiceInput(input: ServiceInput): ServiceInput {
  return {
    ...input,
    name: input.name.trim(),
    description: input.description?.trim() || null,
    net_price: Number(input.net_price.replace(",", ".")).toFixed(2),
    vat_rate: Number(input.vat_rate.replace(",", ".")).toFixed(2),
  };
}
