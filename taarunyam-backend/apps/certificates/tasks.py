import logging
from celery import shared_task, chord, group
from django.db import transaction
from .models import Certificate
from apps.participants.models import Registration
from .services import CertificateService
from apps.authentication.models import AdminUser

logger = logging.getLogger(__name__)


@shared_task(bind=True)
def generate_single_certificate(self, registration_id_str, cert_type, prize_position, issued_by_id):
    """
    Task to generate a single PDF certificate.
    """
    try:
        reg = Registration.objects.get(registration_id=registration_id_str)
        admin = AdminUser.objects.filter(id=issued_by_id).first()

        svc = CertificateService()
        cert = svc.generate(
            registration=reg,
            cert_type=cert_type,
            prize_position=prize_position,
            issued_by=admin
        )
        return {'success': True, 'cert_id': str(cert.id), 'registration_id': registration_id_str}
    except Exception as e:
        logger.error(f"Error generating cert for {registration_id_str}: {e}")
        return {'success': False, 'registration_id': registration_id_str, 'error': str(e)}


@shared_task(bind=True)
def bulk_generate_callback(self, results, event_id, total):
    """
    Callback fired when a bulk generation chord completes.
    `results` is the list of return values from generate_single_certificate.
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


def start_bulk_generation(event_id, cert_type, admin_id):
    """
    Initiates a Celery Chord to generate certificates for all eligible participants
    in an event. Returns the group_id (or task_id of the chord).
    """
    regs = Registration.objects.filter(event_id=event_id)

    # Note: If cert_type == 'winner', we should only generate for those marked as winners
    if cert_type == 'winner':
        # Find which registrations are marked as winner in the cert table,
        # or we might need a separate flag in Registration.
        # Following frontend logic, winners are dictated by the UI toggle which creates/updates cert.
        # But if doing a generic bulk to "generate winner certs", it implies generating them for
        # existing winners. Let's filter registrations that have a winner certificate row pending or existing.
        # For simplicity, if bulk generating 'participation', we do all who are present.
        regs = regs.filter(is_present=True)

    if not regs.exists():
        return None

    tasks = [
        generate_single_certificate.s(
            r.registration_id, cert_type, getattr(r.certificate, 'prize_position', '') if hasattr(r, 'certificate') else '', admin_id
        ) for r in regs
    ]

    total = len(tasks)
    callback = bulk_generate_callback.s(str(event_id), total)

    res = chord(tasks)(callback)
    return res.id
