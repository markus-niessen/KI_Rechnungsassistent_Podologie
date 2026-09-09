import { useEffect, useRef } from "react";

type PatientConfirmationDialogProps = {
  confirmLabel: string;
  description?: string;
  onCancel: () => void;
  onConfirm: () => void;
  title: string;
};

export function PatientConfirmationDialog({ confirmLabel, description, onCancel, onConfirm, title }: PatientConfirmationDialogProps) {
  const cancelButtonRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    cancelButtonRef.current?.focus();
    const onEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") onCancel();
    };
    document.addEventListener("keydown", onEscape);
    return () => document.removeEventListener("keydown", onEscape);
  }, [onCancel]);

  return (
    <div className="patient-dialog-backdrop" onMouseDown={onCancel} role="presentation">
      <section aria-describedby={description ? "patient-dialog-description" : undefined} aria-labelledby="patient-dialog-title" className="patient-dialog" onMouseDown={(event) => event.stopPropagation()} role="dialog" aria-modal="true">
        <h2 id="patient-dialog-title">{title}</h2>
        {description ? <p id="patient-dialog-description">{description}</p> : null}
        <div className="patient-dialog__actions"><button className="patient-action-link" onClick={onCancel} ref={cancelButtonRef} type="button">Abbrechen</button><button className="patient-button patient-button--primary" onClick={onConfirm} type="button">{confirmLabel}</button></div>
      </section>
    </div>
  );
}
