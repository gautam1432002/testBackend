"""
CertificateService — ReportLab PDF generation.
Matches the visual design of the existing React ParticipationCertificate and WinnerCertificate components.
"""
import io
import os
import qrcode
from datetime import datetime

from django.conf import settings
from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib.units import mm, inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, Image as RLImage
)
from reportlab.pdfgen import canvas as rl_canvas

from apps.certificates.models import Certificate
from apps.participants.models import Registration
from apps.settings_app.models import SiteSettings


PAGE_WIDTH, PAGE_HEIGHT = landscape(A4)

# ─── Color Palette ────────────────────────────────────────────────────────────
BLUE_DARK = colors.HexColor('#1e3a5f')
BLUE_MID = colors.HexColor('#2563eb')
BLUE_LIGHT = colors.HexColor('#3b82f6')
GOLD = colors.HexColor('#d4af37')
GOLD_LIGHT = colors.HexColor('#ffd700')
WHITE = colors.white
GREY = colors.HexColor('#64748b')
BLACK = colors.HexColor('#0f172a')


def _get_site_settings():
    try:
        return SiteSettings.objects.get(pk=1)
    except SiteSettings.DoesNotExist:
        return None


def _build_qr_image(url: str, size_mm: int = 25) -> RLImage:
    qr = qrcode.QRCode(
        version=2,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=4,
        border=2
    )
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color='black', back_color='white')
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return RLImage(buf, width=size_mm * mm, height=size_mm * mm)


def _draw_border(c, kind='participation'):
    """Draw decorative page borders."""
    c.saveState()
    margin = 12 * mm
    if kind == 'winner':
        c.setStrokeColor(GOLD)
        c.setLineWidth(3)
        c.rect(margin, margin, PAGE_WIDTH - 2 * margin, PAGE_HEIGHT - 2 * margin)
        c.setStrokeColor(GOLD_LIGHT)
        c.setLineWidth(1)
        c.rect(margin + 4, margin + 4,
               PAGE_WIDTH - 2 * margin - 8, PAGE_HEIGHT - 2 * margin - 8)
    else:
        c.setStrokeColor(BLUE_MID)
        c.setLineWidth(3)
        c.rect(margin, margin, PAGE_WIDTH - 2 * margin, PAGE_HEIGHT - 2 * margin)
        c.setStrokeColor(BLUE_LIGHT)
        c.setLineWidth(1)
        c.rect(margin + 4, margin + 4,
               PAGE_WIDTH - 2 * margin - 8, PAGE_HEIGHT - 2 * margin - 8)
    c.restoreState()


class NumberedCanvas(rl_canvas.Canvas):
    """Canvas subclass to draw borders on each page."""
    def __init__(self, *args, cert_type='participation', **kwargs):
        super().__init__(*args, **kwargs)
        self._cert_type = cert_type

    def showPage(self):
        _draw_border(self, self._cert_type)
        super().showPage()


