import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";

import { activateService, deactivateService, getServices } from "../api/services";
import type { Service, ServiceType } from "../api/types";
import {
  defaultServiceColumnLayout,
  formatCurrency,
  loadServiceColumnLayout,
  saveServiceColumnLayout,
  serviceColumns,
  serviceGrossPrice,
  serviceTypeLabels,
  type ServiceColumnId,
  type ServiceColumnLayout,
} from "../services/serviceHelpers";
import "./ServicePages.css";

type LoadState = "error" | "loading" | "ready";
type StatusFilter = "active" | "all" | "inactive";

export function ServicesPage() {
  const [services, setServices] = useState<Service[]>([]);
  const [loadState, setLoadState] = useState<LoadState>("loading");
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState<"all" | ServiceType>("all");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [layout, setLayout] = useState(loadServiceColumnLayout);
  const [columnsOpen, setColumnsOpen] = useState(false);
  const [actionTarget, setActionTarget] = useState<Service | null>(null);
  const [mutationError, setMutationError] = useState<string | null>(null);
  const columnsRef = useRef<HTMLDivElement>(null);

  const loadServices = () => {
    let mounted = true;
    setLoadState("loading");
    void getServices({ includeInactive: true, search: search.trim() || undefined }).then(
      (data) => { if (mounted) { setServices(data); setLoadState("ready"); } },
      () => mounted && setLoadState("error"),
    );
    return () => { mounted = false; };
  };

  useEffect(() => loadServices(), [search]);
  useEffect(() => {
    if (!columnsOpen) return;
    const closeOutside = (event: MouseEvent) => { if (!columnsRef.current?.contains(event.target as Node)) setColumnsOpen(false); };
    const closeEscape = (event: KeyboardEvent) => { if (event.key === "Escape") setColumnsOpen(false); };
    document.addEventListener("mousedown", closeOutside);
    document.addEventListener("keydown", closeEscape);
    return () => { document.removeEventListener("mousedown", closeOutside); document.removeEventListener("keydown", closeEscape); };
  }, [columnsOpen]);

  const filteredServices = useMemo(() => services.filter((service) => (
    (typeFilter === "all" || service.service_type === typeFilter) &&
    (statusFilter === "all" || (statusFilter === "active" ? service.active : !service.active))
  )), [services, statusFilter, typeFilter]);
  const orderedColumns = layout.order.filter((id) => layout.visibility[id]);

  const updateLayout = (next: ServiceColumnLayout) => { setLayout(next); saveServiceColumnLayout(next); };
  const toggleColumn = (id: ServiceColumnId) => {
    const column = serviceColumns.find((item) => item.id === id);
    if (column?.required) return;
    updateLayout({ ...layout, visibility: { ...layout.visibility, [id]: !layout.visibility[id] } });
  };
  const moveColumn = (id: ServiceColumnId, direction: -1 | 1) => {
    const index = layout.order.indexOf(id);
    const target = index + direction;
    if (target < 0 || target >= layout.order.length) return;
    const order = [...layout.order];
    [order[index], order[target]] = [order[target], order[index]];
    updateLayout({ ...layout, order });
  };
  const changeStatus = async (service: Service) => {
    setMutationError(null);
    try {
      const updated = service.active ? await deactivateService(service.id) : await activateService(service.id);
      setServices((current) => current.map((item) => item.id === updated.id ? updated : item));
    } catch {
      setMutationError("Der Status konnte nicht geändert werden.");
    } finally {
      setActionTarget(null);
    }
  };

  return <section className="service-page" aria-labelledby="services-title">
    <header className="service-page__header">
      <div><h2 id="services-title">Leistungen &amp; Produkte</h2><p>Leistungen, Zusatzleistungen und Produkte auf einen Blick.</p></div>
      <Link className="service-button service-button--primary" to="/services/new">+ Neue Leistung / Produkt</Link>
    </header>
    <div className="service-summary-grid" aria-label="Übersicht der Leistungen und Produkte">
      <ServiceSummary label="Gesamt" value={services.length} />
      <ServiceSummary label="Leistungen" value={services.filter((item) => item.service_type === "SERVICE").length} />
      <ServiceSummary label="Zusatzleistungen" value={services.filter((item) => item.service_type === "ADDITIONAL_SERVICE").length} />
      <ServiceSummary label="Produkte" value={services.filter((item) => item.service_type === "PRODUCT").length} />
      <ServiceSummary label="Inaktiv" value={services.filter((item) => !item.active).length} />
    </div>
    <div className="service-toolbar">
      <label className="service-search"><span className="visually-hidden">Leistungen und Produkte suchen</span><input onChange={(event) => setSearch(event.target.value)} placeholder="Suche nach Bezeichnung oder Beschreibung …" value={search} /></label>
      <div className="service-toolbar__filters">
        <label><span className="visually-hidden">Art filtern</span><select aria-label="Art filtern" onChange={(event) => setTypeFilter(event.target.value as "all" | ServiceType)} value={typeFilter}><option value="all">Alle Arten</option><option value="SERVICE">Leistungen</option><option value="ADDITIONAL_SERVICE">Zusatzleistungen</option><option value="PRODUCT">Produkte</option></select></label>
        <label><span className="visually-hidden">Status filtern</span><select aria-label="Status filtern" onChange={(event) => setStatusFilter(event.target.value as StatusFilter)} value={statusFilter}><option value="all">Alle Status</option><option value="active">Aktiv</option><option value="inactive">Inaktiv</option></select></label>
        <div className="service-columns-popover" ref={columnsRef}>
          <button aria-expanded={columnsOpen} aria-haspopup="menu" className="service-button" onClick={() => setColumnsOpen((open) => !open)} type="button">Spalten</button>
          {columnsOpen ? <div aria-label="Spalten auswählen" className="service-columns" role="menu">{serviceColumns.map((column) => <div className="service-columns__item" key={column.id}><label><input checked={layout.visibility[column.id]} disabled={column.required} onChange={() => toggleColumn(column.id)} type="checkbox" />{column.label}</label><span><button aria-label={`${column.label} nach oben`} disabled={layout.order.indexOf(column.id) === 0} onClick={() => moveColumn(column.id, -1)} type="button">↑</button><button aria-label={`${column.label} nach unten`} disabled={layout.order.indexOf(column.id) === layout.order.length - 1} onClick={() => moveColumn(column.id, 1)} type="button">↓</button></span></div>)}<button className="service-action-button" onClick={() => updateLayout(defaultServiceColumnLayout())} type="button">Standard wiederherstellen</button></div> : null}
        </div>
      </div>
    </div>
    <div className="service-quickfilters" aria-label="Schnellfilter">{(["all", "active", "inactive"] as StatusFilter[]).map((filter) => <button aria-pressed={statusFilter === filter} key={filter} onClick={() => setStatusFilter(filter)} type="button">{filter === "all" ? `Alle (${services.length})` : filter === "active" ? `Aktiv (${services.filter((item) => item.active).length})` : `Inaktiv (${services.filter((item) => !item.active).length})`}</button>)}</div>
    {mutationError ? <p className="service-form__error" role="alert">{mutationError}</p> : null}
    {loadState === "loading" ? <p className="service-loading" role="status">Leistungen und Produkte werden geladen …</p> : null}
    {loadState === "error" ? <div className="service-error"><p>Die Daten konnten momentan nicht geladen werden.</p><button className="service-button" onClick={loadServices} type="button">Erneut versuchen</button></div> : null}
    {loadState === "ready" && filteredServices.length === 0 ? <div className="service-empty"><p>{services.length === 0 ? "Noch keine Leistungen oder Produkte vorhanden." : "Keine Einträge für diese Suche oder Filter gefunden."}</p>{services.length === 0 ? <Link className="service-button service-button--primary" to="/services/new">Eintrag anlegen</Link> : <button className="service-button" onClick={() => { setSearch(""); setTypeFilter("all"); setStatusFilter("all"); }} type="button">Filter zurücksetzen</button>}</div> : null}
    {loadState === "ready" && filteredServices.length > 0 ? <><div className="service-table-card"><div className="service-table-wrap"><table className="service-table"><thead><tr>{orderedColumns.map((id) => <th key={id}>{serviceColumns.find((column) => column.id === id)?.label}</th>)}<th>Aktionen</th></tr></thead><tbody>{filteredServices.map((service) => <ServiceRow columns={orderedColumns} key={service.id} onStatusChange={setActionTarget} service={service} />)}</tbody></table></div></div><div className="service-cards">{filteredServices.map((service) => <ServiceCard key={service.id} onStatusChange={setActionTarget} service={service} />)}</div></> : null}
    {actionTarget ? <ServiceConfirmDialog onCancel={() => setActionTarget(null)} onConfirm={() => void changeStatus(actionTarget)} service={actionTarget} /> : null}
  </section>;
}

