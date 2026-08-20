from __future__ import annotations

import re
from io import BytesIO
from decimal import Decimal
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Image as PdfImage
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.db.models import BusinessProfile, Invoice, Patient
from app.girocode import build_epc_girocode_payload, create_girocode_qr_image


INVOICE_PDF_DIRECTORY = Path("generated/invoices")
_STATIC_IMAGE_DIRECTORY = Path(__file__).parent / "static" / "images"
_DARK_GREEN = colors.HexColor("#0D4A2A")
_ACCENT_GREEN = colors.HexColor("#5E7F42")
_LIGHT_GREEN = colors.HexColor("#F3F7F1")
_LINE_COLOR = colors.HexColor("#C9D3C6")
_TEXT_COLOR = colors.HexColor("#1F2933")


def _format_money(amount: Decimal) -> str:
    return f"{amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") + " €"


def _format_quantity(quantity: Decimal) -> str:
    return f"{quantity:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _format_date(value: object) -> str:
    return value.strftime("%d.%m.%Y")


def _recipient_lines(patient: Patient) -> list[str]:
    alternative_address = (
        patient.invoice_name,
        patient.invoice_street,
        patient.invoice_zip,
        patient.invoice_city,
    )
    if all(value and value.strip() for value in alternative_address):
        return [str(value) for value in alternative_address]
    return [
        f"{patient.first_name} {patient.last_name}",
        patient.street or "",
        f"{patient.zip or ''} {patient.city or ''}".strip(),
    ]


