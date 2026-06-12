from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit

from apps.certificates.models import Certificate
from .models import VerificationLog


def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


class PublicVerifyView(APIView):
    permission_classes = [AllowAny]

    @method_decorator(ratelimit(key='ip', rate='30/m', method='GET', block=True))
    def get(self, request, qr_token):
        """
        Public endpoint to verify a certificate by its UUID qr_token.
        Matches the React CertificateVerifyResponse interface.
        """
        cert = None
        reg = None
        is_registration = False

        try:
            cert = Certificate.objects.select_related(
                'registration__participant',
                'registration__event'
            ).get(qr_token=qr_token)
        except (Certificate.DoesNotExist, ValueError):
            from apps.participants.models import Registration
            try:
                reg = Registration.objects.select_related(
                    'participant', 'event'
                ).get(registration_id=qr_token)
                is_registration = True
            except Registration.DoesNotExist:
                return Response({
                    'success': False,
                    'data': {'isValid': False},
                    'message': 'Invalid Certificate or Registration ID.'
                }, status=404)

        if not is_registration and not cert.is_valid:
             return Response({
                 'success': False,
                 'data': {'isValid': False},
                 'message': 'This certificate has been revoked.'
             }, status=400)

        # Log the verification safely if it's a certificate
        if not is_registration:
            try:
                VerificationLog.objects.create(
                    certificate=cert,
                    ip_address=get_client_ip(request),
                    method='qr'
                )
            except Exception:
                pass # Don't let logging failure break the response

        from apps.settings_app.models import SiteSettings
        cert_settings = {}
        try:
            settings_obj = SiteSettings.objects.get(pk=1)
            cert_settings = settings_obj.cert_settings
        except:
            pass

        # Construct payload
        if is_registration:
            participant = reg.participant
            event = reg.event
            data = {
                'isValid': True,
                'certificateId': reg.registration_id,
                'participant': {
                    'name': participant.full_name,
                    'college': participant.college,
                },
                'event': {
                    'title': event.title,
                    'date': event.event_date.strftime('%B %d, %Y') if event.event_date else '',
                },
                'type': 'entry-pass',
                'issuedAt': reg.registration_date.isoformat(),
                'certSettings': cert_settings,
            }
            message = 'Valid Registration Pass.'
        else:
            reg = cert.registration
            participant = reg.participant
            event = reg.event
            data = {
                'isValid': True,
                'certificateId': str(cert.qr_token),
                'participant': {
                    'name': participant.full_name,
                    'college': participant.college,
                },
                'event': {
                    'title': event.title,
                    'date': event.event_date.strftime('%B %d, %Y') if event.event_date else '',
                },
                'type': cert.type,
                'issuedAt': cert.issued_at.isoformat(),
                'certSettings': cert_settings,
            }
            message = 'Certificate is valid.'

        return Response({'success': True, 'data': data, 'message': message})

