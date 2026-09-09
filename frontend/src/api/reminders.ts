import { apiGet } from "./client";
import type { Reminder } from "./types";

export type GetRemindersParameters = {
  invoiceId?: number;
};

export async function getReminders(parameters: GetRemindersParameters = {}): Promise<Reminder[]> {
  return (await apiGet<Reminder[]>("/reminders", { invoice_id: parameters.invoiceId })) ?? [];
}
