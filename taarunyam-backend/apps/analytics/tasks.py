import logging
from celery import shared_task
from django.core.cache import cache
from django.db.models import Count
from apps.participants.models import Registration, Participant
from apps.events.models import Event
from apps.certificates.models import Certificate

logger = logging.getLogger(__name__)


@shared_task
def refresh_analytics_cache():
    """
    Periodically queries and caches high-level analytics overviews.
    Runs every hour via Celery Beat.
    """
    try:
        total_participants = Participant.objects.count()
        total_winners = Certificate.objects.filter(type='winner').count()
        total_events = Event.objects.count()

        certificates_issued = Certificate.objects.count()
        certificates_sent = Certificate.objects.filter(email_logs__status='sent').distinct().count()

        # Count unique colleges
        unique_colleges = Participant.objects.values('college').distinct().count()

        data = {
            'totalParticipants': total_participants,
            'totalWinners': total_winners,
            'totalEvents': total_events,
            'certificatesIssued': certificates_issued,
            'certificatesSent': certificates_sent,
            'uniqueColleges': unique_colleges
        }

        # Cache for 65 minutes to ensure overlap with 1hr beat schedule
        cache.set('analytics_overview', data, timeout=65 * 60)
        logger.info("Analytics cache refreshed successfully.")
        return data
    except Exception as e:
        logger.error(f"Error refreshing analytics cache: {e}")
        return None