function ServiceSummary({ label, value }: { label: string; value: number }) {
  return <article className="service-summary"><span>{label}</span><strong>{value}</strong><small>{value === 1 ? "Eintrag" : "Einträge"}</small></article>;
}

function ServiceCell({ column, service }: { column: ServiceColumnId; service: Service }) {
  if (column === "name") return <Link className="service-table__name" to={`/services/${service.id}`}>{service.name}</Link>;
  if (column === "type") return <span className={`service-type service-type--${service.service_type.toLowerCase()}`}>{serviceTypeLabels[service.service_type]}</span>;
  if (column === "description") return service.description || "–";
  if (column === "netPrice") return formatCurrency(service.net_price);
  if (column === "vatRate") return `${Number(service.vat_rate).toFixed(0)} %`;
  if (column === "grossPrice") return formatCurrency(serviceGrossPrice(service));
  return <span className={service.active ? "service-status" : "service-status service-status--inactive"}>{service.active ? "Aktiv" : "Inaktiv"}</span>;
}

function ServiceRow({ columns, onStatusChange, service }: { columns: ServiceColumnId[]; onStatusChange: (service: Service) => void; service: Service }) {
  return <tr>{columns.map((column) => <td key={column}><ServiceCell column={column} service={service} /></td>)}<td><div className="service-row-actions"><Link className="service-action-button" to={`/services/${service.id}`}>Öffnen</Link><Link className="service-action-button" to={`/services/${service.id}/edit`}>Bearbeiten</Link><button aria-label={`${service.active ? "Deaktivieren" : "Aktivieren"}: ${service.name}`} className="service-action-button" onClick={() => onStatusChange(service)} type="button">{service.active ? "Deaktivieren" : "Aktivieren"}</button></div></td></tr>;
}

