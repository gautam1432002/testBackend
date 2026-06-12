"""
distribute.py — Standalone SMTP Certificate Email Distributor
=============================================================
This module is COMPLETELY SEPARATE from the authentication password reset system.
It imports nothing from apps.authentication and shares no code with it.

Responsibility:
  - Retrieve SMTP credentials from SiteSettings (Fernet-encrypted password)
  - Fall back to Django settings env-based EMAIL_HOST_PASSWORD if DB credentials
    are not configured
  - Auto-generate certificate PDFs if they don't already exist
  - Send the certificate email with the PDF attached
  - Log every attempt (success or failure) in EmailLog
  - Return per-participant result dicts so the caller can report back to the frontend
"""

import logging
import smtplib
from datetime import datetime, timezone
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any

from django.conf import settings

logger = logging.getLogger(__name__)


# ─── SMTP Helpers (completely independent from auth) ──────────────────────────

def _get_smtp_config() -> dict[str, Any]:
    """
    Load SMTP configuration from the SiteSettings singleton.
    Falls back gracefully to Django's settings.EMAIL_* env vars.
    Returns a dict with: host, port, user, password, from_email
    """
    from apps.settings_app.models import SiteSettings

    obj = SiteSettings.load()

    host = obj.smtp_host or getattr(settings, 'EMAIL_HOST', 'smtp.gmail.com')
    port = obj.smtp_port or getattr(settings, 'EMAIL_PORT', 587)
    user = obj.smtp_user or getattr(settings, 'EMAIL_HOST_USER', '')
    from_email = obj.contact_email or user

    # Decrypt password from DB
    password = ''
    if obj.smtp_password:
        try:
            from cryptography.fernet import Fernet
            fernet = Fernet(settings.FERNET_KEY)
            password = fernet.decrypt(obj.smtp_password.encode()).decode()
        except Exception as e:
            logger.warning(f"[Distribute] Failed to decrypt SMTP password: {e}. Falling back to env.")
            password = getattr(settings, 'EMAIL_HOST_PASSWORD', '')
    else:
        password = getattr(settings, 'EMAIL_HOST_PASSWORD', '')

    return {
        'host': host,
        'port': port,
        'user': user,
        'password': password,
        'from_email': from_email,
    }


def _open_smtp_connection(config: dict):
    """Open and return an authenticated SMTP connection."""
    conn = smtplib.SMTP(config['host'], config['port'], timeout=30)
    conn.ehlo()
    conn.starttls()
    conn.ehlo()
    if config['user'] and config['password']:
        conn.login(config['user'], config['password'])
    return conn


