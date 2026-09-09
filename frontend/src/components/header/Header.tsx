import type { ReactNode, RefObject } from "react";

import { ThemeToggle } from "./ThemeToggle";

type HeaderProps = {
  title: string;
  actions?: ReactNode;
  isNavigationOpen: boolean;
  menuButtonRef: RefObject<HTMLButtonElement | null>;
  onNavigationToggle: () => void;
};

export function Header({ title, actions, isNavigationOpen, menuButtonRef, onNavigationToggle }: HeaderProps) {
  return (
    <header className="app-header">
      <button
        aria-controls="primary-navigation-drawer"
        aria-expanded={isNavigationOpen}
        aria-label={isNavigationOpen ? "Navigation schließen" : "Navigation öffnen"}
        className="app-header__menu-button"
        onClick={onNavigationToggle}
        ref={menuButtonRef}
        type="button"
      >
        <span aria-hidden="true">☰</span>
      </button>
      <div>
        <p className="app-header__eyebrow">KI-Rechnungsassistent</p>
        <h1>{title}</h1>
      </div>
      <div className="app-header__actions">
        {actions}
        <ThemeToggle />
      </div>
    </header>
  );
}
