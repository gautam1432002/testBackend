from django.core.management.base import BaseCommand
from apps.settings_app.models import SiteSettings


DEFAULT_CERT_SETTINGS = {
    "organizerName": "TAARUNYAM INSTITUTE OF TECHNOLOGY",
    "eventName": "TAARUNYAM 2026",
    "brandName": "TAARUNYAM",
    "participation": {
        "title": "CERTIFICATE OF PARTICIPATION",
        "mainText": "This is to certify that",
        "subText": "has successfully participated in",
        "eventDetails": "held during the Tech Fest TAARUNYAM 2026."
    },
    "winner": {
        "title": "CERTIFICATE OF EXCELLENCE",
        "mainText": "This is to certify that",
        "achievementText": "has secured",
        "eventDetails": "in the flagship coding competition held during TAARUNYAM 2026."
    },
    "authorities": {
        "coordinator": {
            "name": "Dr. Arvind Sharma",
            "title": "Faculty Coordinator",
        },
        "hod": {
            "name": "Prof. R. K. Gupta",
            "title": "Head of Department (CSE)",
        },
        "principal": {
            "name": "Dr. V. N. Patel",
            "title": "Principal",
        }
    }
}


class Command(BaseCommand):
    help = 'Initializes the SiteSettings singleton with default certificate template texts.'

    def handle(self, *args, **options):
        settings_obj, created = SiteSettings.objects.get_or_create(id=1)

        if not settings_obj.cert_settings:
            settings_obj.cert_settings = DEFAULT_CERT_SETTINGS
            settings_obj.save()
            self.stdout.write(self.style.SUCCESS('Successfully initialized default CertSettings JSON payload.'))
        else:
            self.stdout.write(self.style.SUCCESS('SiteSettings already has cert configuration. Skipping.'))
