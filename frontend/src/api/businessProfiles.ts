import { apiGet } from "./client";
import type { BusinessProfile } from "./types";

export type GetBusinessProfilesParameters = {
  includeInactive?: boolean;
  search?: string;
};

export async function getBusinessProfiles(parameters: GetBusinessProfilesParameters = {}): Promise<BusinessProfile[]> {
  return (
    (await apiGet<BusinessProfile[]>("/business-profiles", {
      include_inactive: parameters.includeInactive,
      search: parameters.search,
    })) ?? []
  );
}
