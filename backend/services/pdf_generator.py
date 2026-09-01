"""
backend/services/pdf_generator.py
──────────────────────────────────
Generates professional demand-letter PDFs using ReportLab.

Entry point
───────────
    generate_demand_letter_pdf(case, customer) -> io.BytesIO

Returns an in-memory binary buffer containing a fully styled PDF that can be
streamed directly by a FastAPI Response.
"""

from __future__ import annotations

import io
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

if TYPE_CHECKING:
    from backend.models import Customer, RevenueCase

# ── Colour Palette ────────────────────────────────────────────────────────────

BRAND_DARK   = colors.HexColor("#0F172A")
BRAND_ACCENT = colors.HexColor("#6366F1")
BRAND_RED    = colors.HexColor("#EF4444")
TEXT_PRIMARY = colors.HexColor("#1E293B")
TEXT_MUTED   = colors.HexColor("#64748B")
TEXT_LIGHT   = colors.HexColor("#94A3B8")
WHITE        = colors.white
LIGHT_GRAY   = colors.HexColor("#F1F5F9")
BORDER_GRAY  = colors.HexColor("#CBD5E1")


# ── Style Registry ────────────────────────────────────────────────────────────

def _build_styles() -> dict:
    return {
        "company": ParagraphStyle(
            "company", fontSize=22, leading=26, textColor=WHITE,
            fontName="Helvetica-Bold", alignment=TA_LEFT,
        ),
        "tagline": ParagraphStyle(
            "tagline", fontSize=9, leading=12,
            textColor=colors.HexColor("#A5B4FC"),
            fontName="Helvetica", alignment=TA_LEFT,
        ),
        "header_right": ParagraphStyle(
            "header_right", fontSize=8, leading=11,
            textColor=colors.HexColor("#CBD5E1"),
            fontName="Helvetica", alignment=TA_RIGHT,
        ),
        "doc_title": ParagraphStyle(
            "doc_title", fontSize=15, leading=18, textColor=BRAND_ACCENT,
            fontName="Helvetica-Bold", alignment=TA_CENTER, spaceAfter=2,
        ),
        "doc_subtitle": ParagraphStyle(
            "doc_subtitle", fontSize=9, leading=12, textColor=TEXT_MUTED,
            fontName="Helvetica", alignment=TA_CENTER,
        ),
        "section_label": ParagraphStyle(
            "section_label", fontSize=8, leading=10, textColor=BRAND_ACCENT,
            fontName="Helvetica-Bold", spaceBefore=6, spaceAfter=3,
        ),
        "body_justify": ParagraphStyle(
            "body_justify", fontSize=9, leading=14, textColor=TEXT_PRIMARY,
            fontName="Helvetica", alignment=TA_JUSTIFY,
        ),
        "label": ParagraphStyle(
            "label", fontSize=8, leading=11, textColor=TEXT_MUTED, fontName="Helvetica",
        ),
        "value": ParagraphStyle(
            "value", fontSize=9, leading=12, textColor=TEXT_PRIMARY, fontName="Helvetica-Bold",
        ),
        "amount_large": ParagraphStyle(
            "amount_large", fontSize=20, leading=24, textColor=BRAND_RED,
            fontName="Helvetica-Bold", alignment=TA_CENTER,
        ),
        "amount_label": ParagraphStyle(
            "amount_label", fontSize=8, leading=10, textColor=TEXT_MUTED,
            fontName="Helvetica", alignment=TA_CENTER,
        ),
        "footer": ParagraphStyle(
            "footer", fontSize=7, leading=10, textColor=TEXT_LIGHT,
            fontName="Helvetica", alignment=TA_CENTER,
        ),
        "table_header": ParagraphStyle(
            "table_header", fontSize=8, leading=10, textColor=WHITE, fontName="Helvetica-Bold",
        ),
        "table_cell": ParagraphStyle(
            "table_cell", fontSize=8, leading=11, textColor=TEXT_PRIMARY, fontName="Helvetica",
        ),
        "table_cell_bold": ParagraphStyle(
            "table_cell_bold", fontSize=8, leading=11, textColor=TEXT_PRIMARY, fontName="Helvetica-Bold",
        ),
        "table_cell_red": ParagraphStyle(
            "table_cell_red", fontSize=8, leading=11, textColor=BRAND_RED, fontName="Helvetica-Bold",
        ),
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _fmt(amount: float, currency: str) -> str:
    sym = {"INR": "Rs.", "USD": "$", "EUR": "EUR ", "GBP": "GBP "}.get(currency.upper(), currency + " ")
    return f"{sym}{amount:,.2f}"


def _days_overdue(case: "RevenueCase") -> int:
    now = datetime.now(timezone.utc)
    created = case.created_at
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    return max(0, (now - created).days)


def _late_fee(amount: float, days: int) -> float:
    if days <= 0:
        return 0.0
    return round(amount * (0.02 / 30) * days, 2)


# ── Header ────────────────────────────────────────────────────────────────────

def _build_header(styles: dict, case: "RevenueCase") -> Table:
    now_str = datetime.now(timezone.utc).strftime("%d %B %Y")
    ref_id  = str(case.id).upper()[:16]

    left  = [Paragraph("AI Revenue Recovery", styles["company"]),
              Paragraph("Automated Collections & Payment Recovery Platform", styles["tagline"])]
    right = [Paragraph(f"<b>Date:</b> {now_str}", styles["header_right"]),
              Paragraph(f"<b>Ref:</b> {ref_id}", styles["header_right"]),
              Paragraph("<b>Status:</b> OFFICIAL NOTICE", styles["header_right"])]

    tbl = Table([[left, right]], colWidths=["65%", "35%"])
    tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), BRAND_DARK),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING",   (0, 0), (0, -1),  14),
        ("RIGHTPADDING",  (1, 0), (1, -1),  14),
        ("TOPPADDING",    (0, 0), (-1, -1), 14),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
    ]))
    return tbl


