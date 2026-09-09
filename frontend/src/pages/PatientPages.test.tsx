import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  activatePatient,
  createPatient,
  deactivatePatient,
  getPatient,
  getPatientInvoices,
  getPatients,
  updatePatient,
} from "../api/patients";
import { getReminders } from "../api/reminders";
import type { Patient } from "../api/types";
import { patientColumnStorageKey } from "../patients/patientHelpers";
import { patientKpiLayoutStorageKey } from "../patients/patientKpiLayout";
import { PatientDetailPage } from "./PatientDetailPage";
import { PatientFormPage } from "./PatientFormPage";
import { PatientsPage } from "./PatientsPage";

vi.mock("../api/patients", () => ({
  activatePatient: vi.fn(), createPatient: vi.fn(), deactivatePatient: vi.fn(), getPatient: vi.fn(), getPatientInvoices: vi.fn(), getPatients: vi.fn(), updatePatient: vi.fn(),
}));
vi.mock("../api/reminders", () => ({ getReminders: vi.fn() }));

const mockedGetPatients = vi.mocked(getPatients);
const mockedGetPatient = vi.mocked(getPatient);
const mockedGetPatientInvoices = vi.mocked(getPatientInvoices);
const mockedGetReminders = vi.mocked(getReminders);
const mockedCreatePatient = vi.mocked(createPatient);
const mockedUpdatePatient = vi.mocked(updatePatient);
const mockedDeactivatePatient = vi.mocked(deactivatePatient);
const mockedActivatePatient = vi.mocked(activatePatient);

const patient = (overrides: Partial<Patient> = {}): Patient => ({
  id: 1, patient_nr: "P-000001", first_name: "Erika", last_name: "Muster", birth_date: "1950-01-01", deceased: false, death_date: null,
  street: "Musterstraße 1", zip: "12345", city: "Musterstadt", invoice_name: null, invoice_street: null, invoice_zip: null, invoice_city: null,
  home_name: "Sonnenhof", room: "12", active: true, created_at: "2026-01-01T00:00:00", updated_at: "2026-01-01T00:00:00", ...overrides,
});

function renderWithRouter(node: ReactNode, route = "/patients") {
  return render(<MemoryRouter initialEntries={[route]}><Routes><Route path="/patients" element={node} /><Route path="/patients/new" element={node} /><Route path="/patients/:patientId" element={node} /><Route path="/patients/:patientId/edit" element={node} /></Routes></MemoryRouter>);
}

afterEach(() => {
  vi.clearAllMocks();
  window.localStorage.clear();
});