def _safe_filename(invoice_number: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", invoice_number) + ".pdf"


def _document_heading(invoice: Invoice) -> str:
    return "Sammelrechnung" if invoice.document_type == "COLLECTIVE_INVOICE" else "Rechnung"


def _logo_path(business_profile: BusinessProfile) -> Path | None:
    candidates = []
    if business_profile.logo_path:
        candidates.append(Path(business_profile.logo_path))
    candidates.extend((_STATIC_IMAGE_DIRECTORY / "logo.png", _STATIC_IMAGE_DIRECTORY / "Logo.png"))
    return next((path for path in candidates if path.is_file()), None)


def _logo_image(business_profile: BusinessProfile) -> PdfImage | Spacer:
    path = _logo_path(business_profile)
    if path is None:
        return Spacer(58 * mm, 29 * mm)
    try:
        image_width, image_height = ImageReader(str(path)).getSize()
        width = 58 * mm
        return PdfImage(str(path), width=width, height=width * image_height / image_width)
    except Exception:  # pragma: no cover - protects PDF output from unreadable optional assets
        return Spacer(58 * mm, 29 * mm)


def _business_header_lines(business_profile: BusinessProfile) -> str:
    lines = [f"<b>{escape(business_profile.business_name)}</b>", escape(business_profile.location_name)]
    lines.extend((escape(business_profile.street), escape(f"{business_profile.postal_code} {business_profile.city}")))
    if business_profile.phone:
        lines.append(f"Tel. {escape(business_profile.phone)}")
    if business_profile.email:
        lines.append(escape(business_profile.email))
    return "<br/>".join(lines)


def _draw_page_border(canvas: object) -> None:
    canvas.saveState()
    canvas.setStrokeColor(_LINE_COLOR)
    canvas.setLineWidth(0.35)
    canvas.rect(2 * mm, 2 * mm, A4[0] - 4 * mm, A4[1] - 4 * mm)
    canvas.restoreState()


def _draw_fold_marks(canvas: object) -> None:
    canvas.saveState()
    canvas.setStrokeColor(_LINE_COLOR)
    canvas.setLineWidth(0.4)
    for distance_from_top in (105, 148.5, 210):
        y = A4[1] - distance_from_top * mm
        canvas.line(3 * mm, y, 7.5 * mm, y)
    canvas.restoreState()


def _footer_columns(business_profile: BusinessProfile) -> list[tuple[str, list[str]]]:
    practice = [business_profile.business_name, business_profile.street, f"{business_profile.postal_code} {business_profile.city}"]
    bank = [line for line in (business_profile.bank_name, f"IBAN {business_profile.iban}", f"BIC {business_profile.bic}" if business_profile.bic else None) if line]
    tax = [line for line in (f"St.-Nr. {business_profile.tax_number}" if business_profile.tax_number else None, f"USt-IdNr. {business_profile.vat_id}" if business_profile.vat_id else None) if line]
    billing = [f"IK {business_profile.ik_number}"] if business_profile.ik_number else []
    return [("Praxis", practice), ("Bankverbindung", bank), ("Steuer", tax), ("Abrechnung", billing)]


def _draw_footer(canvas: object, document: object, business_profile: BusinessProfile) -> None:
    canvas.saveState()
    left, right = document.leftMargin, A4[0] - document.rightMargin
    canvas.setStrokeColor(_ACCENT_GREEN)
    canvas.setLineWidth(0.45)
    canvas.line(left, 29 * mm, right, 29 * mm)
    column_width = (right - left) / 4
    for index, (title, lines) in enumerate(_footer_columns(business_profile)):
        if not lines:
            continue
        x = left + index * column_width
        canvas.setFillColor(_DARK_GREEN)
        canvas.setFont("Helvetica-Bold", 6.5)
        canvas.drawString(x, 23 * mm, title)
        canvas.setFillColor(_TEXT_COLOR)
        canvas.setFont("Helvetica", 6.2)
        for line_index, line in enumerate(lines[:3]):
            canvas.drawString(x, (20.2 - line_index * 2.8) * mm, line)
    canvas.restoreState()


def _draw_later_page_header(canvas: object, document: object, business_profile: BusinessProfile, heading: str, invoice_number: str) -> None:
    canvas.saveState()
    canvas.setFillColor(_TEXT_COLOR)
    canvas.setFont("Helvetica", 8)
    canvas.drawString(document.leftMargin, A4[1] - 11 * mm, f"{business_profile.business_name} | {heading} {invoice_number}")
    canvas.drawRightString(A4[0] - document.rightMargin, A4[1] - 11 * mm, f"Seite {canvas.getPageNumber()}")
    canvas.setStrokeColor(_LINE_COLOR)
    canvas.setLineWidth(0.35)
    canvas.line(document.leftMargin, A4[1] - 13 * mm, A4[0] - document.rightMargin, A4[1] - 13 * mm)
    canvas.restoreState()


def _first_page(canvas: object, document: object, business_profile: BusinessProfile) -> None:
    _draw_page_border(canvas)
    _draw_fold_marks(canvas)
    _draw_footer(canvas, document, business_profile)


def _later_page(canvas: object, document: object, business_profile: BusinessProfile, heading: str, invoice_number: str) -> None:
    _draw_page_border(canvas)
    _draw_later_page_header(canvas, document, business_profile, heading, invoice_number)
    _draw_footer(canvas, document, business_profile)


def _invoice_data_table(invoice: Invoice, styles: object) -> Table:
    label_style = ParagraphStyle("InvoiceLabel", parent=styles["BodyText"], fontName="Helvetica-Bold", fontSize=7.4, leading=10)
    value_style = ParagraphStyle("InvoiceValue", parent=styles["BodyText"], fontSize=7.4, leading=10)
    due_style = ParagraphStyle("InvoiceDue", parent=value_style, textColor=_DARK_GREEN, fontName="Helvetica-Bold")
    rows = [("Rechnungsnummer", invoice.invoice_number), ("Rechnungsdatum", _format_date(invoice.invoice_date)), ("Fällig am", _format_date(invoice.due_date))]
    data = []
    for label, value in rows:
        style = due_style if label == "Fällig am" else value_style
        data.append([Paragraph(label, label_style), Paragraph(escape(str(value)), style)])
    table = Table(data, colWidths=[31 * mm, 39 * mm])
    table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.8)]))
    return table