def _build_html_email(
    participant_name: str,
    event_title: str,
    is_winner: bool,
    template: dict,
    qr_token: str,
) -> str:
    """Build an HTML email body from a template dict."""
    greeting = template.get('greeting', 'Dear Participant,')
    body = template.get('body', 'Please find your certificate attached.')
    closing = template.get('closing', 'Best Regards,')
    signature = template.get('signature', 'The TAARUNYAM Organizing Team')

    cert_type = 'Winner Certificate' if is_winner else 'Certificate of Participation'

    html = f"""
<html>
<body style="font-family: Arial, sans-serif; color: #1e1e2e; background: #f9f9f9; padding: 0; margin: 0;">
  <div style="max-width: 600px; margin: 40px auto; background: #ffffff; border-radius: 12px;
              box-shadow: 0 4px 24px rgba(0,0,0,0.08); overflow: hidden;">
    <!-- Header -->
    <div style="background: linear-gradient(135deg, #1e3a5f 0%, #2563eb 100%); padding: 40px 32px; text-align: center;">
      <h1 style="color: #ffffff; font-size: 28px; margin: 0; letter-spacing: 3px; font-weight: 900;">
        TAARUNYAM 2026
      </h1>
      <p style="color: rgba(255,255,255,0.8); margin: 8px 0 0; font-size: 13px; letter-spacing: 1px;">
        {event_title}
      </p>
    </div>

    <!-- Body -->
    <div style="padding: 40px 32px;">
      <p style="font-size: 16px; color: #374151; margin: 0 0 16px;">{greeting}</p>

      <p style="font-size: 16px; color: #374151; line-height: 1.7; margin: 0 0 20px;">
        {body}
      </p>

      <!-- Highlight box -->
      <div style="background: {"linear-gradient(135deg, #fef9c3, #fde68a)" if is_winner else "linear-gradient(135deg, #eff6ff, #dbeafe)"};
                  border-left: 4px solid {"#d97706" if is_winner else "#2563eb"};
                  border-radius: 8px; padding: 20px 24px; margin: 24px 0;">
        <p style="margin: 0; font-size: 15px; color: {"#78350f" if is_winner else "#1e3a5f"}; font-weight: bold;">
          {"🏆 " if is_winner else "📄 "}{cert_type}
        </p>
        <p style="margin: 8px 0 0; font-size: 14px; color: {"#92400e" if is_winner else "#1d4ed8"};">
          Awarded to: <strong>{participant_name}</strong>
        </p>
      </div>

      <p style="font-size: 14px; color: #6b7280; margin: 0 0 8px;">
        View and download your official certificate using the secure link below:
      </p>
      
      <div style="text-align: center; margin: 32px 0;">
        <a href="{getattr(settings, 'FRONTEND_URL', 'http://localhost:5173')}/verify/{qr_token}" 
           style="background-color: #2563eb; color: #ffffff; padding: 14px 28px; 
                  text-decoration: none; border-radius: 8px; font-weight: bold; 
                  display: inline-block; box-shadow: 0 4px 6px -1px rgba(37, 99, 235, 0.2);">
          View & Download Certificate
        </a>
      </div>
    </div>

    <!-- Footer -->
    <div style="padding: 24px 32px; background: #f3f4f6; border-top: 1px solid #e5e7eb; text-align: center;">
      <p style="color: #374151; font-size: 14px; margin: 0;">{closing}</p>
      <p style="color: #1d4ed8; font-size: 15px; font-weight: bold; margin: 6px 0 0;">{signature}</p>
      <p style="color: #9ca3af; font-size: 12px; margin: 12px 0 0;">
        TAARUNYAM 2026 — The Ultimate Tech Championship
      </p>
    </div>
  </div>
</body>
</html>
"""
    return html


# ─── PDF Auto-Generation ──────────────────────────────────────────────────────

def _ensure_certificate_pdf(registration, cert_type: str = None) -> tuple:
    """
    Ensure a Certificate row exists.
    Returns (certificate, error_string_or_None).
    """
    from apps.certificates.models import Certificate
    from apps.certificates.services import CertificateService

    correct_type = cert_type if cert_type is not None else (
        'winner' if registration.is_winner else 'participation'
    )

    try:
        cert = Certificate.objects.get(registration=registration)
        if cert.type != correct_type:
            cert.type = correct_type
            cert.save()
        return cert, None
    except Certificate.DoesNotExist:
        try:
            svc = CertificateService()
            cert = svc.generate(
                registration=registration,
                cert_type=correct_type,
                prize_position='',
                issued_by=None,
            )
            return cert, None
        except Exception as e:
            return None, str(e)


# ─── Core Send Function (used by the view) ────────────────────────────────────

