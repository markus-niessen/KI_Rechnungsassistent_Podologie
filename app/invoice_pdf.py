from __future__ import annotations

import re
from io import BytesIO
from decimal import Decimal
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Image as PdfImage
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.db.models import BusinessProfile, Invoice, Patient
from app.girocode import build_epc_girocode_payload, create_girocode_qr_image


INVOICE_PDF_DIRECTORY = Path("generated/invoices")


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


def render_invoice_pdf(
    invoice: Invoice,
    business_profile: BusinessProfile,
    recipient: Patient,
) -> Path:
    if invoice.invoice_number is None:
        raise ValueError("A final invoice number is required for PDF generation.")

    INVOICE_PDF_DIRECTORY.mkdir(parents=True, exist_ok=True)
    output_path = INVOICE_PDF_DIRECTORY / _safe_filename(invoice.invoice_number)
    document = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=f"Rechnung {invoice.invoice_number}",
        author=business_profile.business_name,
    )
    styles = getSampleStyleSheet()
    styles["Title"].fontSize = 20
    styles["Title"].leading = 24
    styles["Heading2"].fontSize = 11
    styles["Heading2"].leading = 14
    styles["BodyText"].fontSize = 9
    styles["BodyText"].leading = 12

    sender_lines = [
        business_profile.business_name,
        business_profile.location_name,
        business_profile.street,
        f"{business_profile.postal_code} {business_profile.city}",
    ]
    if business_profile.phone:
        sender_lines.append(f"Tel.: {business_profile.phone}")
    if business_profile.email:
        sender_lines.append(f"E-Mail: {business_profile.email}")
    if business_profile.tax_number:
        sender_lines.append(f"Steuernummer: {business_profile.tax_number}")
    if business_profile.vat_id:
        sender_lines.append(f"USt-IdNr.: {business_profile.vat_id}")
    if business_profile.ik_number:
        sender_lines.append(f"IK-Nummer: {business_profile.ik_number}")

    story = [Paragraph("Rechnung", styles["Title"]), Spacer(1, 7 * mm)]
    address_table = Table(
        [
            [
                Paragraph("<br/>".join(escape(line) for line in sender_lines), styles["BodyText"]),
                Paragraph("<b>Rechnungsempfänger</b><br/>" + "<br/>".join(
                    escape(line) for line in _recipient_lines(recipient)
                ), styles["BodyText"]),
            ]
        ],
        colWidths=[82 * mm, 82 * mm],
    )
    address_table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.extend([address_table, Spacer(1, 8 * mm)])

    details = Table(
        [
            ["Rechnungsnummer", invoice.invoice_number],
            ["Rechnungsdatum", _format_date(invoice.invoice_date)],
            ["Fälligkeitsdatum", _format_date(invoice.due_date)],
            ["Dokumentart", invoice.document_type],
        ],
        colWidths=[42 * mm, 55 * mm],
    )
    details.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    story.extend([details, Spacer(1, 8 * mm)])

    position_rows = [["Leistung", "Menge", "Einzelpreis", "MwSt.", "Gesamtpreis"]]
    for item in invoice.invoice_items:
        position_rows.append(
            [
                Paragraph(escape(item.service_name_snapshot or item.description), styles["BodyText"]),
                _format_quantity(item.quantity),
                _format_money(item.unit_net_price),
                f"{item.vat_rate:.2f} %".replace(".", ","),
                _format_money(item.line_gross),
            ]
        )
    positions = Table(
        position_rows,
        colWidths=[66 * mm, 20 * mm, 29 * mm, 20 * mm, 29 * mm],
        repeatRows=1,
    )
    positions.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E5E7EB")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
                ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.HexColor("#9CA3AF")),
                ("LINEBELOW", (0, 1), (-1, -1), 0.25, colors.HexColor("#D1D5DB")),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.extend([positions, Spacer(1, 7 * mm)])

    totals = Table(
        [
            ["Netto", _format_money(invoice.total_net)],
            ["MwSt.", _format_money(invoice.total_vat)],
            ["Gesamtbetrag", _format_money(invoice.total_gross)],
        ],
        colWidths=[36 * mm, 35 * mm],
        hAlign="RIGHT",
    )
    totals.setStyle(
        TableStyle(
            [
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                ("LINEABOVE", (0, -1), (-1, -1), 0.75, colors.HexColor("#111827")),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.extend([totals, Spacer(1, 10 * mm)])

    payment_lines = ["<b>Zahlungsinformationen</b>"]
    if business_profile.bank_name:
        payment_lines.append(escape(business_profile.bank_name))
    payment_lines.append(f"IBAN: {escape(business_profile.iban)}")
    if business_profile.bic:
        payment_lines.append(f"BIC: {escape(business_profile.bic)}")
    payment_lines.append(f"Verwendungszweck: Rechnung {escape(invoice.invoice_number)}")
    payment_lines.append("GiroCode für SEPA-Überweisung")
    girocode_buffer = BytesIO()
    create_girocode_qr_image(build_epc_girocode_payload(invoice, business_profile)).save(
        girocode_buffer, format="PNG"
    )
    girocode_buffer.seek(0)
    payment_table = Table(
        [[Paragraph("<br/>".join(payment_lines), styles["BodyText"]), PdfImage(girocode_buffer, 32 * mm, 32 * mm)]],
        colWidths=[120 * mm, 40 * mm],
    )
    payment_table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.append(payment_table)

    document.build(story)
    return output_path
