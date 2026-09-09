import { useEffect } from "react";

import type { DashboardLayout } from "./dashboardLayout";
import { dashboardWidgets, type DashboardWidgetId } from "./dashboardWidgets";

type DashboardCustomizationPanelProps = {
  layout: DashboardLayout;
  onClose: () => void;
  onMove: (widgetId: DashboardWidgetId, direction: "up" | "down") => void;
  onReset: () => void;
  onVisibilityChange: (widgetId: DashboardWidgetId) => void;
};

export function DashboardCustomizationPanel({
  layout,
  onClose,
  onMove,
  onReset,
  onVisibilityChange,
}: DashboardCustomizationPanelProps) {
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  const visibleWidgets = Object.values(layout.visibility).filter(Boolean).length;

  return (
    <section aria-labelledby="dashboard-customization-title" className="dashboard-customization" role="dialog">
      <div className="dashboard-customization__header">
        <div>
          <h2 id="dashboard-customization-title">Dashboard anpassen</h2>
          <p>Widgets einblenden und in eine passende Reihenfolge bringen.</p>
        </div>
        <button aria-label="Dashboard-Anpassung schließen" className="dashboard-customization__close" onClick={onClose} type="button">
          Schließen
        </button>
      </div>
      <ul className="dashboard-customization__list">
        {layout.order.map((widgetId, index) => {
          const widget = dashboardWidgets.find((item) => item.id === widgetId);
          if (widget === undefined) {
            return null;
          }
          const isVisible = layout.visibility[widget.id];
          const visibilityCannotChange = isVisible && visibleWidgets === 1;

          return (
            <li className="dashboard-customization__item" key={widget.id}>
              <label>
                <input
                  checked={isVisible}
                  disabled={visibilityCannotChange}
                  onChange={() => onVisibilityChange(widget.id)}
                  type="checkbox"
                />
                <span>{widget.title}</span>
              </label>
              <div className="dashboard-customization__actions">
                <button aria-label={`${widget.title} nach oben`} disabled={index === 0} onClick={() => onMove(widget.id, "up")} type="button">
                  Nach oben
                </button>
                <button
                  aria-label={`${widget.title} nach unten`}
                  disabled={index === layout.order.length - 1}
                  onClick={() => onMove(widget.id, "down")}
                  type="button"
                >
                  Nach unten
                </button>
              </div>
            </li>
          );
        })}
      </ul>
      <div className="dashboard-customization__footer">
        <button className="dashboard-customization__reset" onClick={onReset} type="button">
          Standard wiederherstellen
        </button>
      </div>
    </section>
  );
}
