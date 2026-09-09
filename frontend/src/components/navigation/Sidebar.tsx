import type { RefObject } from "react";

export type NavigationItemId =
  | "dashboard"
  | "patients"
  | "invoices"
  | "payments"
  | "reminders"
  | "services"
  | "business-profiles"
  | "settings";

type NavigationItem = {
  id: NavigationItemId;
  label: string;
};

const navigationItems: NavigationItem[] = [
  { id: "dashboard", label: "Dashboard" },
  { id: "patients", label: "Patienten" },
  { id: "invoices", label: "Rechnungen" },
  { id: "payments", label: "Zahlungen" },
  { id: "reminders", label: "Mahnwesen" },
  { id: "services", label: "Leistungen / Produkte" },
  { id: "business-profiles", label: "Betriebe / Standorte" },
  { id: "settings", label: "Einstellungen" },
];

type SidebarProps = {
  activeItemId: NavigationItemId;
  isOpen: boolean;
  onNavigate: () => void;
  sidebarRef: RefObject<HTMLElement | null>;
};

export function Sidebar({ activeItemId, isOpen, onNavigate, sidebarRef }: SidebarProps) {
  return (
    <aside
      aria-label="Hauptnavigation"
      className={isOpen ? "app-sidebar app-sidebar--open" : "app-sidebar"}
      id="primary-navigation-drawer"
      ref={sidebarRef}
      tabIndex={-1}
    >
      <div className="app-sidebar__brand">
        <span aria-hidden="true" className="app-sidebar__brand-mark">
          KI
        </span>
        <div>
          <strong>KI-Rechnungsassistent</strong>
          <span>Podologie</span>
        </div>
      </div>

      <nav aria-label="Hauptnavigation" className="app-sidebar__navigation">
        {navigationItems.map((item) => {
          const isActive = item.id === activeItemId;
          return (
            <a
              aria-current={isActive ? "page" : undefined}
              className={isActive ? "app-sidebar__link app-sidebar__link--active" : "app-sidebar__link"}
              href={`#${item.id}`}
              key={item.id}
              onClick={onNavigate}
            >
              {item.label}
            </a>
          );
        })}
      </nav>
    </aside>
  );
}
