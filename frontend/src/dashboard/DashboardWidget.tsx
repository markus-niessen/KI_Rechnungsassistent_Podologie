import type { ReactNode } from "react";

import "./DashboardWidget.css";

type DashboardWidgetProps = {
  description: string;
  status: "info" | "warning" | "danger";
  statusLabel: string;
  title: string;
  value: number;
};

export function DashboardWidget({ description, status, statusLabel, title, value }: DashboardWidgetProps) {
  const titleId = `dashboard-widget-${title.toLowerCase().replaceAll(/[^a-z0-9]+/g, "-")}`;

  return (
    <article aria-labelledby={titleId} className={`dashboard-widget dashboard-widget--${status}`}>
      <div className="dashboard-widget__header">
        <h3 id={titleId}>{title}</h3>
        <span className="dashboard-widget__status">{statusLabel}</span>
      </div>
      <p className="dashboard-widget__value">{value}</p>
      <p className="dashboard-widget__description">{description}</p>
    </article>
  );
}