def _position_table(invoice: Invoice, styles: object) -> Table:
    cell_style = ParagraphStyle("PositionCell", parent=styles["BodyText"], fontSize=7.3, leading=9.2, textColor=_TEXT_COLOR)
    header_style = ParagraphStyle("PositionHeader", parent=cell_style, fontName="Helvetica-Bold", fontSize=7, leading=8)
    if invoice.document_type == "COLLECTIVE_INVOICE":
        headers = ["Pos.", "Patient", "Leistung / Produkt", "Menge", "Einzelpreis", "MwSt.", "Gesamtpreis"]
        widths, numeric_start = [10 * mm, 30 * mm, 39 * mm, 15 * mm, 23 * mm, 15 * mm, 20 * mm], 3
        rows = [[str(position), Paragraph(escape(item.patient_name_snapshot or ""), cell_style), Paragraph(escape(item.service_name_snapshot or item.description), cell_style), _format_quantity(item.quantity), _format_money(item.unit_net_price), f"{item.vat_rate:.2f} %".replace(".", ","), _format_money(item.line_gross)] for position, item in enumerate(invoice.invoice_items, start=1)]
    else:
        headers = ["Pos.", "Leistung / Produkt", "Menge", "Einzelpreis", "MwSt.", "Gesamtpreis"]
        widths, numeric_start = [10 * mm, 69 * mm, 16 * mm, 24 * mm, 16 * mm, 27 * mm], 2
        rows = [[str(position), Paragraph(escape(item.service_name_snapshot or item.description), cell_style), _format_quantity(item.quantity), _format_money(item.unit_net_price), f"{item.vat_rate:.2f} %".replace(".", ","), _format_money(item.line_gross)] for position, item in enumerate(invoice.invoice_items, start=1)]
    table = Table([[Paragraph(header, header_style) for header in headers], *rows], colWidths=widths, repeatRows=1, splitByRow=1)
    table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), _LIGHT_GREEN), ("TEXTCOLOR", (0, 0), (-1, 0), _DARK_GREEN), ("ALIGN", (0, 1), (0, -1), "CENTER"), ("ALIGN", (numeric_start, 1), (-1, -1), "RIGHT"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("GRID", (0, 0), (-1, -1), 0.25, _LINE_COLOR), ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4), ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3)]))
    return table


