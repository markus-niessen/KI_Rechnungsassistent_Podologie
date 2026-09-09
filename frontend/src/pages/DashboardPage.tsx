import { useEffect, useState } from "react";

import { DashboardWidget } from "../dashboard/DashboardWidget";
import { getDashboardData, type DashboardData } from "../dashboard/dashboardData";
import "./DashboardPage.css";

type DashboardState =
  | { data: DashboardData; error: null; loading: false }
  | { data: null; error: null; loading: true }
  | { data: null; error: true; loading: false };

const initialState: DashboardState = { data: null, error: null, loading: true };

export function DashboardPage() {
  const [state, setState] = useState<DashboardState>(initialState);
  const [requestVersion, setRequestVersion] = useState(0);

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

  return (
    <section className="dashboard-page" aria-labelledby="dashboard-overview-title">
      <div className="dashboard-page__intro">
        <h2 id="dashboard-overview-title">Dashboard-Übersicht</h2>
        <p>Aktueller Überblick über Patienten, Rechnungen und Mahnungen.</p>
      </div>
      <div className="dashboard-page__grid">
        <DashboardWidget description="Aktuell aktive Patienten" status="info" statusLabel="Aktuell" title="Aktive Patienten" value={data.activePatients} />
        <DashboardWidget description="Noch nicht vollständig bezahlt" status="info" statusLabel="Offen" title="Offene Rechnungen" value={data.openInvoices} />
        <DashboardWidget description="Fälligkeit bereits überschritten" status="danger" statusLabel="Überfällig" title="Überfällige Rechnungen" value={data.overdueInvoices} />
        <DashboardWidget description="Noch nicht finalisierte Rechnungen" status="info" statusLabel="Entwurf" title="Rechnungsentwürfe" value={data.draftInvoices} />
        <DashboardWidget description="Entwurf oder bereits versendet" status="warning" statusLabel="Offen" title="Offene Mahnungen" value={data.openReminders} />
        <DashboardWidget description="Entwurf benötigt weitere Prüfung" status="warning" statusLabel="Prüfung" title="KI-Prüfung erforderlich" value={data.aiReviewRequired} />
      </div>
    </section>
  );
}
