import { apiGet, apiRequest } from "./client";
import type { Service, ServiceInput, ServiceType } from "./types";

export type GetServicesParameters = {
  includeInactive?: boolean;
  search?: string;
  serviceType?: ServiceType;
};

export async function getServices(parameters: GetServicesParameters = {}): Promise<Service[]> {
  return (
    (await apiGet<Service[]>("/services", {
      include_inactive: parameters.includeInactive,
      search: parameters.search,
      service_type: parameters.serviceType,
    })) ?? []
  );
}

export async function getService(serviceId: number): Promise<Service> {
  return (await apiGet<Service>(`/services/${serviceId}`)) as Service;
}

export async function createService(service: ServiceInput): Promise<Service> {
  return (await apiRequest<Service>("/services", { body: service, method: "POST" })) as Service;
}

export async function updateService(serviceId: number, service: ServiceInput): Promise<Service> {
  return (await apiRequest<Service>(`/services/${serviceId}`, { body: service, method: "PATCH" })) as Service;
}

export async function activateService(serviceId: number): Promise<Service> {
  return (await apiRequest<Service>(`/services/${serviceId}/activate`, { method: "POST" })) as Service;
}

export async function deactivateService(serviceId: number): Promise<Service> {
  return (await apiRequest<Service>(`/services/${serviceId}/deactivate`, { method: "POST" })) as Service;
}
