import type { RefObject } from "react";
import { NavLink, useLocation } from "react-router-dom";

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
  path: string;
};

const navigationItems: NavigationItem[] = [
  { id: "dashboard", label: "Dashboard", path: "/dashboard" },
  { id: "patients", label: "Patienten", path: "/patients" },
  { id: "invoices", label: "Rechnungen", path: "/invoices" },
  { id: "payments", label: "Zahlungen", path: "/payments" },
  { id: "reminders", label: "Mahnwesen", path: "/reminders" },
  { id: "services", label: "Leistungen / Produkte", path: "/services" },
  { id: "business-profiles", label: "Betriebe / Standorte", path: "/business-profiles" },
  { id: "settings", label: "Einstellungen", path: "/settings" },
];

type SidebarProps = {
  isOpen: boolean;
  onNavigate: () => void;
  sidebarRef: RefObject<HTMLElement | null>;
};

export function Sidebar({ isOpen, onNavigate, sidebarRef }: SidebarProps) {
  const { pathname } = useLocation();

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
          const isDashboardAtRoot = item.id === "dashboard" && pathname === "/";
          return (
            <NavLink
              className={({ isActive }) =>
                isActive || isDashboardAtRoot ? "app-sidebar__link app-sidebar__link--active" : "app-sidebar__link"
              }
              end
              key={item.id}
              onClick={onNavigate}
              to={item.path}
            >
              {item.label}
            </NavLink>
          );
        })}
      </nav>
    </aside>
  );
}
