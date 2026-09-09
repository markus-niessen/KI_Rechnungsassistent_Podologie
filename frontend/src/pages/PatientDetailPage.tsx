import { type DragEvent, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { activatePatient, deactivatePatient, getPatient, getPatientInvoices } from "../api/patients";
import { getReminders } from "../api/reminders";
import type { Patient, PatientInvoice, Reminder } from "../api/types";
import { PatientActions } from "../patients/PatientActions";
import { PatientConfirmationDialog } from "../patients/PatientConfirmationDialog";
import { patientAddress, patientStatus } from "../patients/patientHelpers";
import { PatientKpiCustomization } from "../patients/PatientKpiCustomization";
import {
  createDefaultPatientKpiLayout,
  loadPatientKpiLayout,
  patientKpis,
  savePatientKpiLayout,
  type PatientKpiId,
  type PatientKpiLayout,
} from "../patients/patientKpiLayout";
import "./PatientPages.css";

type DetailTab = "documentation" | "invoices" | "overview" | "payments" | "reminders";

export function PatientDetailPage() {
  const { patientId } = useParams();
  const [patient, setPatient] = useState<Patient | null>(null);
  const [invoices, setInvoices] = useState<PatientInvoice[]>([]);
  const [reminders, setReminders] = useState<Reminder[]>([]);
  const [state, setState] = useState<"error" | "loading" | "ready">("loading");
  const [tab, setTab] = useState<DetailTab>("overview");
  const [mutationError, setMutationError] = useState<string | null>(null);
  const [patientForStatusChange, setPatientForStatusChange] = useState<Patient | null>(null);

  useEffect(() => {
    const id = Number(patientId);
    if (!Number.isInteger(id)) {
      setState("error");
      return;
    }
    void Promise.all([getPatient(id), getPatientInvoices(id), getReminders()]).then(
      ([loadedPatient, loadedInvoices, loadedReminders]) => {
        setPatient(loadedPatient);
        setInvoices(loadedInvoices);
        const invoiceIds = new Set(loadedInvoices.map((invoice) => invoice.id));
        setReminders(loadedReminders.filter((reminder) => invoiceIds.has(reminder.invoice_id)));
        setState("ready");
      },
      () => setState("error"),
    );
  }, [patientId]);

  const changeStatus = async (currentPatient: Patient) => {
    setMutationError(null);
    try {
      const updated = currentPatient.active ? await deactivatePatient(currentPatient.id) : await activatePatient(currentPatient.id);
      setPatient(updated);
    } catch {
      setMutationError("Der Patientenstatus konnte nicht geändert werden.");
    }
  };

  if (state === "loading") return <p className="patient-loading" role="status">Patient wird geladen …</p>;
  if (state === "error" || patient === null) return <section className="patient-error"><p>Der Patient wurde nicht gefunden oder existiert nicht mehr.</p><Link className="patient-button" to="/patients">Zur Patientenübersicht</Link></section>;

  const tabs: Array<[DetailTab, string]> = [["overview", "Übersicht"], ["invoices", "Rechnungen"], ["payments", "Zahlungen"], ["reminders", "Mahnungen"], ["documentation", "Dokumentation"]];
  const headerDetails = [patient.birth_date, patientAddress(patient), patient.home_name, patient.room && `Zimmer ${patient.room}`].filter(Boolean).join(" · ");

  return (
    <section className="patient-page">
      <header className="patient-detail__header">
        <div>
          <h2>{patient.first_name} {patient.last_name}</h2>
          <p className="patient-detail__number">Patientennummer: {patient.patient_nr} · <span className={`patient-status patient-status--${patient.deceased ? "deceased" : patient.active ? "active" : "inactive"}`}>{patientStatus(patient)}</span></p>
          <p className="patient-detail__meta">{headerDetails || "Keine weiteren Stammdaten hinterlegt."}</p>
        </div>
        <div className="patient-detail__actions">
          <Link className="patient-action-link" to={`/patients/${patient.id}/edit`}>Patient bearbeiten</Link>
          <PatientActions onStatusChange={setPatientForStatusChange} patient={patient} showNavigationActions={false} />
        </div>
      </header>
      {mutationError ? <p className="patient-form__error" role="alert">{mutationError}</p> : null}
      <div className="patient-tabs" role="tablist">
        {tabs.map(([id, label]) => <button aria-selected={tab === id} key={id} onClick={() => setTab(id)} role="tab" type="button">{label}</button>)}
      </div>
      {tab === "overview" ? <Overview invoices={invoices} patient={patient} /> : null}
      {tab === "invoices" ? <Invoices invoices={invoices} /> : null}
      {tab === "payments" ? <UnavailableTab title="Zahlungen" text="Zahlungen können mit der aktuellen API nicht patientenbezogen ohne zusätzliche Einzelabfragen geladen werden." /> : null}
      {tab === "reminders" ? <Reminders reminders={reminders} /> : null}
      {tab === "documentation" ? <UnavailableTab title="Dokumentation" text="Für diesen Patienten sind keine Dokumentationsdaten verfügbar." /> : null}
      {patientForStatusChange ? <PatientConfirmationDialog confirmLabel={patientForStatusChange.active ? "Deaktivieren" : "Aktivieren"} onCancel={() => setPatientForStatusChange(null)} onConfirm={() => { const selectedPatient = patientForStatusChange; setPatientForStatusChange(null); void changeStatus(selectedPatient); }} title={patientForStatusChange.active ? "Patient deaktivieren?" : "Patient aktivieren?"} /> : null}
    </section>
  );
}

function Overview({ patient, invoices }: { patient: Patient; invoices: PatientInvoice[] }) {
  const [kpiLayout, setKpiLayout] = useState<PatientKpiLayout>(loadPatientKpiLayout);
  const [isCustomizationOpen, setIsCustomizationOpen] = useState(false);
  const [draggingId, setDraggingId] = useState<PatientKpiId | null>(null);
  const [dropTargetId, setDropTargetId] = useState<PatientKpiId | null>(null);

  const updateKpiLayout = (nextLayout: PatientKpiLayout) => {
    setKpiLayout(nextLayout);
    savePatientKpiLayout(nextLayout);
  };
  const moveWidget = (widgetId: PatientKpiId, direction: -1 | 1) => {
    const index = kpiLayout.order.indexOf(widgetId);
    const nextIndex = index + direction;
    if (nextIndex < 0 || nextIndex >= kpiLayout.order.length) return;
    const order = [...kpiLayout.order];
    [order[index], order[nextIndex]] = [order[nextIndex], order[index]];
    updateKpiLayout({ ...kpiLayout, order });
  };
  const moveWidgetBefore = (widgetId: PatientKpiId, targetId: PatientKpiId) => {
    if (widgetId === targetId) return;
    const order = kpiLayout.order.filter((id) => id !== widgetId);
    order.splice(order.indexOf(targetId), 0, widgetId);
    updateKpiLayout({ ...kpiLayout, order });
  };
  const handleDrop = (event: DragEvent<HTMLElement>, targetId: PatientKpiId) => {
    event.preventDefault();
    const transferId = event.dataTransfer.getData("text/plain") as PatientKpiId;
    const widgetId = transferId || draggingId;
    if (widgetId && kpiLayout.order.includes(widgetId)) moveWidgetBefore(widgetId, targetId);
    setDraggingId(null);
    setDropTargetId(null);
  };
  const visibleWidgetIds = kpiLayout.order.filter((widgetId) => kpiLayout.visibility[widgetId]);

  return (
    <>
      <div className="patient-kpi-toolbar"><button aria-expanded={isCustomizationOpen} className="patient-button" onClick={() => setIsCustomizationOpen((isOpen) => !isOpen)} type="button">Widgets anpassen</button></div>
      {isCustomizationOpen ? <PatientKpiCustomization layout={kpiLayout} onMove={moveWidget} onReset={() => updateKpiLayout(createDefaultPatientKpiLayout())} onVisibilityChange={(widgetId) => updateKpiLayout({ ...kpiLayout, visibility: { ...kpiLayout.visibility, [widgetId]: !kpiLayout.visibility[widgetId] } })} /> : null}
      <section aria-label="Finanzübersicht" className="patient-kpi-grid">
        {visibleWidgetIds.map((widgetId) => {
          const widget = patientKpis.find((item) => item.id === widgetId);
          return widget ? <PatientKpi dragging={draggingId === widgetId} dropTarget={dropTargetId === widgetId && draggingId !== widgetId} key={widget.id} label={widget.label} onDragEnd={() => { setDraggingId(null); setDropTargetId(null); }} onDragOver={(event) => { event.preventDefault(); setDropTargetId(widget.id); }} onDragStart={(event) => { event.dataTransfer.effectAllowed = "move"; event.dataTransfer.setData("text/plain", widget.id); setDraggingId(widget.id); }} onDrop={(event) => handleDrop(event, widget.id)} /> : null;
        })}
      </section>
      <div className="patient-detail__content">
        <main className="patient-detail__main">
        <Invoices invoices={invoices} title="Letzte Rechnungen" />
        </main>
        <aside className="patient-detail__side">
          <section className="patient-detail__aside"><h3>Stammdaten</h3><div className="patient-detail__grid"><div><strong>Adresse</strong>{patientAddress(patient)}</div><div><strong>Heim / Zimmer</strong>{[patient.home_name, patient.room].filter(Boolean).join(" · ") || "–"}</div><div><strong>Geburtsdatum</strong>{patient.birth_date ?? "–"}</div><div><strong>Rechnungsanschrift</strong>{patient.invoice_name ? [patient.invoice_name, patient.invoice_street, [patient.invoice_zip, patient.invoice_city].filter(Boolean).join(" ")].filter(Boolean).join(", ") : "Wie Wohnadresse"}</div></div></section>
          <UnavailableTab title="Letzte Dokumentation" text="Für diesen Patienten sind keine Dokumentationsdaten verfügbar." />
        </aside>
      </div>
    </>
  );
}

function PatientKpi({ dragging, dropTarget, label, onDragEnd, onDragOver, onDragStart, onDrop }: { dragging: boolean; dropTarget: boolean; label: string; onDragEnd: () => void; onDragOver: (event: DragEvent<HTMLElement>) => void; onDragStart: (event: DragEvent<HTMLElement>) => void; onDrop: (event: DragEvent<HTMLElement>) => void }) {
  return <article aria-label={label} className={`patient-kpi${dragging ? " patient-kpi--dragging" : ""}${dropTarget ? " patient-kpi--drop-target" : ""}`} draggable onDragEnd={onDragEnd} onDragOver={onDragOver} onDragStart={onDragStart} onDrop={onDrop}><span className="patient-kpi__drag-handle" aria-hidden="true">⠿</span><span>{label}</span><strong>–</strong><small>Noch nicht verfügbar</small></article>;
}

function Invoices({ invoices, title = "Rechnungen" }: { invoices: PatientInvoice[]; title?: string }) {
  if (invoices.length === 0) return <UnavailableTab title={title} text="Für diesen Patienten liegen keine Rechnungen vor." />;
  return <section className="patient-detail__section"><h3>{title}</h3><ul className="patient-invoice-list">{invoices.slice(0, 5).map((invoice) => <li key={invoice.id}><span>{invoice.invoice_number ?? "Entwurf"}</span><span>{invoice.total} € · {invoice.status}</span></li>)}</ul></section>;
}

function Reminders({ reminders }: { reminders: Reminder[] }) {
  if (reminders.length === 0) return <UnavailableTab title="Mahnungen" text="Für diesen Patienten liegen keine Mahnungen vor." />;
  return <section className="patient-detail__section"><h3>Mahnungen</h3><ul className="patient-invoice-list">{reminders.map((reminder) => <li key={reminder.id}><span>Stufe {reminder.sequence}</span><span>{reminder.status}</span></li>)}</ul></section>;
}

function UnavailableTab({ text, title }: { text: string; title: string }) {
  return <section className="patient-detail__unavailable"><h3>{title}</h3><p>{text}</p></section>;
}
