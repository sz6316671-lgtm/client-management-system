"""Invoice PDF generator (reportlab). Ye file `routes/invoice_pdf.py` mein rakhein."""
from decimal import Decimal
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

GREEN = colors.HexColor('#10b981')
DARK = colors.HexColor('#0f172a')
MUTED = colors.HexColor('#64748b')
LINE = colors.HexColor('#e2e8f0')
LIGHT_BG = colors.HexColor('#f8fafc')

COMPANY_NAME = 'SysZenix'  # apni company ka naam yahan badlein


def _money(value):
    return f"${Decimal(value or 0):,.2f}"


def _text(value, default='-'):
    """User data ko Paragraph ke liye safe banao (<, >, & escape)."""
    if value is None or str(value).strip() == '':
        return default
    return escape(str(value))


def _status_color(status):
    s = (status or '').strip().lower()
    if s == 'paid':
        return colors.HexColor('#059669')
    if s in ('overdue', 'unpaid'):
        return colors.HexColor('#dc2626')
    return colors.HexColor('#d97706')  # pending / partial / other


def build_invoice_pdf(invoice, client, payments):
    """
    invoice  : (id, invoice_number, amount, status, due_date, service_type, sub_service)
    client   : (name, email, phone, company)
    payments : list of (payment_date, payment_method, amount_paid, notes)
    Returns  : BytesIO (PDF)
    """
    _, inv_number, amount, status, due_date, service_type, sub_service = invoice
    c_name, c_email, c_phone, c_company = client

    total = Decimal(amount or 0)
    paid = sum((Decimal(p[2] or 0) for p in payments), Decimal(0))
    balance = max(total - paid, Decimal(0))

    styles = getSampleStyleSheet()
    base = ParagraphStyle('base', parent=styles['Normal'], fontName='Helvetica',
                          fontSize=9.5, leading=13, textColor=DARK)
    muted = ParagraphStyle('muted', parent=base, textColor=MUTED, fontSize=8.5)
    label = ParagraphStyle('label', parent=muted, fontName='Helvetica-Bold', fontSize=7.5)
    right = ParagraphStyle('right', parent=base, alignment=TA_RIGHT)
    h_brand = ParagraphStyle('brand', parent=base, fontName='Helvetica-Bold', fontSize=18)
    h_title = ParagraphStyle('title', parent=base, fontName='Helvetica-Bold', fontSize=22,
                             alignment=TA_RIGHT, textColor=GREEN)
    h_sec = ParagraphStyle('sec', parent=base, fontName='Helvetica-Bold', fontSize=11,
                           spaceBefore=14, spaceAfter=6)

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=16 * mm, bottomMargin=16 * mm,
        title=f'Invoice {inv_number}', author=COMPANY_NAME,
    )
    width = A4[0] - 36 * mm
    story = []

    # --- Header ---
    header = Table(
        [[Paragraph(COMPANY_NAME, h_brand), Paragraph('INVOICE', h_title)],
         [Paragraph('Client Management', muted), Paragraph(f'# {_text(inv_number)}', right)]],
        colWidths=[width * 0.55, width * 0.45],
    )
    header.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                                ('LINEBELOW', (0, 1), (-1, 1), 1.2, GREEN),
                                ('BOTTOMPADDING', (0, 1), (-1, 1), 8)]))
    story += [header, Spacer(1, 12)]

    # --- Bill To / Invoice details ---
    status_style = ParagraphStyle('st', parent=base, fontName='Helvetica-Bold',
                                  textColor=_status_color(status))
    bill_to = [Paragraph('BILL TO', label),
               Paragraph(f'<b>{_text(c_name)}</b>', base)]
    if c_company:
        bill_to.append(Paragraph(_text(c_company), base))
    bill_to += [Paragraph(_text(c_email), muted), Paragraph(_text(c_phone), muted)]

    details = Table(
        [[Paragraph('STATUS', label), Paragraph(_text(status, 'Pending').upper(), status_style)],
         [Paragraph('DUE DATE', label), Paragraph(_text(due_date, 'N/A'), base)]],
        colWidths=[22 * mm, 40 * mm],
    )
    details.setStyle(TableStyle([('TOPPADDING', (0, 0), (-1, -1), 2),
                                 ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
                                 ('LEFTPADDING', (0, 0), (-1, -1), 0)]))

    info = Table([[bill_to, details]], colWidths=[width * 0.55, width * 0.45])
    info.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'),
                              ('LEFTPADDING', (0, 0), (-1, -1), 0),
                              ('ALIGN', (1, 0), (1, 0), 'RIGHT')]))
    story += [info, Spacer(1, 14)]

    # --- Service line ---
    desc = f'<b>{_text(service_type, "Service")}</b>'
    if sub_service:
        desc += f'<br/><font color="#64748b">{_text(sub_service)}</font>'

    items = Table(
        [[Paragraph('DESCRIPTION', label), Paragraph('AMOUNT', ParagraphStyle('l2', parent=label, alignment=TA_RIGHT))],
         [Paragraph(desc, base), Paragraph(_money(total), right)]],
        colWidths=[width * 0.75, width * 0.25],
    )
    items.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), LIGHT_BG),
        ('LINEBELOW', (0, 0), (-1, -1), 0.5, LINE),
        ('TOPPADDING', (0, 0), (-1, -1), 8), ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    story.append(items)

    # --- Totals ---
    bal_color = '#dc2626' if balance > 0 else '#059669'
    totals = Table(
        [[Paragraph('Total', base), Paragraph(_money(total), right)],
         [Paragraph('Paid', base), Paragraph(_money(paid), right)],
         [Paragraph('<b>Balance Due</b>', base),
          Paragraph(f'<b><font color="{bal_color}">{_money(balance)}</font></b>', right)]],
        colWidths=[35 * mm, 30 * mm], hAlign='RIGHT',
    )
    totals.setStyle(TableStyle([('LINEABOVE', (0, 2), (-1, 2), 1, DARK),
                                ('TOPPADDING', (0, 0), (-1, -1), 4),
                                ('BOTTOMPADDING', (0, 0), (-1, -1), 4)]))
    story += [Spacer(1, 8), totals]

    # --- Payment history ---
    story.append(Paragraph('Payment History', h_sec))
    if payments:
        rows = [[Paragraph(h, label) for h in ('DATE', 'METHOD', 'NOTES')]
                + [Paragraph('AMOUNT', ParagraphStyle('l3', parent=label, alignment=TA_RIGHT))]]
        for p_date, p_method, p_amount, p_notes in payments:
            rows.append([Paragraph(_text(p_date), base), Paragraph(_text(p_method), base),
                         Paragraph(_text(p_notes), muted), Paragraph(_money(p_amount), right)])
        pay = Table(rows, colWidths=[width * 0.20, width * 0.22, width * 0.38, width * 0.20],
                    repeatRows=1)
        pay.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), LIGHT_BG),
            ('LINEBELOW', (0, 0), (-1, -1), 0.5, LINE),
            ('TOPPADDING', (0, 0), (-1, -1), 6), ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        story.append(pay)
    else:
        story.append(Paragraph('No payments recorded yet.', muted))

    story += [Spacer(1, 22), Paragraph(f'Thank you for your business. - {COMPANY_NAME}',
                                       ParagraphStyle('foot', parent=muted, alignment=1))]

    doc.build(story)
    buf.seek(0)
    return buf