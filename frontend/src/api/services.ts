import { apiGet } from "./client";
import type { Service } from "./types";

export type GetServicesParameters = {
  includeInactive?: boolean;
  search?: string;
};

export async function getServices(parameters: GetServicesParameters = {}): Promise<Service[]> {
  return (
    (await apiGet<Service[]>("/services", {
      include_inactive: parameters.includeInactive,
      search: parameters.search,
    })) ?? []
  );
}