def distribute_emails(registration_ids: list[str], template: dict) -> list[dict]:
    """
    Send certificate emails to a list of registration IDs.
    Auto-generates PDFs if they don't already exist.
    Logs every attempt.

    Args:
        registration_ids: List of registration_id strings
        template: Dict with keys: subject, greeting, body, closing, signature

    Returns:
        List of per-participant result dicts:
        {
            'registration_id': str,
            'participant_name': str,
            'email': str,
            'status': 'sent' | 'failed',
            'error': str | None,
        }
    """
    from apps.participants.models import Registration
    from apps.emails.models import EmailLog

    if not registration_ids:
        return []

    # Load SMTP config once
    try:
        smtp_config = _get_smtp_config()
    except Exception as e:
        logger.error(f"[Distribute] Failed to load SMTP config: {e}")
        return [
            {
                'registration_id': rid,
                'participant_name': '',
                'email': '',
                'status': 'failed',
                'error': f'SMTP configuration error: {e}',
            }
            for rid in registration_ids
        ]

    subject = template.get('subject', 'Your TAARUNYAM 2026 Certificate')

    results = []

    # Open one persistent SMTP connection for all recipients
    smtp_conn = None
    try:
        smtp_conn = _open_smtp_connection(smtp_config)
    except Exception as e:
        logger.error(f"[Distribute] SMTP connection failed: {e}")
        smtp_conn = None

    for reg_id in registration_ids:
        result = {
            'registration_id': reg_id,
            'participant_name': '',
            'email': '',
            'status': 'failed',
            'error': None,
        }

        # ── 1. Load registration ──────────────────────────────────────
        try:
            reg = Registration.objects.select_related('participant', 'event').get(
                registration_id=reg_id
            )
            result['participant_name'] = reg.participant.full_name
            result['email'] = reg.participant.email
        except Registration.DoesNotExist:
            result['error'] = f'Registration {reg_id} not found.'
            results.append(result)
            continue

        # ── 2. Ensure PDF exists ──────────────────────────────────────
        cert, pdf_error = _ensure_certificate_pdf(reg)
        if pdf_error or not cert:
            result['error'] = pdf_error or 'PDF generation failed.'
            results.append(result)
            # Log failure
            _log_email_attempt(cert, reg, result['email'], 'failed', pdf_error or 'PDF generation failed.')
            continue

        # ── 3. Build email message ────────────────────────────────────
        try:
            is_winner = cert.type == 'winner'
            html_body = _build_html_email(
                participant_name=reg.participant.full_name,
                event_title=reg.event.title,
                is_winner=is_winner,
                template=template,
                qr_token=str(cert.qr_token),
            )

            msg = MIMEMultipart('mixed')
            msg['Subject'] = subject
            msg['From'] = smtp_config['from_email']
            msg['To'] = reg.participant.email

            # HTML part
            alt_part = MIMEMultipart('alternative')
            alt_part.attach(MIMEText(html_body, 'html', 'utf-8'))
            msg.attach(alt_part)

        except Exception as e:
            result['error'] = f'Failed to build email: {e}'
            results.append(result)
            _log_email_attempt(cert, reg, result['email'], 'failed', str(e))
            continue

        # ── 4. Send ───────────────────────────────────────────────────
        try:
            if smtp_conn is None:
                # Try reconnecting
                smtp_conn = _open_smtp_connection(smtp_config)

            smtp_conn.sendmail(smtp_config['from_email'], [reg.participant.email], msg.as_bytes())
            result['status'] = 'sent'
            result['error'] = None
            _log_email_attempt(cert, reg, reg.participant.email, 'sent', '')

        except smtplib.SMTPServerDisconnected:
            # Connection dropped — reconnect once and retry
            try:
                smtp_conn = _open_smtp_connection(smtp_config)
                smtp_conn.sendmail(smtp_config['from_email'], [reg.participant.email], msg.as_bytes())
                result['status'] = 'sent'
                result['error'] = None
                _log_email_attempt(cert, reg, reg.participant.email, 'sent', '')
            except Exception as retry_e:
                result['error'] = f'SMTP error (retry): {retry_e}'
                _log_email_attempt(cert, reg, reg.participant.email, 'failed', str(retry_e))

        except Exception as e:
            result['error'] = f'Send error: {e}'
            _log_email_attempt(cert, reg, reg.participant.email, 'failed', str(e))

        results.append(result)

    # Close connection
    if smtp_conn:
        try:
            smtp_conn.quit()
        except Exception:
            pass

    return results


def _log_email_attempt(cert, reg, recipient_email: str, status: str, error_msg: str):
    """Create or update an EmailLog entry for this send attempt."""
    from apps.emails.models import EmailLog

    if cert is None:
        return  # Can't log without a certificate FK

    try:
        # Get latest non-sent log or create new
        log = cert.email_logs.exclude(status='sent').order_by('-created_at').first()
        if not log:
            log = EmailLog(certificate=cert, recipient_email=recipient_email)

        log.status = status
        log.error_message = error_msg
        if status == 'sent':
            log.sent_at = datetime.now(timezone.utc)
        log.save()
    except Exception as e:
        logger.error(f"[Distribute] Failed to write EmailLog: {e}")
