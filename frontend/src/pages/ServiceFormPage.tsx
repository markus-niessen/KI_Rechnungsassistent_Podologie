import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { createService, getService, updateService } from "../api/services";
import type { ServiceInput } from "../api/types";
import { emptyServiceInput, formatCurrency, normalizeServiceInput, serviceToInput, serviceTypeLabels } from "../services/serviceHelpers";
import "./ServicePages.css";

type Props = { mode: "create" | "edit" };
type LoadState = "loading" | "ready" | "error";

export function ServiceFormPage({ mode }: Props) {
  const { serviceId } = useParams();
  const navigate = useNavigate();
  const numericId = Number(serviceId);
  const [input, setInput] = useState<ServiceInput>(emptyServiceInput);
  const [grossPrice, setGrossPrice] = useState("0.00");
  const [loadState, setLoadState] = useState<LoadState>(mode === "edit" ? "loading" : "ready");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (mode !== "edit") return;
    if (!Number.isInteger(numericId) || numericId <= 0) { setLoadState("error"); return; }
    let mounted = true;
    void getService(numericId).then((service) => {
      if (!mounted) return;
      const next = serviceToInput(service);
      setInput(next);
      setGrossPrice((Number(next.net_price) * (1 + Number(next.vat_rate) / 100)).toFixed(2));
      setLoadState("ready");
    }, () => mounted && setLoadState("error"));
    return () => { mounted = false; };
  }, [mode, numericId]);

  const calculatedGross = useMemo(() => Number(input.net_price.replace(",", ".")) * (1 + Number(input.vat_rate.replace(",", ".")) / 100), [input.net_price, input.vat_rate]);
  useEffect(() => { if (Number.isFinite(calculatedGross)) setGrossPrice(calculatedGross.toFixed(2)); }, [calculatedGross]);

  const update = <K extends keyof ServiceInput>(field: K, value: ServiceInput[K]) => setInput((current) => ({ ...current, [field]: value }));
  const changeGross = (value: string) => {
    setGrossPrice(value);
    const gross = Number(value.replace(",", "."));
    const vat = Number(input.vat_rate.replace(",", "."));
    if (Number.isFinite(gross) && Number.isFinite(vat) && vat >= 0) update("net_price", (gross / (1 + vat / 100)).toFixed(2));
  };
  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    const normalized = normalizeServiceInput(input);
    if (!normalized.name || !Number.isFinite(Number(normalized.net_price)) || !Number.isFinite(Number(normalized.vat_rate))) { setError("Bitte Name, Nettopreis und MwSt.-Satz vollständig angeben."); return; }
    setSaving(true); setError(null);
    try {
      const saved = mode === "create" ? await createService(normalized) : await updateService(numericId, normalized);
      navigate(`/services/${saved.id}`);
    } catch {
      setError("Der Eintrag konnte nicht gespeichert werden. Bitte prüfen Sie Ihre Eingaben und versuchen Sie es erneut.");
    } finally { setSaving(false); }
  };

  if (loadState === "loading") return <p className="service-loading" role="status">Eintrag wird geladen …</p>;
  if (loadState === "error") return <section className="service-error"><p>Der Eintrag wurde nicht gefunden oder konnte nicht geladen werden.</p><Link className="service-button" to="/services">Zur Übersicht</Link></section>;

  return <section className="service-page service-form-page" aria-labelledby="service-form-title"><header className="service-page__header"><div><h2 id="service-form-title">{mode === "create" ? "Neue Leistung / Produkt" : "Leistung / Produkt bearbeiten"}</h2><p>{mode === "create" ? "Erfassen Sie eine podologische Leistung, Zusatzleistung oder ein Produkt." : "Ändern Sie die Stammdaten des ausgewählten Eintrags."}</p></div><Link className="service-button" to="/services">Zurück zur Übersicht</Link></header><div className="service-form-layout"><form className="service-form" onSubmit={submit}><fieldset><legend>Stammdaten</legend><div className="service-form__grid"><label className="service-form__field--wide">Bezeichnung<input aria-label="Bezeichnung" onChange={(event) => update("name", event.target.value)} required value={input.name} /></label><label>Art<select aria-label="Art" onChange={(event) => update("service_type", event.target.value as ServiceInput["service_type"])} value={input.service_type}>{Object.entries(serviceTypeLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label><label className="service-form__field--full">Beschreibung<textarea aria-label="Beschreibung" onChange={(event) => update("description", event.target.value)} value={input.description ?? ""} /></label></div></fieldset><fieldset><legend>Preise</legend><div className="service-form__grid service-form__grid--prices"><label>Nettopreis<input aria-label="Nettopreis" inputMode="decimal" min="0" onChange={(event) => update("net_price", event.target.value)} required step="0.01" type="number" value={input.net_price} /></label><label>MwSt.-Satz<select aria-label="MwSt.-Satz" onChange={(event) => update("vat_rate", event.target.value)} value={input.vat_rate}><option value="0.00">0 %</option><option value="7.00">7 %</option><option value="19.00">19 %</option></select></label><label>Bruttopreis<input aria-label="Bruttopreis" inputMode="decimal" min="0" onChange={(event) => changeGross(event.target.value)} step="0.01" type="number" value={grossPrice} /></label></div><p className="service-form__hint">Netto- und Bruttopreis werden anhand des MwSt.-Satzes automatisch gegeneinander berechnet.</p></fieldset>{error ? <p className="service-form__error" role="alert">{error}</p> : null}<div className="service-form__actions"><Link className="service-button" to="/services">Abbrechen</Link><button className="service-button service-button--primary" disabled={saving} type="submit">{saving ? "Wird gespeichert …" : mode === "create" ? "Eintrag speichern" : "Änderungen speichern"}</button></div></form><aside className="service-preview"><h3>Vorschau</h3><span className={`service-type service-type--${input.service_type.toLowerCase()}`}>{serviceTypeLabels[input.service_type]}</span><strong>{input.name || "Bezeichnung"}</strong><dl><div><dt>Nettopreis</dt><dd>{formatCurrency(input.net_price)}</dd></div><div><dt>MwSt.</dt><dd>{Number(input.vat_rate || 0).toFixed(0)} %</dd></div><div><dt>Bruttopreis</dt><dd>{formatCurrency(calculatedGross)}</dd></div></dl></aside></div></section>;
}
