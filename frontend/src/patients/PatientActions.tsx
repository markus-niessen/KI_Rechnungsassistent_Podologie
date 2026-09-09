import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";

import type { Patient } from "../api/types";

type PatientActionsProps = {
  onStatusChange: (patient: Patient) => void;
  patient: Patient;
  pending?: boolean;
  showNavigationActions?: boolean;
};

export function PatientActions({ onStatusChange, patient, pending = false, showNavigationActions = true }: PatientActionsProps) {
  const [isOpen, setIsOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!isOpen) return;

    const closeOnOutsideClick = (event: MouseEvent) => {
      if (!menuRef.current?.contains(event.target as Node)) setIsOpen(false);
    };
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setIsOpen(false);
    };
    document.addEventListener("mousedown", closeOnOutsideClick);
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("mousedown", closeOnOutsideClick);
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, [isOpen]);

  const closeMenu = () => setIsOpen(false);

  return (
    <div className="patient-actions" ref={menuRef}>
      {showNavigationActions ? <Link aria-label={`${patient.first_name} ${patient.last_name} öffnen`} className="patient-action-button" to={`/patients/${patient.id}`}>Öffnen</Link> : null}
      {showNavigationActions ? <Link aria-label={`${patient.first_name} ${patient.last_name} bearbeiten`} className="patient-action-button" to={`/patients/${patient.id}/edit`}>Bearbeiten</Link> : null}
      <button aria-expanded={isOpen} aria-haspopup="menu" aria-label={`Weitere Aktionen für ${patient.first_name} ${patient.last_name}`} className="patient-action-button patient-action-button--icon" onClick={() => setIsOpen((open) => !open)} type="button">•••</button>
      {isOpen ? (
        <div aria-label={`Aktionen für ${patient.first_name} ${patient.last_name}`} className="patient-action-menu" role="menu">
          {showNavigationActions ? <Link onClick={closeMenu} role="menuitem" to={`/patients/${patient.id}`}>Patient öffnen</Link> : null}
          {showNavigationActions ? <Link onClick={closeMenu} role="menuitem" to={`/patients/${patient.id}/edit`}>Patient bearbeiten</Link> : null}
          {!patient.deceased ? <button disabled={pending} onClick={() => { closeMenu(); onStatusChange(patient); }} role="menuitem" type="button">{patient.active ? "Deaktivieren" : "Aktivieren"}</button> : null}
          {patient.deceased && !showNavigationActions ? <span className="patient-action-menu__empty">Keine weiteren Aktionen verfügbar</span> : null}
        </div>
      ) : null}
    </div>
  );
}
