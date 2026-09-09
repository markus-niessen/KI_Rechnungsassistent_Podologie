import { apiGet } from "./client";
import type { Invoice } from "./types";

export type GetInvoicesParameters = {
  status?: string;
};

export async function getInvoices(parameters: GetInvoicesParameters = {}): Promise<Invoice[]> {
  return (await apiGet<Invoice[]>("/invoices", parameters)) ?? [];
}