# ── Recipient table ───────────────────────────────────────────────────────────

def _build_recipient_table(styles: dict, customer: "Customer") -> Table:
    def row(label: str, value: str) -> list:
        return [Paragraph(label, styles["label"]), Paragraph(value or "N/A", styles["value"])]

    data = [
        row("Full Name",  str(customer.name)),
        row("Email",      str(customer.email)),
        row("Phone",      str(customer.phone) if customer.phone else "N/A"),
        row("Account ID", str(customer.id)[:20].upper()),
    ]
    tbl = Table(data, colWidths=["28%", "72%"])
    tbl.setStyle(TableStyle([
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [WHITE, LIGHT_GRAY]),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
        ("GRID",          (0, 0), (-1, -1), 0.4, BORDER_GRAY),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return tbl


# ── Amount spotlight ──────────────────────────────────────────────────────────

def _build_amount_spotlight(styles: dict, case: "RevenueCase") -> Table:
    days     = _days_overdue(case)
    late_fee = _late_fee(case.amount, days)
    total    = case.amount + late_fee

    cell = [
        Paragraph("TOTAL AMOUNT DUE", styles["amount_label"]),
        Paragraph(_fmt(total, case.currency), styles["amount_large"]),
        Paragraph(
            f"Original: {_fmt(case.amount, case.currency)}  +  "
            f"Late Fee: {_fmt(late_fee, case.currency)}",
            styles["amount_label"],
        ),
    ]
    tbl = Table([[cell]], colWidths=["100%"])
    tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), colors.HexColor("#FEF2F2")),
        ("TOPPADDING",    (0, 0), (-1, -1), 12),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
        ("BOX",           (0, 0), (-1, -1), 1.5, BRAND_RED),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return tbl


# ── Overdue breakdown table ───────────────────────────────────────────────────

