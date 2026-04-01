import uuid
from django.db import models


class Participant(models.Model):
    YEAR_CHOICES = [
        ('1st', '1st Year'),
        ('2nd', '2nd Year'),
        ('3rd', '3rd Year'),
        ('4th', '4th Year'),
    ]
    GENDER_CHOICES = [
        ('M', 'Male'),
        ('F', 'Female'),
        ('O', 'Other'),
        ('P', 'Prefer not to say'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    full_name = models.CharField(max_length=255)
    email = models.EmailField(unique=True,
                              db_index=True)
    phone = models.CharField(max_length=20)
    college = models.CharField(max_length=255)
    department = models.CharField(max_length=255, blank=True)
    year_of_study = models.CharField(max_length=5, choices=YEAR_CHOICES, blank=True)
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'participants'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.full_name} <{self.email}>"


class Registration(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    participant = models.ForeignKey(
        Participant, on_delete=models.CASCADE, related_name='registrations'
    )
    event = models.ForeignKey(
        'events.Event', on_delete=models.CASCADE, related_name='registrations'
    )
    registration_id = models.CharField(max_length=20, unique=True, blank=True)
    registration_date = models.DateTimeField(auto_now_add=True)
    is_present = models.BooleanField(default=False)
    notes = models.TextField(blank=True)

    class Meta:
        db_table = 'registrations'
        unique_together = [['participant', 'event']]
        ordering = ['-registration_date']

    def save(self, *args, **kwargs):
        if not self.registration_id:
            self.registration_id = self._generate_registration_id()
        super().save(*args, **kwargs)

    def _generate_registration_id(self):
        """Generate TAR-{YEAR}-{3-digit sequential number}."""
        from django.utils import timezone
        year = timezone.now().year
        # Count ALL registrations for this year
        existing_count = Registration.objects.filter(
            registration_date__year=year
        ).count()
        seq = existing_count + 1
        return f'TAR-{year}-{seq:03d}'

    def __str__(self):
        return f"{self.registration_id}: {self.participant.full_name} @ {self.event.title}"

    @property
    def is_winner(self):
        return hasattr(self, 'certificate') and self.certificate.type == 'winner'

    @property
    def certificate_issued(self):
        return hasattr(self, 'certificate')

    @property
    def certificate_sent_at(self):
        if not self.certificate_issued:
            return None
        cert = self.certificate
        log = cert.email_logs.filter(status='sent').order_by('-sent_at').first()
        return log.sent_at.isoformat() if log else None
