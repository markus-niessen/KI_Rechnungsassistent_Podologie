import { type FormEvent, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { createPatient, getPatient, updatePatient } from "../api/patients";
import type { PatientInput } from "../api/types";
import { emptyPatientInput, normalizePatientInput, patientToInput } from "../patients/patientHelpers";
import { PatientConfirmationDialog } from "../patients/PatientConfirmationDialog";
import "./PatientPages.css";

export function PatientFormPage({ mode }: { mode: "create" | "edit" }) {
  const { patientId } = useParams();
  const navigate = useNavigate();
  const [input, setInput] = useState<PatientInput>(emptyPatientInput);
  const [patientNr, setPatientNr] = useState<string | null>(null);
  const [loadState, setLoadState] = useState(mode === "edit" ? "loading" : "ready");
  const [error, setError] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [showInvoiceAddress, setShowInvoiceAddress] = useState(false);
  const [pendingDeceasedValue, setPendingDeceasedValue] = useState<boolean | null>(null);

  useEffect(() => {
    if (mode !== "edit" || patientId === undefined) {
      return;
    }
    void getPatient(Number(patientId)).then(
      (patient) => {
        setInput(patientToInput(patient));
        setPatientNr(patient.patient_nr);
        setShowInvoiceAddress(Boolean(patient.invoice_name || patient.invoice_street || patient.invoice_zip || patient.invoice_city));
        setLoadState("ready");
      },
      () => setLoadState("error"),
    );
  }, [mode, patientId]);

  const setField = <Key extends keyof PatientInput>(field: Key, value: PatientInput[Key]) => {
    setInput((current) => ({ ...current, [field]: value }));
  };

  const confirmDeceasedChange = () => {
    if (pendingDeceasedValue === null) return;
    setInput((current) => ({ ...current, deceased: pendingDeceasedValue, death_date: pendingDeceasedValue ? current.death_date : null }));
    setPendingDeceasedValue(null);
  };

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const normalized = normalizePatientInput(input);
    if (!normalized.first_name || !normalized.last_name) {
      setError("Vorname und Nachname sind erforderlich.");
      return;
    }
    if (normalized.death_date && normalized.birth_date && normalized.death_date < normalized.birth_date) {
      setError("Das Sterbedatum darf nicht vor dem Geburtsdatum liegen.");
      return;
    }

    setError(null);
    setIsSaving(true);
    try {
      const patient = mode === "create"
        ? await createPatient(normalized)
        : await updatePatient(Number(patientId), normalized);
      navigate(`/patients/${patient.id}`);
    } catch {
      setError("Patient konnte nicht gespeichert werden. Bitte prüfen Sie die Eingaben und versuchen Sie es erneut.");
    } finally {
      setIsSaving(false);
    }
  };

  if (loadState === "loading") {
    return <p className="patient-loading" role="status">Patient wird geladen …</p>;
  }
  if (loadState === "error") {
    return <section className="patient-error"><p>Der Patient wurde nicht gefunden oder existiert nicht mehr.</p><Link className="patient-button" to="/patients">Zur Patientenübersicht</Link></section>;
  }

  return (
    <section className="patient-page" aria-labelledby="patient-form-title">
      <header className="patient-form__header"><div><h2 id="patient-form-title">{mode === "create" ? "Neuer Patient" : "Patient bearbeiten"}</h2><p>{mode === "create" ? "Patientennummer wird beim Speichern automatisch vergeben." : `Patientennummer: ${patientNr ?? "–"}`}</p></div></header>
      <form className="patient-form" onSubmit={submit}>
        <fieldset className="patient-form__group"><legend>Persönliche Daten</legend><div className="patient-form__grid"><label>Patientennummer<input disabled readOnly value={mode === "create" ? "Wird automatisch vergeben" : patientNr ?? "–"} /></label><label>Vorname<input onChange={(event) => setField("first_name", event.target.value)} value={input.first_name} /></label><label>Nachname<input onChange={(event) => setField("last_name", event.target.value)} value={input.last_name} /></label><label>Geburtsdatum<input onChange={(event) => setField("birth_date", event.target.value || null)} type="date" value={input.birth_date ?? ""} /></label></div></fieldset>
        <fieldset className="patient-form__group"><legend>Wohnadresse</legend><div className="patient-form__grid patient-form__grid--address"><label>Straße / Hausnummer<input onChange={(event) => setField("street", event.target.value || null)} value={input.street ?? ""} /></label><label>PLZ<input onChange={(event) => setField("zip", event.target.value || null)} value={input.zip ?? ""} /></label><label>Ort<input onChange={(event) => setField("city", event.target.value || null)} value={input.city ?? ""} /></label></div></fieldset>
        <fieldset className="patient-form__group"><legend>Heim / Einrichtung</legend><div className="patient-form__grid patient-form__grid--home"><label className="patient-form__field--wide">Heim / Einrichtung<input onChange={(event) => setField("home_name", event.target.value || null)} value={input.home_name ?? ""} /></label><label>Zimmer<input onChange={(event) => setField("room", event.target.value || null)} value={input.room ?? ""} /></label></div></fieldset>
        <fieldset className="patient-form__group"><legend>Abweichende Rechnungsanschrift</legend><label className="patient-form__checkbox"><input checked={showInvoiceAddress} onChange={(event) => {
          setShowInvoiceAddress(event.target.checked);
          if (!event.target.checked) {
            setInput((current) => ({ ...current, invoice_name: null, invoice_street: null, invoice_zip: null, invoice_city: null }));
          }
        }} type="checkbox" />Abweichende Rechnungsanschrift verwenden</label>{showInvoiceAddress ? <div className="patient-form__grid patient-form__grid--invoice"><label className="patient-form__field--wide">Rechnungsempfänger<input onChange={(event) => setField("invoice_name", event.target.value || null)} value={input.invoice_name ?? ""} /></label><label>Straße / Hausnummer<input onChange={(event) => setField("invoice_street", event.target.value || null)} value={input.invoice_street ?? ""} /></label><label>PLZ<input onChange={(event) => setField("invoice_zip", event.target.value || null)} value={input.invoice_zip ?? ""} /></label><label>Ort<input onChange={(event) => setField("invoice_city", event.target.value || null)} value={input.invoice_city ?? ""} /></label></div> : null}</fieldset>
        <fieldset className="patient-form__group"><legend>Status</legend><div className="patient-form__status-row"><p className="patient-form__status-note">Der Aktivstatus wird über die Patientenansicht verwaltet.</p><label className="patient-form__checkbox"><input checked={input.deceased} onChange={(event) => setPendingDeceasedValue(event.target.checked)} type="checkbox" />Verstorben</label>{input.deceased ? <label>Sterbedatum<input onChange={(event) => setField("death_date", event.target.value || null)} type="date" value={input.death_date ?? ""} /></label> : null}</div></fieldset>
        {error ? <p className="patient-form__error" role="alert">{error}</p> : null}
        <div className="patient-form__actions"><Link className="patient-action-link" to={mode === "edit" ? `/patients/${patientId}` : "/patients"}>Abbrechen</Link><button className="patient-button patient-button--primary" disabled={isSaving} type="submit">{isSaving ? "Wird gespeichert …" : mode === "create" ? "Patient speichern" : "Änderungen speichern"}</button></div>
      </form>
      {pendingDeceasedValue !== null ? <PatientConfirmationDialog confirmLabel={pendingDeceasedValue ? "Als verstorben markieren" : "Kennzeichnung aufheben"} description={pendingDeceasedValue ? undefined : "Diese Änderung sollte nur vorgenommen werden, wenn der Status versehentlich gesetzt wurde."} onCancel={() => setPendingDeceasedValue(null)} onConfirm={confirmDeceasedChange} title={pendingDeceasedValue ? "Patient als verstorben markieren?" : "Kennzeichnung ‚Verstorben‘ aufheben?"} /> : null}
    </section>
  );
}
