export type IsoDate = string;
export type IsoDateTime = string;
export type Money = string;
export type ServiceType = "SERVICE" | "ADDITIONAL_SERVICE" | "PRODUCT";

export type Patient = {
  id: number;
  patient_nr: string;
  first_name: string;
  last_name: string;
  birth_date: IsoDate | null;
  deceased: boolean;
  death_date: IsoDate | null;
  street: string | null;
  zip: string | null;
  city: string | null;
  invoice_name: string | null;
  invoice_street: string | null;
  invoice_zip: string | null;
  invoice_city: string | null;
  home_name: string | null;
  room: string | null;
  active: boolean;
  created_at: IsoDateTime;
  updated_at: IsoDateTime;
};

export type PatientInput = {
  first_name: string;
  last_name: string;
  birth_date: IsoDate | null;
  deceased: boolean;
  death_date: IsoDate | null;
  street: string | null;
  zip: string | null;
  city: string | null;
  invoice_name: string | null;
  invoice_street: string | null;
  invoice_zip: string | null;
  invoice_city: string | null;
  home_name: string | null;
  room: string | null;
};

export type PatientInvoice = {
  id: number;
  invoice_number: string | null;
  document_type: string;
  status: string;
  invoice_date: IsoDate;
  due_date: IsoDate;
  subtotal: Money;
  tax_total: Money;
  total: Money;
  item_count: number;
  pdf_available: boolean;
};

export type Invoice = {
  id: number;
  company_id: number;
  patient_id: number | null;
  document_type: "INVOICE" | "COLLECTIVE_INVOICE" | "RECEIPT";
  status: string;
  invoice_number: string | null;
  invoice_date: IsoDate;
  due_date: IsoDate;
  subtotal: Money;
  tax_total: Money;
  total: Money;
  source_text: string | null;
  ai_review_comment: string | null;
  patient_resolution_required: boolean;
  ready_for_finalization: boolean;
  paid_amount: Money;
  remaining_amount: Money;
  payment_status: "OPEN" | "PARTIALLY_PAID" | "PAID";
  created_at: IsoDateTime;
  item_count: number;
};

export type Reminder = {
  id: number;
  invoice_id: number;
  sequence: number;
  type: "PAYMENT_REMINDER" | "REMINDER";
  open_amount: Money;
  reminder_fee: Money;
  postage_fee: Money;
  status: "DRAFT" | "ISSUED" | "PAID" | "CANCELLED";
  issued_at: IsoDateTime | null;
  snoozed_until: IsoDate | null;
  reminder_fee_waived: boolean;
  postage_fee_waived: boolean;
  created_at: IsoDateTime;
  updated_at: IsoDateTime;
  total_due: Money;
};

export type Service = {
  id: number;
  name: string;
  service_type: ServiceType;
  description: string | null;
  net_price: Money;
  vat_rate: Money;
  active: boolean;
  created_at: IsoDateTime;
};

export type ServiceInput = {
  name: string;
  service_type: ServiceType;
  description: string | null;
  net_price: Money;
  vat_rate: Money;
};

export type BusinessProfile = {
  id: number;
  business_name: string;
  location_name: string;
  location_code: string | null;
  invoice_prefix: string;
  street: string;
  postal_code: string;
  city: string;
  phone: string | null;
  email: string | null;
  tax_number: string | null;
  vat_id: string | null;
  ik_number: string | null;
  iban: string;
  bic: string | null;
  bank_name: string | null;
  logo_path: string | null;
  active: boolean;
  created_at: IsoDateTime;
  updated_at: IsoDateTime;
};

export type BusinessProfileInput = {
  business_name: string;
  location_name: string;
  location_code: string | null;
  street: string;
  postal_code: string;
  city: string;
  phone: string | null;
  email: string | null;
  tax_number: string | null;
  vat_id: string | null;
  ik_number: string | null;
  iban: string;
  bic: string | null;
  bank_name: string | null;
  logo_path: string | null;
};