class CertificateService:
    """
    Generates PDF certificates using ReportLab.
    Call generate(registration_id, cert_type, prize_position, issued_by) to produce
    a Certificate model instance with the PDF saved to MEDIA_ROOT.
    """

    def generate(self, registration: Registration, cert_type: str,
                 prize_position: str, issued_by) -> Certificate:
        """
        Create or update the Certificate row and generate the PDF.
        Returns the saved Certificate instance.
        """
        from django.core.files.base import ContentFile

        settings_obj = _get_site_settings()
        cert_settings = settings_obj.cert_settings if settings_obj else {}

        # Build or fetch Certificate row
        cert, _ = Certificate.objects.get_or_create(
            registration=registration,
            defaults={
                'type': cert_type,
                'prize_position': prize_position,
                'issued_by': issued_by,
            }
        )
        cert.type = cert_type
        cert.prize_position = prize_position
        cert.issued_by = issued_by

        # Generate PDF binary
        pdf_binary = self._render_pdf(registration, cert, cert_settings)

        # Save to storage
        filename = f'certificates/{registration.event.slug}/{cert.qr_token}.pdf'
        cert.pdf_path.save(filename, ContentFile(pdf_binary), save=False)
        cert.save()
        return cert

    def _render_pdf(self, registration: Registration, cert: Certificate,
                    cert_settings: dict) -> bytes:
        buf = io.BytesIO()
        is_winner = cert.type == 'winner'

        # Build verify URL for QR
        base_url = getattr(settings, 'SITE_URL', 'http://localhost:8000')
        verify_url = f'{base_url}/api/verify/{cert.qr_token}/'

        doc = SimpleDocTemplate(
            buf,
            pagesize=landscape(A4),
            rightMargin=20 * mm,
            leftMargin=20 * mm,
            topMargin=18 * mm,
            bottomMargin=18 * mm,
        )

        styles = getSampleStyleSheet()
        story = []

        accent_color = GOLD if is_winner else BLUE_MID
        heading_color = BLACK

        # ── Header ──────────────────────────────────────────────────────────
        org_name = cert_settings.get('organizerName', 'TAARUNYAM INSTITUTE OF TECHNOLOGY')
        event_name = cert_settings.get('eventName', 'TAARUNYAM 2026')
        brand = cert_settings.get('brandName', 'TAARUNYAM')

        org_style = ParagraphStyle('org', parent=styles['Normal'],
                                   fontSize=11, textColor=GREY, alignment=TA_CENTER,
                                   spaceAfter=2)
        brand_style = ParagraphStyle('brand', parent=styles['Normal'],
                                     fontSize=28, textColor=accent_color,
                                     fontName='Helvetica-Bold', alignment=TA_CENTER,
                                     spaceAfter=2)
        event_style = ParagraphStyle('event', parent=styles['Normal'],
                                     fontSize=13, textColor=BLUE_DARK,
                                     alignment=TA_CENTER, spaceAfter=6)

        story.append(Paragraph(org_name.upper(), org_style))
        story.append(Paragraph(brand, brand_style))
        story.append(Paragraph(event_name, event_style))
        story.append(HRFlowable(width='100%', thickness=2, color=accent_color, spaceAfter=10))

        # ── Title ────────────────────────────────────────────────────────────
        title_text = 'CERTIFICATE OF EXCELLENCE' if is_winner else 'CERTIFICATE OF PARTICIPATION'
        if is_winner and cert.prize_position:
            title_text = f'CERTIFICATE OF EXCELLENCE — {cert.prize_position} PLACE'

        title_style = ParagraphStyle('title', parent=styles['Normal'],
                                     fontSize=18, textColor=heading_color,
                                     fontName='Helvetica-Bold', alignment=TA_CENTER,
                                     spaceAfter=14)
        story.append(Paragraph(title_text, title_style))

        # ── Body ─────────────────────────────────────────────────────────────
        intro_text = cert_settings.get(
            'winner' if is_winner else 'participation', {}
        ).get('mainText', 'This is to certify that')

        intro_style = ParagraphStyle('intro', parent=styles['Normal'],
                                     fontSize=12, textColor=GREY, alignment=TA_CENTER,
                                     spaceAfter=4)
        story.append(Paragraph(intro_text, intro_style))

        name_style = ParagraphStyle('name', parent=styles['Normal'],
                                    fontSize=32, fontName='Helvetica-Bold',
                                    textColor=accent_color, alignment=TA_CENTER,
                                    spaceAfter=6)
        story.append(Paragraph(registration.participant.full_name.upper(), name_style))

        event_date = registration.event.event_date.strftime('%B %d, %Y')
        event_detail_text = (
            f'for outstanding performance in <b>{registration.event.title}</b> held on {event_date}'
            if is_winner else
            f'for participating in <b>{registration.event.title}</b> held on {event_date}'
        )
        detail_style = ParagraphStyle('detail', parent=styles['Normal'],
                                      fontSize=12, textColor=GREY, alignment=TA_CENTER,
                                      spaceAfter=16)
        story.append(Paragraph(event_detail_text, detail_style))

        # ── Footer: Signatures + QR ──────────────────────────────────────────
        authorities = cert_settings.get('authorities', {})
        coord = authorities.get('coordinator', {})
        hod = authorities.get('hod', {})
        principal = authorities.get('principal', {})

        qr_img = _build_qr_image(verify_url, size_mm=25)

        def _sig_cell(auth: dict) -> list:
            name = auth.get('name', '—')
            title = auth.get('title', '')
            return [
                HRFlowable(width=40 * mm, thickness=1, color=GREY),
                Paragraph(f'<b>{name}</b>', ParagraphStyle(
                    'sn', parent=styles['Normal'], fontSize=9,
                    textColor=BLACK, alignment=TA_CENTER
                )),
                Paragraph(title, ParagraphStyle(
                    'st', parent=styles['Normal'], fontSize=8,
                    textColor=GREY, alignment=TA_CENTER
                )),
            ]

        id_para = Paragraph(
            f'<font size=7 color=grey>ID: {cert.qr_token}</font>',
            ParagraphStyle('id_p', parent=styles['Normal'], alignment=TA_CENTER)
        )

        footer_data = [[
            [qr_img, id_para],
            _sig_cell(coord),
            _sig_cell(hod),
            _sig_cell(principal),
        ]]

        footer_table = Table(footer_data, colWidths=[35 * mm, 60 * mm, 60 * mm, 60 * mm])
        footer_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'BOTTOM'),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('PADDING', (0, 0), (-1, -1), 4),
        ]))
        story.append(footer_table)

        def make_canvas(*args, **kwargs):
            return NumberedCanvas(*args, cert_type=cert.type, **kwargs)

        doc.build(story, canvasmaker=make_canvas)
        buf.seek(0)
        return buf.read()