def _totals_table(invoice: Invoice) -> Table:
    vat_rates = {Decimal(item.vat_rate) for item in invoice.invoice_items}
    vat_label = f"MwSt. {next(iter(vat_rates)):.0f} %" if len(vat_rates) == 1 else "MwSt."
    table = Table([["Nettobetrag", _format_money(invoice.total_net)], [vat_label, _format_money(invoice.total_vat)], ["Gesamtbetrag", _format_money(invoice.total_gross)]], colWidths=[37 * mm, 34 * mm], hAlign="RIGHT")
    table.setStyle(TableStyle([("ALIGN", (1, 0), (1, -1), "RIGHT"), ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"), ("TEXTCOLOR", (0, -1), (-1, -1), _DARK_GREEN), ("LINEABOVE", (0, -1), (-1, -1), 0.7, _ACCENT_GREEN), ("FONTSIZE", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 3.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5)]))
    return table


def _payment_table(invoice: Invoice, business_profile: BusinessProfile, styles: object) -> Table:
    payment_style = ParagraphStyle("Payment", parent=styles["BodyText"], fontSize=7.2, leading=10, textColor=_TEXT_COLOR)
    payment_lines = ["<b><font color='#0D4A2A'>Zahlungsinformationen</font></b>", f"Bitte überweisen Sie den Gesamtbetrag von <b>{_format_money(invoice.total_gross)}</b> bis zum <b>{_format_date(invoice.due_date)}</b> unter Angabe der Rechnungsnummer."]
    if business_profile.bank_name:
        payment_lines.append(f"Bank: {escape(business_profile.bank_name)}")
    payment_lines.append(f"IBAN: {escape(business_profile.iban)}")
    if business_profile.bic:
        payment_lines.append(f"BIC: {escape(business_profile.bic)}")
    payment_lines.append(f"Verwendungszweck: {escape(invoice.invoice_number or '')}")
    girocode_buffer = BytesIO()
    create_girocode_qr_image(build_epc_girocode_payload(invoice, business_profile)).save(girocode_buffer, format="PNG")
    girocode_buffer.seek(0)
    qr_style = ParagraphStyle("GiroCode", parent=payment_style, alignment=1)
    qr_block = [Paragraph("<b><font color='#0D4A2A'>GiroCode</font></b>", qr_style), Paragraph("Mit Banking-App scannen und bequem bezahlen.", qr_style), Spacer(1, 1.5 * mm), PdfImage(girocode_buffer, 27 * mm, 27 * mm)]
    table = Table([[Paragraph("<br/>".join(payment_lines), payment_style), qr_block]], colWidths=[119 * mm, 41 * mm])
    table.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.5, _LINE_COLOR), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6), ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
    return table


def render_invoice_pdf(invoice: Invoice, business_profile: BusinessProfile, recipient: Patient) -> Path:
    if invoice.invoice_number is None:
        raise ValueError("A final invoice number is required for PDF generation.")

    INVOICE_PDF_DIRECTORY.mkdir(parents=True, exist_ok=True)
    output_path = INVOICE_PDF_DIRECTORY / _safe_filename(invoice.invoice_number)
    heading = _document_heading(invoice)
    document = SimpleDocTemplate(str(output_path), pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm, topMargin=14 * mm, bottomMargin=32 * mm, title=f"{heading} {invoice.invoice_number}", author=business_profile.business_name)
    styles = getSampleStyleSheet()
    styles["BodyText"].fontSize, styles["BodyText"].leading = 8.3, 10.5
    title_style = ParagraphStyle("DocumentTitle", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=15, leading=18, textColor=_DARK_GREEN)
    intro_style = ParagraphStyle("InvoiceIntro", parent=styles["BodyText"], fontSize=8, leading=10.5)
    recipient_style = ParagraphStyle("Recipient", parent=styles["BodyText"], fontSize=8.7, leading=11)
    header = Table([[_logo_image(business_profile), Paragraph(_business_header_lines(business_profile), styles["BodyText"])]], colWidths=[101 * mm, 69 * mm])
    header.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
    sender_line = f"{business_profile.business_name} · {business_profile.street} · {business_profile.postal_code} {business_profile.city}"
    recipient_text = "<br/>".join(escape(line) for line in _recipient_lines(recipient))
    address_and_details = Table([[Paragraph(f"<font size='6.4'>{escape(sender_line)}</font><br/><br/>{recipient_text}", recipient_style), _invoice_data_table(invoice, styles)]], colWidths=[100 * mm, 70 * mm])
    address_and_details.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
    story = [header, Spacer(1, 3 * mm), address_and_details, Spacer(1, 18 * mm), Paragraph(heading, title_style), Spacer(1, 3 * mm), Paragraph("Für die nachfolgend aufgeführten Leistungen erlauben wir uns, wie folgt in Rechnung zu stellen:", intro_style), Spacer(1, 5 * mm), _position_table(invoice, styles), Spacer(1, 6 * mm), KeepTogether([_totals_table(invoice), Spacer(1, 8 * mm), _payment_table(invoice, business_profile, styles)])]
    document.build(story, onFirstPage=lambda canvas, doc: _first_page(canvas, doc, business_profile), onLaterPages=lambda canvas, doc: _later_page(canvas, doc, business_profile, heading, invoice.invoice_number))
    return output_path
