import { apiGet, apiRequest } from "./client";
import type { BusinessProfile, BusinessProfileInput } from "./types";

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

export async function getBusinessProfile(profileId: number): Promise<BusinessProfile> {
  return (await apiGet<BusinessProfile>(`/business-profiles/${profileId}`)) as BusinessProfile;
}

export async function createBusinessProfile(profile: BusinessProfileInput): Promise<BusinessProfile> {
  return (await apiRequest<BusinessProfile>("/business-profiles", { method: "POST", body: profile })) as BusinessProfile;
}

export async function updateBusinessProfile(profileId: number, profile: BusinessProfileInput): Promise<BusinessProfile> {
  return (await apiRequest<BusinessProfile>(`/business-profiles/${profileId}`, { method: "PATCH", body: profile })) as BusinessProfile;
}

export async function activateBusinessProfile(profileId: number): Promise<BusinessProfile> {
  return (await apiRequest<BusinessProfile>(`/business-profiles/${profileId}/activate`, { method: "POST" })) as BusinessProfile;
}

export async function deactivateBusinessProfile(profileId: number): Promise<BusinessProfile> {
  return (await apiRequest<BusinessProfile>(`/business-profiles/${profileId}/deactivate`, { method: "POST" })) as BusinessProfile;
}

export async function uploadBusinessProfileLogo(profileId: number, logo: File): Promise<BusinessProfile> {
  const body = new FormData();
  body.append("logo", logo);
  const response = await fetch(`/business-profiles/${profileId}/logo`, { method: "POST", body });
  const payload = await response.json().catch(() => undefined);
  if (!response.ok) throw new Error(typeof payload?.detail === "string" ? payload.detail : "Logo konnte nicht hochgeladen werden.");
  return payload as BusinessProfile;
}

export async function removeBusinessProfileLogo(profileId: number): Promise<BusinessProfile> {
  const response = await fetch(`/business-profiles/${profileId}/logo`, { method: "DELETE" });
  const payload = await response.json().catch(() => undefined);
  if (!response.ok) throw new Error(typeof payload?.detail === "string" ? payload.detail : "Logo konnte nicht entfernt werden.");
  return payload as BusinessProfile;
}
