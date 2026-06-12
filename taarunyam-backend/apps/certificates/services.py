"""
CertificateService — Simplified
===============================
This module now ONLY generates the Certificate database row (metadata).
PDF generation has been entirely offloaded to the frontend (html2canvas) 
to guarantee 100% visual fidelity with the React CSS. 
"""
from apps.certificates.models import Certificate
from apps.participants.models import Registration

class CertificateService:
    """
    Generates PDF certificate metadata.
    Call generate() to produce a Certificate model instance.
    """
    def generate(self, registration: Registration, cert_type: str,
                 prize_position: str, issued_by) -> Certificate:
        """
        Create or update the Certificate row.
        Returns the saved Certificate instance.
        """
        cert, created = Certificate.objects.get_or_create(
            registration=registration,
            defaults={
                'type': cert_type,
                'prize_position': prize_position,
                'issued_by': issued_by,
            }
        )
        
        # If the type or prize changed, update it
        if not created and (cert.type != cert_type or cert.prize_position != prize_position):
            cert.type = cert_type
            cert.prize_position = prize_position
            cert.issued_by = issued_by
            cert.save()
            
        return cert
