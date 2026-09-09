import type { PatientKpiId, PatientKpiLayout } from "./patientKpiLayout";
import { patientKpis } from "./patientKpiLayout";

type PatientKpiCustomizationProps = {
  layout: PatientKpiLayout;
  onMove: (widgetId: PatientKpiId, direction: -1 | 1) => void;
  onReset: () => void;
  onVisibilityChange: (widgetId: PatientKpiId) => void;
};

export function PatientKpiCustomization({ layout, onMove, onReset, onVisibilityChange }: PatientKpiCustomizationProps) {
  return (
    <section aria-label="KPI-Widgets anpassen" className="patient-kpi-customization">
      <div><h3>Widgets anpassen</h3><p>Widgets einblenden und ihre Reihenfolge festlegen.</p></div>
      <div className="patient-kpi-customization__list">
        {layout.order.map((widgetId, index) => {
          const widget = patientKpis.find((item) => item.id === widgetId);
          if (!widget) return null;
          return <div className="patient-kpi-customization__item" key={widgetId}><label><input checked={layout.visibility[widgetId]} onChange={() => onVisibilityChange(widgetId)} type="checkbox" />{widget.label}</label><span><button aria-label={`${widget.label} nach vorne verschieben`} disabled={index === 0} onClick={() => onMove(widgetId, -1)} type="button">↑</button><button aria-label={`${widget.label} nach hinten verschieben`} disabled={index === layout.order.length - 1} onClick={() => onMove(widgetId, 1)} type="button">↓</button></span></div>;
        })}
      </div>
      <button className="patient-action-button" onClick={onReset} type="button">Standard wiederherstellen</button>
    </section>
  );
}
