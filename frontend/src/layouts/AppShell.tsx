import { useEffect, useRef, useState, type ReactNode } from "react";

import { Header } from "../components/header/Header";
import { Sidebar } from "../components/navigation/Sidebar";
import "./AppShell.css";

type AppShellProps = {
  children: ReactNode;
  pageTitle: string;
};

export function AppShell({ children, pageTitle }: AppShellProps) {
  const [isNavigationOpen, setIsNavigationOpen] = useState(false);
  const menuButtonRef = useRef<HTMLButtonElement>(null);
  const sidebarRef = useRef<HTMLElement>(null);

  const closeNavigation = (restoreFocus = true) => {
    setIsNavigationOpen(false);

    if (restoreFocus) {
      requestAnimationFrame(() => menuButtonRef.current?.focus());
    }
  };

  useEffect(() => {
    if (!isNavigationOpen) {
      return;
    }

    sidebarRef.current?.focus();

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        closeNavigation();
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [isNavigationOpen]);

  return (
    <div className="app-shell">
      <Sidebar
        isOpen={isNavigationOpen}
        onNavigate={() => closeNavigation(false)}
        sidebarRef={sidebarRef}
      />
      {isNavigationOpen ? (
        <button
          aria-label="Navigation durch Klick außerhalb schließen"
          className="app-shell__overlay"
          onClick={() => closeNavigation()}
          type="button"
        />
      ) : null}
      <div className="app-shell__content">
        <Header
          isNavigationOpen={isNavigationOpen}
          menuButtonRef={menuButtonRef}
          onNavigationToggle={() => setIsNavigationOpen((isOpen) => !isOpen)}
          title={pageTitle}
        />
        <main className="app-shell__main">{children}</main>
      </div>
    </div>
  );
}
