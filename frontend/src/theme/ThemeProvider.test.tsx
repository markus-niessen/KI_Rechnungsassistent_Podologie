import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "../App";
import { THEME_STORAGE_KEY } from "./ThemeProvider";

function setSystemTheme(isDark: boolean) {
  Object.defineProperty(window, "matchMedia", {
    configurable: true,
    value: vi.fn().mockImplementation(() => ({
      matches: isDark,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })),
  });
}

describe("ThemeProvider", () => {
  beforeEach(() => {
    setSystemTheme(false);
  });

  it("applies and persists a selected dark theme", () => {
    render(<App />);

    fireEvent.change(screen.getByLabelText("Darstellung"), { target: { value: "dark" } });

    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBe("dark");
  });

  it("restores the stored theme on startup", () => {
    window.localStorage.setItem(THEME_STORAGE_KEY, "light");

    render(<App />);

    expect(screen.getByLabelText("Darstellung")).toHaveValue("light");
    expect(document.documentElement.dataset.theme).toBe("light");
  });

  it("uses the system preference when system mode is selected", () => {
    setSystemTheme(true);
    window.localStorage.setItem(THEME_STORAGE_KEY, "system");

    render(<App />);

    expect(screen.getByLabelText("Darstellung")).toHaveValue("system");
    expect(document.documentElement.dataset.theme).toBe("dark");
  });
});
