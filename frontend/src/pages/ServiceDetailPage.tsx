import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { activateService, deactivateService, getService } from "../api/services";
import type { Service } from "../api/types";
import { formatCurrency, serviceGrossPrice, serviceTypeLabels } from "../services/serviceHelpers";
import "./ServicePages.css";

type LoadState = "error" | "loading" | "ready";

export function ServiceDetailPage() {
  const { serviceId } = useParams();
  const id = Number(serviceId);
  const [service, setService] = useState<Service | null>(null);
  const [loadState, setLoadState] = useState<LoadState>("loading");
  const [confirming, setConfirming] = useState(false);
  const [mutationError, setMutationError] = useState<string | null>(null);

  const load = () => {
    if (!Number.isInteger(id) || id <= 0) { setLoadState("error"); return; }
    let mounted = true;
    setLoadState("loading");
    void getService(id).then((data) => { if (mounted) { setService(data); setLoadState("ready"); } }, () => mounted && setLoadState("error"));
    return () => { mounted = false; };
  };
  useEffect(() => load(), [id]);
  const changeStatus = async () => {
    if (!service) return;
    setMutationError(null);
    try { setService(service.active ? await deactivateService(service.id) : await activateService(service.id)); }
    catch { setMutationError("Der Status konnte nicht geändert werden."); }
    finally { setConfirming(false); }
  };

  if (loadState === "loading") return <p className="service-loading" role="status">Eintrag wird geladen …</p>;
  if (loadState === "error" || !service) return <section className="service-error"><p>Der Eintrag wurde nicht gefunden oder existiert nicht mehr.</p><Link className="service-button" to="/services">Zur Übersicht</Link></section>;
  const gross = serviceGrossPrice(service);
  return <section className="service-page service-detail" aria-labelledby="service-detail-title"><header className="service-page__header"><div><h2 id="service-detail-title">{service.name}</h2><p>{serviceTypeLabels[service.service_type]} · <span className={service.active ? "service-status" : "service-status service-status--inactive"}>{service.active ? "Aktiv" : "Inaktiv"}</span></p></div><div className="service-detail__actions"><Link className="service-button" to="/services">Zurück zur Übersicht</Link><Link className="service-button service-button--primary" to={`/services/${service.id}/edit`}>Bearbeiten</Link><button className="service-button" onClick={() => setConfirming(true)} type="button">{service.active ? "Deaktivieren" : "Aktivieren"}</button></div></header>{mutationError ? <p className="service-form__error" role="alert">{mutationError}</p> : null}<div className="service-detail__layout"><section className="service-detail__card"><h3>Allgemeine Informationen</h3><dl><div><dt>Bezeichnung</dt><dd>{service.name}</dd></div><div><dt>Art</dt><dd><span className={`service-type service-type--${service.service_type.toLowerCase()}`}>{serviceTypeLabels[service.service_type]}</span></dd></div><div><dt>Beschreibung</dt><dd>{service.description || "Keine Beschreibung hinterlegt."}</dd></div><div><dt>Nettopreis</dt><dd>{formatCurrency(service.net_price)}</dd></div><div><dt>MwSt.-Satz</dt><dd>{Number(service.vat_rate).toFixed(0)} %</dd></div><div><dt>Bruttopreis</dt><dd><strong>{formatCurrency(gross)}</strong></dd></div><div><dt>Status</dt><dd><span className={service.active ? "service-status" : "service-status service-status--inactive"}>{service.active ? "Aktiv" : "Inaktiv"}</span></dd></div><div><dt>Angelegt am</dt><dd>{new Date(service.created_at).toLocaleDateString("de-DE")}</dd></div></dl></section><aside className="service-detail__summary"><span className={`service-type service-type--${service.service_type.toLowerCase()}`}>{serviceTypeLabels[service.service_type]}</span><h3>{service.name}</h3><strong>{formatCurrency(gross)}</strong><small>inkl. {Number(service.vat_rate).toFixed(0)} % MwSt.</small><p>Preis- und Steuerwerte werden beim Erstellen einer Rechnung als Snapshot gespeichert.</p></aside></div>{confirming ? <div className="service-dialog-backdrop" role="presentation"><section aria-label={`Eintrag ${service.active ? "deaktivieren" : "aktivieren"}?`} aria-modal="true" className="service-dialog" role="dialog"><h2>Eintrag {service.active ? "deaktivieren" : "aktivieren"}?</h2><p>{service.active ? "Der Eintrag wird für neue Vorgänge nicht mehr vorgeschlagen." : "Der Eintrag ist wieder für neue Vorgänge verfügbar."}</p><div className="service-dialog__actions"><button className="service-button" onClick={() => setConfirming(false)} type="button">Abbrechen</button><button className="service-button service-button--primary" onClick={() => void changeStatus()} type="button">{service.active ? "Deaktivieren" : "Aktivieren"}</button></div></section></div> : null}</section>;
}
