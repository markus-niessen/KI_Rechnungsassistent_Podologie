import { getInvoices } from "../api/invoices";
import { getPatients } from "../api/patients";
import { getReminders } from "../api/reminders";
import type { Invoice, Reminder } from "../api/types";

export type DashboardData = {
  activePatients: number;
  openInvoices: number;
  overdueInvoices: number;
  draftInvoices: number;
  openReminders: number;
  aiReviewRequired: number;
};

function isPositiveMoney(amount: string): boolean {
  return Number(amount) > 0;
}

function isOverdue(invoice: Invoice, today: Date): boolean {
  if (invoice.status !== "FINAL" || !isPositiveMoney(invoice.remaining_amount)) {
    return false;
  }

  const dueDate = new Date(`${invoice.due_date}T00:00:00Z`);
  const currentDate = new Date(Date.UTC(today.getFullYear(), today.getMonth(), today.getDate()));
  return dueDate < currentDate;
}

function isOpenReminder(reminder: Reminder): boolean {
  return reminder.status === "DRAFT" || reminder.status === "ISSUED";
}

export async function getDashboardData(today = new Date()): Promise<DashboardData> {
  const [patients, invoices, reminders] = await Promise.all([getPatients(), getInvoices(), getReminders()]);

  return {
    activePatients: patients.filter((patient) => patient.active).length,
    openInvoices: invoices.filter(
      (invoice) => invoice.status === "FINAL" && isPositiveMoney(invoice.remaining_amount),
    ).length,
    overdueInvoices: invoices.filter((invoice) => isOverdue(invoice, today)).length,
    draftInvoices: invoices.filter((invoice) => invoice.status === "DRAFT").length,
    openReminders: reminders.filter(isOpenReminder).length,
    aiReviewRequired: invoices.filter((invoice) => invoice.ai_review_comment !== null).length,
  };
}
