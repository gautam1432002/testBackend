import uuid
from django.db import models


class VerificationLog(models.Model):
    METHOD_CHOICES = [
        ('qr', 'QR Scan'),
        ('manual', 'Manual Entry'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    certificate = models.ForeignKey(
        'certificates.Certificate',
        on_delete=models.CASCADE,
        related_name='verifications'
    )
    verified_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    method = models.CharField(max_length=10, choices=METHOD_CHOICES, default='qr')

    class Meta:
        db_table = 'verification_logs'
        ordering = ['-verified_at']

    def __str__(self):
        return f"Verified {self.certificate.qr_token} at {self.verified_at}"
