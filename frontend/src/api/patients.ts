import { apiGet, apiRequest } from "./client";
import type { Patient, PatientInput, PatientInvoice } from "./types";

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

export async function getPatient(patientId: number): Promise<Patient> {
  return (await apiGet<Patient>(`/patients/${patientId}`)) as Patient;
}

export async function getPatientInvoices(patientId: number): Promise<PatientInvoice[]> {
  return (await apiGet<PatientInvoice[]>(`/patients/${patientId}/invoices`)) ?? [];
}

export async function createPatient(patient: PatientInput): Promise<Patient> {
  return (await apiRequest<Patient>("/patients", { body: patient, method: "POST" })) as Patient;
}

export async function updatePatient(patientId: number, patient: PatientInput): Promise<Patient> {
  return (await apiRequest<Patient>(`/patients/${patientId}`, { body: patient, method: "PATCH" })) as Patient;
}

export async function activatePatient(patientId: number): Promise<Patient> {
  return (await apiRequest<Patient>(`/patients/${patientId}/activate`, { method: "POST" })) as Patient;
}

export async function deactivatePatient(patientId: number): Promise<Patient> {
  return (await apiRequest<Patient>(`/patients/${patientId}/deactivate`, { method: "POST" })) as Patient;
}
