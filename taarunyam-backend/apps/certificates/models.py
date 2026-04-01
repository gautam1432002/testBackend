import uuid
from django.db import models


class Certificate(models.Model):
    TYPE_CHOICES = [
        ('participation', 'Participation'),
        ('winner', 'Winner'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    qr_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    registration = models.OneToOneField(
        'participants.Registration',
        on_delete=models.CASCADE,
        related_name='certificate'
    )
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='participation')
    prize_position = models.CharField(max_length=20, blank=True)
    pdf_path = models.FileField(
        upload_to='certificates/',
        null=True,
        blank=True
    )
    issued_at = models.DateTimeField(auto_now_add=True)
    issued_by = models.ForeignKey(
        'authentication.AdminUser',
        on_delete=models.SET_NULL,
        null=True,
        related_name='issued_certificates'
    )
    is_valid = models.BooleanField(default=True)

    class Meta:
        db_table = 'certificates'
        ordering = ['-issued_at']

    def __str__(self):
        return f"{self.type.title()} — {self.registration.registration_id}"

    @property
    def pdf_url(self):
        if self.pdf_path:
            return self.pdf_path.url
        return None
