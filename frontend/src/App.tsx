import { type ThemeMode, ThemeProvider, useTheme } from "./theme/ThemeProvider";

const themeOptions: Array<{ value: ThemeMode; label: string }> = [
  { value: "light", label: "Hell" },
  { value: "dark", label: "Dunkel" },
  { value: "system", label: "System" },
];

function AppContent() {
  const { mode, setMode } = useTheme();

  return (
    <main>
      <h1>KI-Rechnungsassistent für Podologie</h1>
      <p>Frontend-Grundgerüst bereit.</p>
      <label>
        Darstellung
        <select aria-label="Darstellung" value={mode} onChange={(event) => setMode(event.target.value as ThemeMode)}>
          {themeOptions.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </label>
    </main>
  );
}

export function App() {
  return (
    <ThemeProvider>
      <AppContent />
    </ThemeProvider>
  );
}
