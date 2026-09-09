import { createContext, type ReactNode, useContext, useEffect, useMemo, useState } from "react";

export type ThemeMode = "light" | "dark" | "system";
type ResolvedTheme = Exclude<ThemeMode, "system">;

const THEME_STORAGE_KEY = "ki-rechnungsassistent.theme";

type ThemeContextValue = {
  mode: ThemeMode;
  resolvedTheme: ResolvedTheme;
  setMode: (mode: ThemeMode) => void;
};

const ThemeContext = createContext<ThemeContextValue | undefined>(undefined);

function systemTheme(): ResolvedTheme {
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function initialThemeMode(): ThemeMode {
  const storedMode = window.localStorage.getItem(THEME_STORAGE_KEY);
  return storedMode === "light" || storedMode === "dark" || storedMode === "system" ? storedMode : "system";
}

function applyTheme(mode: ThemeMode): ResolvedTheme {
  const resolvedTheme = mode === "system" ? systemTheme() : mode;
  document.documentElement.dataset.theme = resolvedTheme;
  document.documentElement.style.colorScheme = resolvedTheme;
  return resolvedTheme;
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [mode, setMode] = useState<ThemeMode>(initialThemeMode);
  const [resolvedTheme, setResolvedTheme] = useState<ResolvedTheme>(() => applyTheme(initialThemeMode()));

  useEffect(() => {
    window.localStorage.setItem(THEME_STORAGE_KEY, mode);
    setResolvedTheme(applyTheme(mode));

    if (mode !== "system") {
      return undefined;
    }

    const mediaQuery = window.matchMedia?.("(prefers-color-scheme: dark)");
    if (!mediaQuery) {
      return undefined;
    }

    const updateSystemTheme = () => setResolvedTheme(applyTheme("system"));
    mediaQuery.addEventListener("change", updateSystemTheme);
    return () => mediaQuery.removeEventListener("change", updateSystemTheme);
  }, [mode]);

  const value = useMemo(() => ({ mode, resolvedTheme, setMode }), [mode, resolvedTheme]);
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeContextValue {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error("useTheme must be used within ThemeProvider");
  }
  return context;
}

export { THEME_STORAGE_KEY };
