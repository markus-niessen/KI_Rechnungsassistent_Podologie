import { afterEach, describe, expect, it, vi } from "vitest";

import { getInvoices } from "../api/invoices";
import { getPatients } from "../api/patients";
import { getReminders } from "../api/reminders";
import type { Invoice, Patient, Reminder } from "../api/types";
import { getDashboardData } from "./dashboardData";

vi.mock("../api/invoices", () => ({ getInvoices: vi.fn() }));
vi.mock("../api/patients", () => ({ getPatients: vi.fn() }));
vi.mock("../api/reminders", () => ({ getReminders: vi.fn() }));

const mockedGetInvoices = vi.mocked(getInvoices);
const mockedGetPatients = vi.mocked(getPatients);
const mockedGetReminders = vi.mocked(getReminders);

function patient(overrides: Partial<Patient> = {}): Patient {
  return {
    id: 1,
    patient_nr: "P-000001",
    first_name: "Test",
    last_name: "Patient",
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
    active: true,
    created_at: "2026-01-01T00:00:00",
    updated_at: "2026-01-01T00:00:00",
    ...overrides,
  };
}

function invoice(overrides: Partial<Invoice> = {}): Invoice {
  return {
    id: 1,
    company_id: 1,
    patient_id: 1,
    document_type: "INVOICE",
    status: "FINAL",
    invoice_number: "EU-RE-2026-000001",
    invoice_date: "2026-01-01",
    due_date: "2026-01-10",
    subtotal: "10.00",
    tax_total: "0.00",
    total: "10.00",
    source_text: null,
    ai_review_comment: null,
    patient_resolution_required: false,
    ready_for_finalization: true,
    paid_amount: "0.00",
    remaining_amount: "10.00",
    payment_status: "OPEN",
    created_at: "2026-01-01T00:00:00",
    item_count: 1,
    ...overrides,
  };
}

function reminder(overrides: Partial<Reminder> = {}): Reminder {
  return {
    id: 1,
    invoice_id: 1,
    sequence: 0,
    type: "PAYMENT_REMINDER",
    open_amount: "10.00",
    reminder_fee: "0.00",
    postage_fee: "0.00",
    status: "DRAFT",
    issued_at: null,
    snoozed_until: null,
    reminder_fee_waived: false,
    postage_fee_waived: false,
    created_at: "2026-01-01T00:00:00",
    updated_at: "2026-01-01T00:00:00",
    total_due: "10.00",
    ...overrides,
  };
}

function configureApiData({
  patients = [],
  invoices = [],
  reminders = [],
}: {
  patients?: Patient[];
  invoices?: Invoice[];
  reminders?: Reminder[];
} = {}) {
  mockedGetPatients.mockResolvedValue(patients);
  mockedGetInvoices.mockResolvedValue(invoices);
  mockedGetReminders.mockResolvedValue(reminders);
}

afterEach(() => {
  vi.clearAllMocks();
});

describe("getDashboardData", () => {
  it("counts active patients, drafts, open invoices, open reminders, and AI reviews", async () => {
    configureApiData({
      patients: [patient(), patient({ id: 2, active: false })],
      invoices: [
        invoice(),
        invoice({ id: 2, status: "DRAFT", invoice_number: null, remaining_amount: "0.00" }),
        invoice({ id: 3, ai_review_comment: "Bitte prüfen" }),
      ],
      reminders: [reminder(), reminder({ id: 2, status: "ISSUED" }), reminder({ id: 3, status: "PAID" })],
    });

    await expect(getDashboardData(new Date(2026, 0, 11))).resolves.toEqual({
      activePatients: 1,
      openInvoices: 2,
      overdueInvoices: 2,
      draftInvoices: 1,
      openReminders: 2,
      aiReviewRequired: 1,
    });
  });

  it("does not count paid invoices as open", async () => {
    configureApiData({ invoices: [invoice({ remaining_amount: "0.00", payment_status: "PAID" })] });

    await expect(getDashboardData(new Date(2026, 0, 11))).resolves.toMatchObject({
      openInvoices: 0,
      overdueInvoices: 0,
    });
  });

  it("counts only invoices due before today as overdue", async () => {
    configureApiData({
      invoices: [
        invoice({ due_date: "2026-01-09" }),
        invoice({ id: 2, due_date: "2026-01-10" }),
        invoice({ id: 3, due_date: "2026-01-11" }),
      ],
    });

    await expect(getDashboardData(new Date(2026, 0, 10))).resolves.toMatchObject({ overdueInvoices: 1 });
  });

  it("treats decimal money values numerically", async () => {
    configureApiData({
      invoices: [
        invoice({ remaining_amount: "0.00" }),
        invoice({ id: 2, remaining_amount: "0.01" }),
        invoice({ id: 3, remaining_amount: "10.00" }),
      ],
    });

    await expect(getDashboardData(new Date(2026, 0, 11))).resolves.toMatchObject({ openInvoices: 2 });
  });

  it("does not count paid or cancelled reminders as open", async () => {
    configureApiData({
      reminders: [
        reminder({ status: "DRAFT" }),
        reminder({ id: 2, status: "ISSUED" }),
        reminder({ id: 3, status: "PAID" }),
        reminder({ id: 4, status: "CANCELLED" }),
      ],
    });

    await expect(getDashboardData()).resolves.toMatchObject({ openReminders: 2 });
  });

  it("starts the three API requests in parallel without additional calls", async () => {
    let resolvePatients!: (patients: Patient[]) => void;
    let resolveInvoices!: (invoices: Invoice[]) => void;
    let resolveReminders!: (reminders: Reminder[]) => void;
    mockedGetPatients.mockReturnValue(new Promise((resolve) => (resolvePatients = resolve)));
    mockedGetInvoices.mockReturnValue(new Promise((resolve) => (resolveInvoices = resolve)));
    mockedGetReminders.mockReturnValue(new Promise((resolve) => (resolveReminders = resolve)));

    const result = getDashboardData();

    expect(mockedGetPatients).toHaveBeenCalledOnce();
    expect(mockedGetInvoices).toHaveBeenCalledOnce();
    expect(mockedGetReminders).toHaveBeenCalledOnce();

    resolvePatients([]);
    resolveInvoices([]);
    resolveReminders([]);

    await expect(result).resolves.toEqual({
      activePatients: 0,
      openInvoices: 0,
      overdueInvoices: 0,
      draftInvoices: 0,
      openReminders: 0,
      aiReviewRequired: 0,
    });
  });
});