def _build_overdue_table(styles: dict, case: "RevenueCase") -> Table:
    days     = _days_overdue(case)
    late_fee = _late_fee(case.amount, days)
    total    = case.amount + late_fee

    header_row = [Paragraph(h, styles["table_header"])
                  for h in ["Description", "Amount", "Days Overdue", "Status"]]

    status_style = styles["table_cell_red"] if case.status in ("PENDING", "ESCALATED") else styles["table_cell_bold"]

    data = [
        header_row,
        [Paragraph("Original Overdue Amount", styles["table_cell_bold"]),
         Paragraph(_fmt(case.amount, case.currency), styles["table_cell_red"]),
         Paragraph(str(days), styles["table_cell"]),
         Paragraph(case.status, status_style)],
        [Paragraph(f"Late Fee ({days}d @ 2%/mo)", styles["table_cell"]),
         Paragraph(_fmt(late_fee, case.currency), styles["table_cell_red"]),
         Paragraph("N/A", styles["table_cell"]),
         Paragraph("Accruing", styles["table_cell"])],
        [Paragraph("<b>TOTAL DUE</b>", styles["table_cell_bold"]),
         Paragraph(f"<b>{_fmt(total, case.currency)}</b>", styles["table_cell_red"]),
         Paragraph("N/A", styles["table_cell"]),
         Paragraph("OUTSTANDING", styles["table_cell_red"])],
    ]

    tbl = Table(data, colWidths=["40%", "22%", "20%", "18%"])
    tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0),  BRAND_DARK),
        ("TOPPADDING",    (0, 0), (-1, 0),  7),
        ("BOTTOMPADDING", (0, 0), (-1, 0),  7),
        ("ROWBACKGROUNDS",(0, 1), (-1, -2), [WHITE, LIGHT_GRAY]),
        ("TOPPADDING",    (0, 1), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 6),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
        ("BACKGROUND",    (0, -1), (-1, -1), colors.HexColor("#FEF2F2")),
        ("LINEABOVE",     (0, -1), (-1, -1), 1.2, BRAND_RED),
        ("BOX",           (0, 0), (-1, -1), 0.8, BORDER_GRAY),
        ("INNERGRID",     (0, 1), (-1, -1), 0.4, BORDER_GRAY),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return tbl


# ── Payment instructions ──────────────────────────────────────────────────────

