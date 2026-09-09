import { type ThemeMode, useTheme } from "../../theme/ThemeProvider";

const themeOptions: Array<{ value: ThemeMode; label: string }> = [
  { value: "light", label: "Hell" },
  { value: "dark", label: "Dunkel" },
  { value: "system", label: "System" },
];

export function ThemeToggle() {
  const { mode, setMode } = useTheme();

  return (
    <label className="theme-toggle">
      <span>Darstellung</span>
      <select aria-label="Darstellung" value={mode} onChange={(event) => setMode(event.target.value as ThemeMode)}>
        {themeOptions.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
  );
}
