from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.core.mail import EmailMessage
from cryptography.fernet import Fernet

from django.conf import settings
from apps.authentication.permissions import IsSuperAdmin
from .models import SiteSettings
from .serializers import PublicSiteSettingsSerializer, AdminSiteSettingsSerializer, SMTPTestSerializer


def _success(data, message='', status_code=status.HTTP_200_OK):
    return Response({'success': True, 'data': data, 'message': message}, status=status_code)


class PublicSettingsView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        settings_obj = SiteSettings.load()
        serializer = PublicSiteSettingsSerializer(settings_obj)
        return _success(serializer.data)


class AdminSettingsView(APIView):
    """Note: Usually GET can be IsAdmin, but PUT is restricted to IsSuperAdmin."""
    def get_permissions(self):
        if self.request.method in ['PUT', 'PATCH']:
            return [IsSuperAdmin()]
        from apps.authentication.permissions import IsAdmin
        return [IsAdmin()]

    def get(self, request):
        settings_obj = SiteSettings.load()
        serializer = AdminSiteSettingsSerializer(settings_obj)
        return _success(serializer.data)

    def put(self, request):
        settings_obj = SiteSettings.load()
        serializer = AdminSiteSettingsSerializer(settings_obj, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        if 'smtp_password' in serializer.validated_data:
            pw = serializer.validated_data.pop('smtp_password')
            if pw:
                # Password encryption logic is handled securely in model save()
                settings_obj.smtp_password = pw
            elif pw == '':
                settings_obj.smtp_password = ''

        for attr, value in serializer.validated_data.items():
            setattr(settings_obj, attr, value)

        settings_obj.save()

        # Re-fetch for response
        settings_obj.refresh_from_db()
        return _success(AdminSiteSettingsSerializer(settings_obj).data, 'Settings updated successfully.')


class SMTPTestView(APIView):
    permission_classes = [IsSuperAdmin]

    def post(self, request):
        serializer = SMTPTestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        test_email = serializer.validated_data['test_email']

        settings_obj = SiteSettings.load()
        if not settings_obj.smtp_user or not settings_obj.smtp_password:
            return Response({'success': False, 'data': {}, 'message': 'SMTP credentials incomplete.'}, status=400)

        # Decrypt password for test execution
        try:
            fernet = Fernet(settings.FERNET_KEY)
            decrypted_password = fernet.decrypt(settings_obj.smtp_password.encode()).decode()
        except Exception:
             return Response({'success': False, 'data': {}, 'message': 'Failed to decrypt SMTP password.'}, status=500)

        try:
            from django.core.mail.backends.smtp import EmailBackend
            backend = EmailBackend(
                host=settings_obj.smtp_host,
                port=settings_obj.smtp_port,
                username=settings_obj.smtp_user,
                password=decrypted_password,
                use_tls=True,
                fail_silently=False,
            )

            email = EmailMessage(
                subject='TAARUNYAM SMTP Test',
                body='This is a test email verifying that TAARUNYAM SMTP integration is working successfully.',
                from_email=settings_obj.contact_email,
                to=[test_email],
                connection=backend
            )
            email.send()
            return _success({}, 'Test email sent successfully.')
        except Exception as e:
            return Response({'success': False, 'data': {}, 'message': f'SMTP Error: {str(e)}'}, status=500)
