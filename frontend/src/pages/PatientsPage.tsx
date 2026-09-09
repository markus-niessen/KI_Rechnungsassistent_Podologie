import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";

import { activatePatient, deactivatePatient, getPatients } from "../api/patients";
import type { Patient } from "../api/types";
import {
  defaultPatientColumnLayout,
  loadPatientColumnLayout,
  patientAddress,
  patientColumns,
  patientStatus,
  savePatientColumnLayout,
  type PatientColumnLayout,
  type PatientColumnId,
} from "../patients/patientHelpers";
import { PatientActions } from "../patients/PatientActions";
import { PatientConfirmationDialog } from "../patients/PatientConfirmationDialog";
import "./PatientPages.css";

type LoadState = "error" | "loading" | "ready";
type QuickFilter = "active" | "all" | "inactive";

export function PatientsPage() {
  const [patients, setPatients] = useState<Patient[]>([]);
  const [loadState, setLoadState] = useState<LoadState>("loading");
  const [search, setSearch] = useState("");
  const [quickFilter, setQuickFilter] = useState<QuickFilter>("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [cityFilter, setCityFilter] = useState("all");
  const [zipFilter, setZipFilter] = useState("all");
  const [homeFilter, setHomeFilter] = useState("all");
  const [deceasedFilter, setDeceasedFilter] = useState("all");
  const [columnLayout, setColumnLayout] = useState(loadPatientColumnLayout);
  const [isColumnsOpen, setIsColumnsOpen] = useState(false);
  const [isFiltersOpen, setIsFiltersOpen] = useState(false);
  const [pendingStatusId, setPendingStatusId] = useState<number | null>(null);
  const [mutationError, setMutationError] = useState<string | null>(null);
  const [patientForStatusChange, setPatientForStatusChange] = useState<Patient | null>(null);
  const columnsRef = useRef<HTMLDivElement>(null);

  const loadPatients = () => {
    let active = true;
    setLoadState("loading");
    void getPatients({ includeInactive: true, search: search.trim() || undefined }).then(
      (data) => {
        if (active) {
          setPatients(data);
          setLoadState("ready");
        }
      },
      () => active && setLoadState("error"),
    );
    return () => {
      active = false;
    };
  };

  useEffect(() => loadPatients(), [search]);

  useEffect(() => {
    if (!isColumnsOpen) return;
    const closeOnOutsideClick = (event: MouseEvent) => {
      if (!columnsRef.current?.contains(event.target as Node)) setIsColumnsOpen(false);
    };
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setIsColumnsOpen(false);
    };
    document.addEventListener("mousedown", closeOnOutsideClick);
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("mousedown", closeOnOutsideClick);
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, [isColumnsOpen]);

  const options = useMemo(() => ({
    cities: [...new Set(patients.map((patient) => patient.city).filter((value): value is string => Boolean(value)))],
    zips: [...new Set(patients.map((patient) => patient.zip).filter((value): value is string => Boolean(value)))],
    homes: [...new Set(patients.map((patient) => patient.home_name).filter((value): value is string => Boolean(value)))],
  }), [patients]);

  const filteredPatients = patients.filter((patient) => {
    const activeFilter = quickFilter === "active" ? "active" : quickFilter === "inactive" ? "inactive" : statusFilter;
    return (
      (activeFilter === "all" || (activeFilter === "active" ? patient.active : !patient.active)) &&
      (cityFilter === "all" || patient.city === cityFilter) &&
      (zipFilter === "all" || patient.zip === zipFilter) &&
      (homeFilter === "all" || patient.home_name === homeFilter) &&
      (deceasedFilter === "all" || (deceasedFilter === "yes" ? patient.deceased : !patient.deceased))
    );
  });
  const quickFilterCounts = {
    active: patients.filter((patient) => patient.active && !patient.deceased).length,
    all: patients.length,
    inactive: patients.filter((patient) => !patient.active || patient.deceased).length,
  };

  const updateColumnLayout = (nextLayout: PatientColumnLayout) => {
    setColumnLayout(nextLayout);
    savePatientColumnLayout(nextLayout);
  };

  const updateColumns = (columnId: PatientColumnId) => {
    updateColumnLayout({ ...columnLayout, visibility: { ...columnLayout.visibility, [columnId]: !columnLayout.visibility[columnId] } });
  };

  const moveColumn = (columnId: PatientColumnId, direction: -1 | 1) => {
    const index = columnLayout.order.indexOf(columnId);
    const nextIndex = index + direction;
    if (nextIndex < 0 || nextIndex >= columnLayout.order.length) return;
    const order = [...columnLayout.order];
    [order[index], order[nextIndex]] = [order[nextIndex], order[index]];
    updateColumnLayout({ ...columnLayout, order });
  };

  const updateStatus = async (patient: Patient) => {
    setPendingStatusId(patient.id);
    setMutationError(null);
    try {
      const updatedPatient = patient.active ? await deactivatePatient(patient.id) : await activatePatient(patient.id);
      setPatients((current) => current.map((item) => (item.id === updatedPatient.id ? updatedPatient : item)));
    } catch {
      setMutationError("Der Patientenstatus konnte nicht geändert werden.");
    } finally {
      setPendingStatusId(null);
    }
  };

  const orderedColumns = columnLayout.order.filter((columnId) => columnLayout.visibility[columnId]);

  const resetFilters = () => {
    setQuickFilter("all");
    setStatusFilter("all");
    setCityFilter("all");
    setZipFilter("all");
    setHomeFilter("all");
    setDeceasedFilter("all");
    setSearch("");
  };

  return (
    <section className="patient-page" aria-labelledby="patients-title">
      <header className="patient-page__header">
        <div>
          <h2 id="patients-title">Patienten</h2>
          <p className="patient-page__subtitle">Stammdaten verwalten und Rechnungen je Patient einsehen.</p>
        </div>
        <Link className="patient-button patient-button--primary" to="/patients/new">+ Neuer Patient</Link>
      </header>

      <div className="patient-toolbar">
        <label className="patient-search">
          <span className="visually-hidden">Patienten suchen</span>
          <input onChange={(event) => setSearch(event.target.value)} placeholder="Name oder Patientennummer suchen" value={search} />
        </label>
        <div className="patient-toolbar__actions">
          <button aria-expanded={isFiltersOpen} aria-controls="patient-filters" className="patient-button" onClick={() => setIsFiltersOpen((open) => !open)} type="button">Filter</button>
          <div className="patient-columns-popover" ref={columnsRef}>
            <button aria-expanded={isColumnsOpen} aria-haspopup="menu" className="patient-button" onClick={() => setIsColumnsOpen((open) => !open)} type="button">Spalten</button>
            {isColumnsOpen ? (
              <div aria-label="Spalten auswählen" className="patient-columns" role="menu">
                {patientColumns.map((column) => (
                  <div className="patient-columns__item" key={column.id}>
                    <label><input checked={columnLayout.visibility[column.id]} onChange={() => updateColumns(column.id)} type="checkbox" />{column.label}</label>
                    <span className="patient-columns__order"><button aria-label={`${column.label} nach oben`} disabled={columnLayout.order.indexOf(column.id) === 0} onClick={() => moveColumn(column.id, -1)} type="button">↑</button><button aria-label={`${column.label} nach unten`} disabled={columnLayout.order.indexOf(column.id) === columnLayout.order.length - 1} onClick={() => moveColumn(column.id, 1)} type="button">↓</button></span>
                  </div>
                ))}
                <button className="patient-action-button" onClick={() => updateColumnLayout(defaultPatientColumnLayout())} type="button">Standard wiederherstellen</button>
              </div>
            ) : null}
          </div>
        </div>
      </div>

      <div className="patient-quickfilters" aria-label="Schnellfilter">
        {(["all", "active", "inactive"] as QuickFilter[]).map((filter) => (
          <button aria-pressed={quickFilter === filter} key={filter} onClick={() => setQuickFilter(filter)} type="button">
            {filter === "all" ? `Alle (${quickFilterCounts.all})` : filter === "active" ? `Aktiv (${quickFilterCounts.active})` : `Inaktiv (${quickFilterCounts.inactive})`}
          </button>
        ))}
      </div>

      {isFiltersOpen ? <div className="patient-filter-card" id="patient-filters">
        <div className="patient-filter-card__header"><h3>Filter</h3><button className="patient-action-button" onClick={resetFilters} type="button">Filter zurücksetzen</button></div>
        <div className="patient-filter-row">
        <label className="patient-filter">Status<select onChange={(event) => setStatusFilter(event.target.value)} value={statusFilter}><option value="all">Alle</option><option value="active">Aktiv</option><option value="inactive">Inaktiv</option></select></label>
        <label className="patient-filter">Ort<select onChange={(event) => setCityFilter(event.target.value)} value={cityFilter}><option value="all">Alle</option>{options.cities.map((value) => <option key={value}>{value}</option>)}</select></label>
        <label className="patient-filter">PLZ<select onChange={(event) => setZipFilter(event.target.value)} value={zipFilter}><option value="all">Alle</option>{options.zips.map((value) => <option key={value}>{value}</option>)}</select></label>
        <label className="patient-filter">Heim / Einrichtung<select onChange={(event) => setHomeFilter(event.target.value)} value={homeFilter}><option value="all">Alle</option>{options.homes.map((value) => <option key={value}>{value}</option>)}</select></label>
        <label className="patient-filter">Verstorben<select onChange={(event) => setDeceasedFilter(event.target.value)} value={deceasedFilter}><option value="all">Alle</option><option value="yes">Ja</option><option value="no">Nein</option></select></label>
        </div>
      </div> : null}
      {mutationError ? <p className="patient-form__error" role="alert">{mutationError}</p> : null}

      {loadState === "loading" ? <p className="patient-loading" role="status">Patienten werden geladen …</p> : null}
      {loadState === "error" ? <div className="patient-error"><p>Die Daten konnten momentan nicht geladen werden.</p><button className="patient-button" onClick={loadPatients} type="button">Erneut versuchen</button></div> : null}
      {loadState === "ready" && filteredPatients.length === 0 ? (
        <div className="patient-empty">
          <p>{patients.length === 0 ? "Noch keine Patienten vorhanden." : "Keine Patienten für diese Suche gefunden."}</p>
          {patients.length === 0 ? <Link className="patient-button patient-button--primary" to="/patients/new">Patient anlegen</Link> : <button className="patient-button" onClick={resetFilters} type="button">Filter zurücksetzen</button>}
        </div>
      ) : null}

      {loadState === "ready" && filteredPatients.length > 0 ? (
        <>
          <div className="patient-table-card"><div className="patient-table-wrap"><table className="patient-table"><thead><tr>{orderedColumns.map((columnId) => <th key={columnId}>{patientColumns.find((column) => column.id === columnId)?.label}</th>)}<th>Aktionen</th></tr></thead><tbody>{filteredPatients.map((patient) => <PatientRow columns={orderedColumns} key={patient.id} onStatusChange={setPatientForStatusChange} patient={patient} pending={pendingStatusId === patient.id} />)}</tbody></table></div></div>
          <div className="patient-cards">{filteredPatients.map((patient) => <PatientCard key={patient.id} onStatusChange={setPatientForStatusChange} patient={patient} pending={pendingStatusId === patient.id} />)}</div>
        </>
      ) : null}
      {patientForStatusChange ? <PatientConfirmationDialog confirmLabel={patientForStatusChange.active ? "Deaktivieren" : "Aktivieren"} onCancel={() => setPatientForStatusChange(null)} onConfirm={() => { const selectedPatient = patientForStatusChange; setPatientForStatusChange(null); void updateStatus(selectedPatient); }} title={patientForStatusChange.active ? "Patient deaktivieren?" : "Patient aktivieren?"} /> : null}
    </section>
  );
}

function StatusBadge({ patient }: { patient: Patient }) {
  const modifier = patient.deceased ? "deceased" : patient.active ? "active" : "inactive";
  return <span className={`patient-status patient-status--${modifier}`}>{patientStatus(patient)}</span>;
}

function PatientRow({ columns, onStatusChange, patient, pending }: { columns: PatientColumnId[]; onStatusChange: (patient: Patient) => void; patient: Patient; pending: boolean }) {
  return <tr>{columns.map((columnId) => <PatientCell columnId={columnId} key={columnId} patient={patient} />)}<td><PatientActions onStatusChange={onStatusChange} patient={patient} pending={pending} /></td></tr>;
}

function PatientCard({ onStatusChange, patient, pending }: { onStatusChange: (patient: Patient) => void; patient: Patient; pending: boolean }) {
  return <article className="patient-card"><div className="patient-card__heading"><div><Link className="patient-table__name" to={`/patients/${patient.id}`}>{patient.first_name} {patient.last_name}</Link><p className="patient-card__number">{patient.patient_nr}</p></div><StatusBadge patient={patient} /></div><div className="patient-card__meta"><span>{patientAddress(patient)}</span><span>{[patient.home_name, patient.room && `Zimmer ${patient.room}`].filter(Boolean).join(" · ") || "Keine Heimangabe"}</span></div><PatientActions onStatusChange={onStatusChange} patient={patient} pending={pending} /></article>;
}

function PatientCell({ columnId, patient }: { columnId: PatientColumnId; patient: Patient }) {
  if (columnId === "patientNr") return <td>{patient.patient_nr}</td>;
  if (columnId === "name") return <td><Link className="patient-table__name" to={`/patients/${patient.id}`}>{patient.first_name} {patient.last_name}</Link></td>;
  if (columnId === "address") return <td>{patientAddress(patient)}</td>;
  if (columnId === "home") return <td>{patient.home_name ?? "–"}</td>;
  if (columnId === "room") return <td>{patient.room ?? "–"}</td>;
  return <td><StatusBadge patient={patient} /></td>;
}