function ServiceCard({ onStatusChange, service }: { onStatusChange: (service: Service) => void; service: Service }) {
  return <article className="service-card"><div><Link className="service-table__name" to={`/services/${service.id}`}>{service.name}</Link><p>{service.description || "Keine Beschreibung hinterlegt."}</p></div><div className="service-card__meta"><span className={`service-type service-type--${service.service_type.toLowerCase()}`}>{serviceTypeLabels[service.service_type]}</span><strong>{formatCurrency(serviceGrossPrice(service))}</strong><span className={service.active ? "service-status" : "service-status service-status--inactive"}>{service.active ? "Aktiv" : "Inaktiv"}</span></div><div className="service-row-actions"><Link className="service-action-button" to={`/services/${service.id}`}>Öffnen</Link><Link className="service-action-button" to={`/services/${service.id}/edit`}>Bearbeiten</Link><button className="service-action-button" onClick={() => onStatusChange(service)} type="button">{service.active ? "Deaktivieren" : "Aktivieren"}</button></div></article>;
}

function ServiceConfirmDialog({ onCancel, onConfirm, service }: { onCancel: () => void; onConfirm: () => void; service: Service }) {
  const verb = service.active ? "deaktivieren" : "aktivieren";
  return <div className="service-dialog-backdrop" role="presentation"><section aria-label={`Eintrag ${verb}?`} aria-modal="true" className="service-dialog" role="dialog"><h2>Eintrag {verb}?</h2><p>{service.name} wird {service.active ? "nicht mehr für neue Vorgänge vorgeschlagen" : "wieder für neue Vorgänge verfügbar"}.</p><div className="service-dialog__actions"><button className="service-button" onClick={onCancel} type="button">Abbrechen</button><button className="service-button service-button--primary" onClick={onConfirm} type="button">{service.active ? "Deaktivieren" : "Aktivieren"}</button></div></section></div>;
}
