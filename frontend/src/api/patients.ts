import { apiGet } from "./client";
import type { Patient } from "./types";

export type GetPatientsParameters = {
  includeInactive?: boolean;
  search?: string;
};

export async function getPatients(parameters: GetPatientsParameters = {}): Promise<Patient[]> {
  return (
    (await apiGet<Patient[]>("/patients", {
      include_inactive: parameters.includeInactive,
      search: parameters.search,
    })) ?? []
  );
}