def _build_payment_table(styles: dict, case: "RevenueCase") -> Table:
    days     = _days_overdue(case)
    late_fee = _late_fee(case.amount, days)
    total    = case.amount + late_fee
    ref_id   = str(case.id)[:8].upper()

    items = [
        ("Bank Name",        "AI Recovery Bank Ltd."),
        ("Account Number",   "XXXX-XXXX-4521"),
        ("IFSC Code",        "AIRB0001234"),
        ("UPI ID",           f"recovery+{ref_id}@airecovery.in"),
        ("Reference / Note", f"CASE-{ref_id}"),
        ("Amount Due",       _fmt(total, case.currency)),
        ("Online Portal",    f"http://localhost:8000/api/cases/{case.id}/pdf"),
    ]
    data = [[Paragraph(k, styles["label"]), Paragraph(v, styles["value"])] for k, v in items]
    tbl = Table(data, colWidths=["30%", "70%"])
    tbl.setStyle(TableStyle([
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [WHITE, LIGHT_GRAY]),
        ("TOPPADDING",     (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING",  (0, 0), (-1, -1), 5),
        ("LEFTPADDING",    (0, 0), (-1, -1), 8),
        ("RIGHTPADDING",   (0, 0), (-1, -1), 8),
        ("GRID",           (0, 0), (-1, -1), 0.4, BORDER_GRAY),
        ("VALIGN",         (0, 0), (-1, -1), "MIDDLE"),
        ("BACKGROUND",     (0, -1), (-1, -1), colors.HexColor("#EFF6FF")),
    ]))
    return tbl


# ── Legal notice ──────────────────────────────────────────────────────────────

_LEGAL_NOTICE = """
This is an official demand notice issued by <b>AI Revenue Recovery System</b> on behalf of
the creditor. Your account reflects an outstanding overdue balance as detailed above.

Pursuant to the terms and conditions agreed upon at the time of the original transaction,
payment in full is required <b>within 7 (seven) business days</b> of the date of this notice.
Failure to remit payment within the stipulated period may result in:
<br/><br/>
&nbsp;&nbsp;• Escalation to a registered debt-collection agency.<br/>
&nbsp;&nbsp;• Reporting to credit bureaus, which may adversely affect your credit score.<br/>
&nbsp;&nbsp;• Initiation of legal recovery proceedings as permissible under applicable law.<br/>
&nbsp;&nbsp;• Accrual of additional late fees and interest per the agreed payment terms.<br/>
<br/>
If you believe this notice has been sent in error, or if you have already made payment,
please contact our support desk immediately with your transaction reference. We are committed
to resolving this matter amicably.
<br/><br/>
<i>This is a legally binding demand notice. Please retain this document for your records.</i>
"""


# ── Main entry point ──────────────────────────────────────────────────────────

def generate_demand_letter_pdf(
    case: "RevenueCase",
    customer: "Customer",
) -> io.BytesIO:
    """
    Generate a professional demand-letter PDF for an overdue revenue case.

    Parameters
    ----------
    case     : RevenueCase ORM object with amount, currency, status, risk_level, etc.
    customer : Customer ORM object with name, email, phone.

    Returns
    -------
    io.BytesIO
        In-memory buffer (seek position 0) containing the rendered PDF bytes.
    """
    buf    = io.BytesIO()
    styles = _build_styles()

    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=1.8 * cm,
        rightMargin=1.8 * cm,
        topMargin=1.5 * cm,
        bottomMargin=2 * cm,
        title=f"Demand Letter - Case {str(case.id)[:8].upper()}",
        author="AI Revenue Recovery System",
        subject="Official Payment Demand Notice",
    )

    story: list = []

    # 1. Branded header
    story.append(_build_header(styles, case))
    story.append(Spacer(1, 12))

    # 2. Document title
    story.append(Paragraph("OFFICIAL PAYMENT DEMAND NOTICE", styles["doc_title"]))
    story.append(Paragraph(
        f"Case Reference: CASE-{str(case.id)[:8].upper()} | "
        f"Priority: {case.risk_level} | "
        f"Issued: {datetime.now(timezone.utc).strftime('%d %B %Y')}",
        styles["doc_subtitle"],
    ))
    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", thickness=1.5, color=BRAND_ACCENT, spaceAfter=8))

    # 3. Recipient info
    story.append(Paragraph("RECIPIENT INFORMATION", styles["section_label"]))
    story.append(_build_recipient_table(styles, customer))
    story.append(Spacer(1, 10))

    # 4. Amount spotlight
    story.append(_build_amount_spotlight(styles, case))
    story.append(Spacer(1, 10))

    # 5. Overdue breakdown
    story.append(Paragraph("OVERDUE ACCOUNT BREAKDOWN", styles["section_label"]))
    story.append(_build_overdue_table(styles, case))
    story.append(Spacer(1, 10))

    # 6. Legal notice
    story.append(Paragraph("FORMAL LEGAL NOTICE", styles["section_label"]))
    story.append(HRFlowable(width="100%", thickness=0.5, color=BRAND_ACCENT, spaceAfter=6))
    story.append(Paragraph(_LEGAL_NOTICE.strip(), styles["body_justify"]))
    story.append(Spacer(1, 10))

    # 7. Payment instructions
    story.append(Paragraph("PAYMENT INSTRUCTIONS", styles["section_label"]))
    story.append(_build_payment_table(styles, case))
    story.append(Spacer(1, 14))

    # 8. Footer
    story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER_GRAY, spaceBefore=4, spaceAfter=6))
    story.append(Paragraph(
        "AI Revenue Recovery System  •  Automated Collections Division  •  "
        "support@airecovery.in  •  This document is system-generated.",
        styles["footer"],
    ))
    story.append(Paragraph(
        f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}  "
        f"| Ref: {str(case.id).upper()}",
        styles["footer"],
    ))

    doc.build(story)
    buf.seek(0)
    return buf
