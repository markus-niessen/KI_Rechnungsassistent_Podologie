import { useEffect, useState } from "react";

import { DashboardCustomizationPanel } from "../dashboard/DashboardCustomizationPanel";
import { DashboardWidget } from "../dashboard/DashboardWidget";
import { getDashboardData, type DashboardData } from "../dashboard/dashboardData";
import {
  loadDashboardLayout,
  resetDashboardLayout,
  saveDashboardLayout,
  type DashboardLayout,
} from "../dashboard/dashboardLayout";
import { dashboardWidgets, type DashboardWidgetId } from "../dashboard/dashboardWidgets";
import "./DashboardPage.css";

type DashboardState =
  | { data: DashboardData; error: null; loading: false }
  | { data: null; error: null; loading: true }
  | { data: null; error: true; loading: false };

const initialState: DashboardState = { data: null, error: null, loading: true };

export function DashboardPage() {
  const [state, setState] = useState<DashboardState>(initialState);
  const [requestVersion, setRequestVersion] = useState(0);
  const [layout, setLayout] = useState<DashboardLayout>(loadDashboardLayout);
  const [isCustomizationOpen, setIsCustomizationOpen] = useState(false);

  useEffect(() => {
    let isMounted = true;
    setState(initialState);

    void getDashboardData().then(
      (data) => {
        if (isMounted) {
          setState({ data, error: null, loading: false });
        }
      },
      () => {
        if (isMounted) {
          setState({ data: null, error: true, loading: false });
        }
      },
    );

    return () => {
      isMounted = false;
    };
  }, [requestVersion]);

  if (state.loading) {
    return (
      <section aria-live="polite" className="dashboard-page__loading" role="status">
        Dashboard-Daten werden geladen …
      </section>
    );
  }

  if (state.error) {
    return (
      <section className="dashboard-page__error">
        <h2>Dashboard-Daten konnten nicht geladen werden.</h2>
        <p>Bitte versuchen Sie es erneut.</p>
        <button className="dashboard-page__retry" onClick={() => setRequestVersion((version) => version + 1)} type="button">
          Wiederholen
        </button>
      </section>
    );
  }

  const { data } = state;
  const visibleWidgetIds = layout.order.filter((widgetId) => layout.visibility[widgetId]);

  const updateLayout = (nextLayout: DashboardLayout) => {
    setLayout(nextLayout);
    saveDashboardLayout(nextLayout);
  };

  const toggleWidgetVisibility = (widgetId: DashboardWidgetId) => {
    if (layout.visibility[widgetId] && visibleWidgetIds.length === 1) {
      return;
    }

    updateLayout({
      ...layout,
      visibility: {
        ...layout.visibility,
        [widgetId]: !layout.visibility[widgetId],
      },
    });
  };

  const moveWidget = (widgetId: DashboardWidgetId, direction: "up" | "down") => {
    const currentIndex = layout.order.indexOf(widgetId);
    const targetIndex = direction === "up" ? currentIndex - 1 : currentIndex + 1;
    if (currentIndex < 0 || targetIndex < 0 || targetIndex >= layout.order.length) {
      return;
    }

    const order = [...layout.order];
    [order[currentIndex], order[targetIndex]] = [order[targetIndex], order[currentIndex]];
    updateLayout({ ...layout, order });
  };

  const restoreDefaultLayout = () => {
    updateLayout(resetDashboardLayout());
  };

  return (
    <section className="dashboard-page" aria-labelledby="dashboard-overview-title">
      <div className="dashboard-page__intro">
        <div>
          <h2 id="dashboard-overview-title">Dashboard-Übersicht</h2>
          <p>Aktueller Überblick über Patienten, Rechnungen und Mahnungen.</p>
        </div>
        <button
          aria-controls="dashboard-customization"
          aria-expanded={isCustomizationOpen}
          className="dashboard-page__customize"
          onClick={() => setIsCustomizationOpen((isOpen) => !isOpen)}
          type="button"
        >
          Dashboard anpassen
        </button>
      </div>
      {isCustomizationOpen ? (
        <div id="dashboard-customization">
          <DashboardCustomizationPanel
            layout={layout}
            onClose={() => setIsCustomizationOpen(false)}
            onMove={moveWidget}
            onReset={restoreDefaultLayout}
            onVisibilityChange={toggleWidgetVisibility}
          />
        </div>
      ) : null}
      <div className="dashboard-page__grid">
        {visibleWidgetIds.map((widgetId) => {
          const widget = dashboardWidgets.find((item) => item.id === widgetId);
          return widget === undefined ? null : (
            <DashboardWidget
              description={widget.description}
              key={widget.id}
              status={widget.status}
              statusLabel={widget.statusLabel}
              title={widget.title}
              value={widget.value(data)}
            />
          );
        })}
      </div>
    </section>
  );
}
