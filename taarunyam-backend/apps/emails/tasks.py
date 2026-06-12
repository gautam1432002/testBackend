import logging
from django.utils import timezone
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from celery import shared_task, chord
from celery.exceptions import MaxRetriesExceededError
from cryptography.fernet import Fernet
import json
import base64

from django.conf import settings
from .models import EmailLog
from apps.certificates.models import Certificate
from apps.settings_app.models import SiteSettings

logger = logging.getLogger(__name__)


def get_smtp_credentials():
    """Retrieve decrypted SMTP password from SiteSettings."""
    try:
        site_settings = SiteSettings.objects.get(pk=1)
        fernet = Fernet(settings.FERNET_KEY)
        decrypted_password = fernet.decrypt(site_settings.smtp_password.encode()).decode()
        return {
            'host': site_settings.smtp_host,
            'port': site_settings.smtp_port,
            'user': site_settings.smtp_user,
            'password': decrypted_password,
            'from_email': site_settings.contact_email
        }
    except Exception as e:
        logger.error(f"Failed to get SMTP credentials: {e}")
        return None


@shared_task(bind=True, max_retries=3, default_retry_delay=5 * 60)
def send_certificate_email(self, log_id):
    """
    Celery task to send a single certificate email.
    Retries up to 3 times on failure.
    """
    try:
        log = EmailLog.objects.get(pk=log_id)
    except EmailLog.DoesNotExist:
        return {'success': False, 'error': 'EmailLog not found'}

    if log.status == 'sent':
        return {'success': True, 'log_id': log_id, 'message': 'Already sent'}

    cert = log.certificate

    smtp_creds = get_smtp_credentials()
    if not smtp_creds:
        log.status = 'failed'
        log.error_message = 'SMTP credentials not configured'
        log.save()
        return {'success': False, 'log_id': log_id, 'error': 'SMTP credentials not configured'}

    # Build Email Message
    participant_name = cert.registration.participant.full_name
    event_title = cert.registration.event.title

    subject = f"Your Certificate for {event_title}"
    body = (
        f"Dear {participant_name},\n\n"
        f"Thank you for participating in {event_title}.\n\n"
        f"View and download your official certificate using the secure link below:\n"
        f"{getattr(settings, 'FRONTEND_URL', 'http://localhost:5173')}/verify/{cert.qr_token}\n\n"
        f"Best regards,\n"
        f"The TAARUNYAM Team"
    )

    try:
        # We manually configure the connection using the DB credentials
        from django.core.mail.backends.smtp import EmailBackend
        backend = EmailBackend(
            host=smtp_creds['host'],
            port=smtp_creds['port'],
            username=smtp_creds['user'],
            password=smtp_creds['password'],
            use_tls=True,
            fail_silently=False,
        )

        email = EmailMessage(
            subject=subject,
            body=body,
            from_email=smtp_creds['from_email'],
            to=[log.recipient_email],
            connection=backend
        )
        email.send()

        log.status = 'sent'
        log.sent_at = timezone.now()
        log.error_message = ''
        log.save()
        return {'success': True, 'log_id': log_id}

    except Exception as exc:
        log.retry_count += 1
        log.error_message = str(exc)
        log.save()
        try:
            self.retry(exc=exc)
        except MaxRetriesExceededError:
            log.status = 'failed'
            log.save()
            return {'success': False, 'log_id': log_id, 'error': str(exc)}


@shared_task(bind=True)
def bulk_email_callback(self, results, event_id, total):
    """
    Callback fired when a bulk email chord completes.
    """
    successes = sum(1 for r in results if r.get('success'))
    failures = total - successes
    return {
        'status': 'finished',
        'event_id': event_id,
        'total': total,
        'success_count': successes,
        'failure_count': failures
    }


def start_bulk_email(event_id):
    """
    Initiates a Celery Chord to send certificates to all participants
    who have a generated certificate but haven't received it successfully yet.
    """
    # Find valid certificates for this event that haven't been successfully sent
    certs = Certificate.objects.filter(
        registration__event_id=event_id,
        is_valid=True
    ).exclude(
        email_logs__status='sent'
    ).select_related('registration__participant')

    if not certs.exists():
        return None

    tasks = []
    for cert in certs:
        # Check if there's a pending/failed log, if not create one
        log = cert.email_logs.exclude(status='sent').order_by('-created_at').first()
        if not log:
             log = EmailLog.objects.create(
                 certificate=cert,
                 recipient_email=cert.registration.participant.email
             )
        else:
             # Reset status to pending for retry
             log.status = 'pending'
             log.save()

        tasks.append(send_certificate_email.s(log.id))

    total = len(tasks)
    callback = bulk_email_callback.s(str(event_id), total)

    res = chord(tasks)(callback)
    return res.id


@shared_task
def retry_failed_emails():
    """
    Periodic task (Celery Beat) to retry emails that failed due to transient errors.
    """
    failed_logs = EmailLog.objects.filter(status='failed', retry_count__lt=5)
    for log in failed_logs:
        log.status = 'pending'
        log.save()
        send_certificate_email.delay(log.id)
