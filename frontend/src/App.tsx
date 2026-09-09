import { AppShell } from "./layouts/AppShell";
import { ThemeProvider } from "./theme/ThemeProvider";

export function App() {
  return (
    <ThemeProvider>
      <AppShell activeItemId="dashboard" pageTitle="Dashboard">
        <section className="dashboard-placeholder">
          <h2>Dashboard wird vorbereitet</h2>
          <p>Die gemeinsame Anwendungshülle ist bereit. Dashboard-Daten und Widgets folgen in einem separaten Schritt.</p>
        </section>
      </AppShell>
    </ThemeProvider>
  );
}