describe("PatientsPage", () => {
  it("loads patients, filters them, persists column choices, and changes status", async () => {
    const inactivePatient = patient({ id: 2, first_name: "Ina", active: false, city: "Andersstadt" });
    mockedGetPatients.mockResolvedValue([patient(), inactivePatient]);
    mockedDeactivatePatient.mockResolvedValue(patient({ active: false }));

    renderWithRouter(<PatientsPage />);
    await waitFor(() => expect(screen.getAllByText("Erika Muster").length).toBeGreaterThan(0));
    fireEvent.click(screen.getByRole("button", { name: /^Inaktiv/ }));
    expect(screen.getAllByText("Ina Muster").length).toBeGreaterThan(0);
    expect(screen.queryByText("Erika Muster")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Spalten" }));
    fireEvent.click(screen.getByRole("checkbox", { name: "Zimmer" }));
    expect(window.localStorage.getItem(patientColumnStorageKey)).toContain("room");

    fireEvent.click(screen.getByRole("button", { name: /^Alle/ }));
    fireEvent.click(screen.getAllByRole("button", { name: "Weitere Aktionen für Erika Muster" })[0]);
    fireEvent.click(screen.getByRole("menuitem", { name: "Deaktivieren" }));
    expect(mockedDeactivatePatient).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Deaktivieren" }));
    await waitFor(() => expect(mockedDeactivatePatient).toHaveBeenCalledWith(1));
  });

  it("closes the column popover with Escape and keeps home and room visible by default", async () => {
    mockedGetPatients.mockResolvedValue([patient()]);
    renderWithRouter(<PatientsPage />);
    await waitFor(() => expect(screen.getByRole("columnheader", { name: "Heim / Einrichtung" })).toBeInTheDocument());
    expect(screen.getByRole("columnheader", { name: "Zimmer" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Spalten" }));
    expect(screen.getByRole("menu", { name: "Spalten auswählen" })).toBeInTheDocument();
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("menu", { name: "Spalten auswählen" })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Spalten" }));
    fireEvent.mouseDown(document.body);
    expect(screen.queryByRole("menu", { name: "Spalten auswählen" })).not.toBeInTheDocument();
  });

  it("shows loading, empty, and error states", async () => {
    mockedGetPatients.mockReturnValueOnce(new Promise(() => undefined));
    const { unmount } = renderWithRouter(<PatientsPage />);
    expect(screen.getByRole("status")).toHaveTextContent("Patienten werden geladen");
    unmount();

    mockedGetPatients.mockResolvedValueOnce([]);
    renderWithRouter(<PatientsPage />);
    await waitFor(() => expect(screen.getByText("Noch keine Patienten vorhanden.")).toBeInTheDocument());
  });

  it("shows an API error and restores saved column visibility", async () => {
    mockedGetPatients.mockRejectedValueOnce(new Error("offline"));
    const { unmount } = renderWithRouter(<PatientsPage />);
    await waitFor(() => expect(screen.getByText("Die Daten konnten momentan nicht geladen werden.")).toBeInTheDocument());
    unmount();

    window.localStorage.setItem(patientColumnStorageKey, JSON.stringify({ address: true, home: true, patientNr: true, room: false, status: true }));
    mockedGetPatients.mockResolvedValueOnce([patient()]);
    renderWithRouter(<PatientsPage />);
    await waitFor(() => expect(screen.getByRole("columnheader", { name: "Name" })).toBeInTheDocument());
    expect(screen.queryByRole("columnheader", { name: "Zimmer" })).not.toBeInTheDocument();
  });

  it("persists reordered columns and restores the default layout", async () => {
    mockedGetPatients.mockResolvedValue([patient()]);
    const { unmount } = renderWithRouter(<PatientsPage />);
    await waitFor(() => expect(screen.getByRole("columnheader", { name: "Patientennummer" })).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Spalten" }));
    fireEvent.click(screen.getByRole("button", { name: "Name nach oben" }));
    expect(JSON.parse(window.localStorage.getItem(patientColumnStorageKey) ?? "{}").order[0]).toBe("name");
    unmount();
    renderWithRouter(<PatientsPage />);
    await waitFor(() => expect(screen.getAllByRole("columnheader")[0]).toHaveTextContent("Name"));
    fireEvent.click(screen.getByRole("button", { name: "Spalten" }));
    fireEvent.click(screen.getByRole("button", { name: "Standard wiederherstellen" }));
    expect(JSON.parse(window.localStorage.getItem(patientColumnStorageKey) ?? "{}").order[0]).toBe("patientNr");
  });
});

describe("Patient form", () => {
  it("validates required fields and creates a patient", async () => {
    mockedCreatePatient.mockResolvedValue(patient());
    renderWithRouter(<PatientFormPage mode="create" />, "/patients/new");

    fireEvent.click(screen.getByRole("button", { name: "Patient speichern" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Vorname und Nachname sind erforderlich");
    fireEvent.change(screen.getByLabelText("Vorname"), { target: { value: "Erika" } });
    fireEvent.change(screen.getByLabelText("Nachname"), { target: { value: "Muster" } });
    fireEvent.click(screen.getByRole("button", { name: "Patient speichern" }));
    await waitFor(() => expect(mockedCreatePatient).toHaveBeenCalled());
  });

  it("loads existing values and saves an edit", async () => {
    mockedGetPatient.mockResolvedValue(patient());
    mockedUpdatePatient.mockResolvedValue(patient({ city: "Neuort" }));
    renderWithRouter(<PatientFormPage mode="edit" />, "/patients/1/edit");
    await waitFor(() => expect(screen.getByLabelText("Vorname")).toHaveValue("Erika"));
    fireEvent.change(screen.getByLabelText("Ort"), { target: { value: "Neuort" } });
    fireEvent.click(screen.getByRole("button", { name: "Änderungen speichern" }));
    await waitFor(() => expect(mockedUpdatePatient).toHaveBeenCalledWith(1, expect.objectContaining({ city: "Neuort" })));
  });

  it("shows the automatic patient number and toggles the invoice address", () => {
    renderWithRouter(<PatientFormPage mode="create" />, "/patients/new");
    expect(screen.getByDisplayValue("Wird automatisch vergeben")).toBeDisabled();
    expect(screen.queryByLabelText("Rechnungsempfänger")).not.toBeInTheDocument();
    fireEvent.click(screen.getByLabelText("Abweichende Rechnungsanschrift verwenden"));
    expect(screen.getByLabelText("Rechnungsempfänger")).toBeInTheDocument();
  });

  it("confirms deceased changes without changing the active status", async () => {
    mockedGetPatient.mockResolvedValue(patient({ active: true }));
    mockedUpdatePatient.mockResolvedValue(patient({ deceased: true, death_date: "2026-01-01", active: true }));
    renderWithRouter(<PatientFormPage mode="edit" />, "/patients/1/edit");
    await waitFor(() => expect(screen.getByLabelText("Verstorben")).not.toBeChecked());
    fireEvent.click(screen.getByLabelText("Verstorben"));
    expect(screen.getByRole("dialog", { name: "Patient als verstorben markieren?" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Abbrechen" }));
    expect(screen.getByLabelText("Verstorben")).not.toBeChecked();
    fireEvent.click(screen.getByLabelText("Verstorben"));
    fireEvent.click(screen.getByRole("button", { name: "Als verstorben markieren" }));
    fireEvent.click(screen.getByRole("button", { name: "Änderungen speichern" }));
    await waitFor(() => expect(mockedUpdatePatient).toHaveBeenCalledWith(1, expect.objectContaining({ deceased: true })));
    expect(mockedUpdatePatient.mock.calls[0][1]).not.toHaveProperty("active");
  });

  it("confirms removal of an existing deceased marker", async () => {
    mockedGetPatient.mockResolvedValue(patient({ deceased: true, death_date: "2026-01-01" }));
    renderWithRouter(<PatientFormPage mode="edit" />, "/patients/1/edit");
    await waitFor(() => expect(screen.getByLabelText("Verstorben")).toBeChecked());
    fireEvent.click(screen.getByLabelText("Verstorben"));
    expect(screen.getByText("Diese Änderung sollte nur vorgenommen werden, wenn der Status versehentlich gesetzt wurde.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Kennzeichnung aufheben" }));
    expect(screen.getByLabelText("Verstorben")).not.toBeChecked();
  });
});

describe("Patient detail", () => {
  it("loads patient data, renders invoices and empty detail tabs", async () => {
    mockedGetPatient.mockResolvedValue(patient());
    mockedGetPatientInvoices.mockResolvedValue([{ id: 9, invoice_number: "EU-RE-2026-000001", document_type: "INVOICE", status: "FINAL", invoice_date: "2026-01-01", due_date: "2026-01-10", subtotal: "10.00", tax_total: "0.00", total: "10.00", item_count: 1, pdf_available: true }]);
    mockedGetReminders.mockResolvedValue([]);
    mockedActivatePatient.mockResolvedValue(patient());

    renderWithRouter(<PatientDetailPage />, "/patients/1");
    await waitFor(() => expect(screen.getByRole("heading", { name: "Erika Muster" })).toBeInTheDocument());
    expect(screen.getAllByText("–")).toHaveLength(4);
    expect(screen.queryByLabelText("Erika Muster öffnen")).not.toBeInTheDocument();
    expect(screen.getAllByText("Patient bearbeiten")).toHaveLength(1);
    fireEvent.click(screen.getByRole("tab", { name: "Rechnungen" }));
    expect(screen.getByText("EU-RE-2026-000001")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("tab", { name: "Dokumentation" }));
    expect(screen.getByText("Für diesen Patienten sind keine Dokumentationsdaten verfügbar.")).toBeInTheDocument();
  });

  it("shows a not-found state", async () => {
    mockedGetPatient.mockRejectedValue(new Error("Not found"));
    mockedGetPatientInvoices.mockResolvedValue([]);
    mockedGetReminders.mockResolvedValue([]);
    renderWithRouter(<PatientDetailPage />, "/patients/404");
    await waitFor(() => expect(screen.getByText("Der Patient wurde nicht gefunden oder existiert nicht mehr.")).toBeInTheDocument());
  });

  it("keeps the action menu for a deceased patient", async () => {
    mockedGetPatient.mockResolvedValue(patient({ deceased: true, active: true }));
    mockedGetPatientInvoices.mockResolvedValue([]);
    mockedGetReminders.mockResolvedValue([]);
    renderWithRouter(<PatientDetailPage />, "/patients/1");
    await waitFor(() => expect(screen.getByRole("heading", { name: "Erika Muster" })).toBeInTheDocument());
    expect(screen.getByRole("button", { name: "Weitere Aktionen für Erika Muster" })).toBeInTheDocument();
  });

  it("reorders KPI widgets by drag and drop and restores that order after remounting", async () => {
    mockedGetPatient.mockResolvedValue(patient());
    mockedGetPatientInvoices.mockResolvedValue([]);
    mockedGetReminders.mockResolvedValue([]);
    const { unmount } = renderWithRouter(<PatientDetailPage />, "/patients/1");
    await waitFor(() => expect(screen.getAllByRole("article")).toHaveLength(4));
    const dataTransfer = { effectAllowed: "", getData: vi.fn(() => "not-due"), setData: vi.fn() };
    const widgets = screen.getAllByRole("article");
    fireEvent.dragStart(widgets[0], { dataTransfer });
    fireEvent.dragOver(widgets[2], { dataTransfer });
    fireEvent.drop(widgets[2], { dataTransfer });
    expect(screen.getAllByRole("article")[0]).toHaveAccessibleName("Offen");
    expect(window.localStorage.getItem(patientKpiLayoutStorageKey)).toContain('"open","not-due"');

    unmount();
    renderWithRouter(<PatientDetailPage />, "/patients/1");
    await waitFor(() => expect(screen.getAllByRole("article")[0]).toHaveAccessibleName("Offen"));
  });

  it("hides, restores and resets KPI widgets", async () => {
    mockedGetPatient.mockResolvedValue(patient());
    mockedGetPatientInvoices.mockResolvedValue([]);
    mockedGetReminders.mockResolvedValue([]);
    renderWithRouter(<PatientDetailPage />, "/patients/1");
    await waitFor(() => expect(screen.getAllByRole("article")).toHaveLength(4));
    fireEvent.click(screen.getByRole("button", { name: "Widgets anpassen" }));
    fireEvent.click(screen.getByRole("checkbox", { name: "Offen" }));
    expect(screen.queryByRole("article", { name: "Offen" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("checkbox", { name: "Offen" }));
    expect(screen.getByRole("article", { name: "Offen" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Offen nach hinten verschieben" }));
    fireEvent.click(screen.getByRole("button", { name: "Standard wiederherstellen" }));
    expect(screen.getAllByRole("article")[0]).toHaveAccessibleName("Noch nicht fällig");
  });
});
