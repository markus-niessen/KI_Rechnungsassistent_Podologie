import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { activateService, createService, deactivateService, getService, getServices, updateService } from "../api/services";
import type { Service } from "../api/types";
import { serviceColumnStorageKey } from "../services/serviceHelpers";
import { ServiceDetailPage } from "./ServiceDetailPage";
import { ServiceFormPage } from "./ServiceFormPage";
import { ServicesPage } from "./ServicesPage";

vi.mock("../api/services", () => ({
  activateService: vi.fn(), createService: vi.fn(), deactivateService: vi.fn(), getService: vi.fn(), getServices: vi.fn(), updateService: vi.fn(),
}));

const mockedGetServices = vi.mocked(getServices);
const mockedGetService = vi.mocked(getService);
const mockedCreateService = vi.mocked(createService);
const mockedUpdateService = vi.mocked(updateService);
const mockedDeactivateService = vi.mocked(deactivateService);
const mockedActivateService = vi.mocked(activateService);

const service = (overrides: Partial<Service> = {}): Service => ({
  id: 1, name: "Fußpflege klein", service_type: "SERVICE", description: "Podologische Behandlung", net_price: "38.00", vat_rate: "19.00", active: true, created_at: "2026-01-01T00:00:00", ...overrides,
});

function renderWithRouter(node: ReactNode, route = "/services") {
  return render(<MemoryRouter initialEntries={[route]}><Routes><Route path="/services" element={node} /><Route path="/services/new" element={node} /><Route path="/services/:serviceId" element={node} /><Route path="/services/:serviceId/edit" element={node} /></Routes></MemoryRouter>);
}

afterEach(() => { vi.clearAllMocks(); window.localStorage.clear(); });

describe("ServicesPage", () => {
  it("loads all service types, filters them, and persists the column layout", async () => {
    const additional = service({ id: 2, name: "Mehrarbeit", service_type: "ADDITIONAL_SERVICE" });
    const product = service({ id: 3, name: "Pflegegel", service_type: "PRODUCT", active: false });
    mockedGetServices.mockResolvedValue([service(), additional, product]);
    renderWithRouter(<ServicesPage />);
    await waitFor(() => expect(screen.getAllByText("Fußpflege klein").length).toBeGreaterThan(0));
    expect(screen.getByText("Gesamt")).toBeInTheDocument();
    expect(screen.getAllByText("Zusatzleistung").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Produkt").length).toBeGreaterThan(0);
    fireEvent.change(screen.getByLabelText("Art filtern"), { target: { value: "PRODUCT" } });
    expect(screen.getAllByText("Pflegegel").length).toBeGreaterThan(0);
    expect(screen.queryByText("Mehrarbeit")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Spalten" }));
    fireEvent.click(screen.getByRole("checkbox", { name: "Beschreibung" }));
    expect(window.localStorage.getItem(serviceColumnStorageKey)).toContain("description");
  });

  it("shows loading, empty, and API error states", async () => {
    mockedGetServices.mockReturnValueOnce(new Promise(() => undefined));
    const { unmount } = renderWithRouter(<ServicesPage />);
    expect(screen.getByRole("status")).toHaveTextContent("werden geladen");
    unmount();
    mockedGetServices.mockResolvedValueOnce([]);
    renderWithRouter(<ServicesPage />);
    await waitFor(() => expect(screen.getByText("Noch keine Leistungen oder Produkte vorhanden.")).toBeInTheDocument());
  });

  it("confirms activation changes", async () => {
    mockedGetServices.mockResolvedValue([service()]);
    mockedDeactivateService.mockResolvedValue(service({ active: false }));
    renderWithRouter(<ServicesPage />);
    await waitFor(() => expect(screen.getByRole("button", { name: "Deaktivieren: Fußpflege klein" })).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Deaktivieren: Fußpflege klein" }));
    fireEvent.click(screen.getAllByRole("button", { name: "Deaktivieren" })[1]);
    await waitFor(() => expect(mockedDeactivateService).toHaveBeenCalledWith(1));
  });
});

describe("Service form", () => {
  it("creates an entry and calculates net to gross and gross to net", async () => {
    mockedCreateService.mockResolvedValue(service({ id: 2, name: "Pflegegel", service_type: "PRODUCT", net_price: "10.00" }));
    renderWithRouter(<ServiceFormPage mode="create" />, "/services/new");
    fireEvent.change(screen.getByLabelText("Bezeichnung"), { target: { value: "Pflegegel" } });
    fireEvent.change(screen.getByLabelText("Nettopreis"), { target: { value: "10.00" } });
    await waitFor(() => expect(screen.getByLabelText("Bruttopreis")).toHaveValue(11.9));
    fireEvent.change(screen.getByLabelText("Bruttopreis"), { target: { value: "11.90" } });
    expect(screen.getByLabelText("Nettopreis")).toHaveValue(10);
    fireEvent.click(screen.getByRole("button", { name: "Eintrag speichern" }));
    await waitFor(() => expect(mockedCreateService).toHaveBeenCalledWith(expect.objectContaining({ net_price: "10.00" })));
  });

  it("loads an entry and saves edits", async () => {
    mockedGetService.mockResolvedValue(service());
    mockedUpdateService.mockResolvedValue(service({ name: "Fußpflege groß" }));
    renderWithRouter(<ServiceFormPage mode="edit" />, "/services/1/edit");
    await waitFor(() => expect(screen.getByLabelText("Bezeichnung")).toHaveValue("Fußpflege klein"));
    fireEvent.change(screen.getByLabelText("Bezeichnung"), { target: { value: "Fußpflege groß" } });
    fireEvent.click(screen.getByRole("button", { name: "Änderungen speichern" }));
    await waitFor(() => expect(mockedUpdateService).toHaveBeenCalledWith(1, expect.objectContaining({ name: "Fußpflege groß" })));
  });
});

describe("Service detail", () => {
  it("shows detail data and a useful not-found state", async () => {
    mockedGetService.mockResolvedValue(service({ service_type: "PRODUCT" }));
    mockedActivateService.mockResolvedValue(service());
    const { unmount } = renderWithRouter(<ServiceDetailPage />, "/services/1");
    await waitFor(() => expect(screen.getByRole("heading", { level: 2, name: "Fußpflege klein" })).toBeInTheDocument());
    expect(screen.getAllByText("Produkt").length).toBeGreaterThan(0);

    unmount();
    mockedGetService.mockRejectedValueOnce(new Error("missing"));
    renderWithRouter(<ServiceDetailPage />, "/services/999");
    await waitFor(() => expect(screen.getByText("Der Eintrag wurde nicht gefunden oder existiert nicht mehr.")).toBeInTheDocument());
  });
});
