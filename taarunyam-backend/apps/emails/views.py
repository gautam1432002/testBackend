from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from celery.result import AsyncResult

from apps.authentication.permissions import IsAdmin
from .models import EmailLog
from .serializers import EmailLogSerializer, SendEmailSerializer
from .tasks import send_certificate_email
from apps.certificates.models import Certificate


def _success(data, message='', status_code=status.HTTP_200_OK):
    return Response({'success': True, 'data': data, 'message': message}, status=status_code)


class AdminEmailLogListView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        qs = EmailLog.objects.select_related(
            'certificate__registration__participant',
            'certificate__registration__event'
        ).all()

        status_filter = request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)

        event_filter = request.query_params.get('event')
        if event_filter:
            qs = qs.filter(certificate__registration__event_id=event_filter)

        from taarunyam.pagination import StandardPagination
        paginator = StandardPagination()
        page = paginator.paginate_queryset(qs, request)
        serializer = EmailLogSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class AdminSendEmailView(APIView):
    """Send a single certificate email (uses Celery task)."""
    permission_classes = [IsAdmin]

    def post(self, request):
        serializer = SendEmailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        cert_id = serializer.validated_data['certificate_id']
        try:
            cert = Certificate.objects.get(pk=cert_id)
        except Certificate.DoesNotExist:
            return Response({'success': False, 'data': {}, 'message': 'Certificate not found.'}, status=404)

        if not cert.pdf_path:
            return Response({'success': False, 'data': {}, 'message': 'PDF not generated yet.'}, status=400)

        log = cert.email_logs.exclude(status='sent').order_by('-created_at').first()
        if not log:
            log = EmailLog.objects.create(
                certificate=cert,
                recipient_email=cert.registration.participant.email
            )
        else:
            log.status = 'pending'
            log.save()

        task = send_certificate_email.delay(log.id)
        log.celery_task_id = task.id
        log.save()

        return _success({'task_id': task.id}, 'Email sending started.', status.HTTP_202_ACCEPTED)


# ─── NEW: Bulk Send with participant_ids + template ───────────────────────────

class AdminUploadSendEmailView(APIView):
    """
    Accepts multipart/form-data from the frontend containing a fully generated PDF Blob,
    then constructs an EmailMessage and sends it immediately.
    """
    permission_classes = [IsAdmin]

    def post(self, request):
        participant_id = request.data.get('participant_id')
        participant_name = request.data.get('participant_name', '')
        participant_email = request.data.get('participant_email')
        subject = request.data.get('subject', 'Your TAARUNYAM 2026 Certificate')
        greeting = request.data.get('greeting', 'Dear Participant,')
        body_text = request.data.get('body', '')
        closing = request.data.get('closing', '')
        signature = request.data.get('signature', '')
        is_winner = request.data.get('is_winner') == 'true'
        pdf_file = request.FILES.get('certificate_pdf')

        if not participant_id or not participant_email or not pdf_file:
            return Response({'success': False, 'data': {}, 'message': 'Missing required fields or PDF file.'}, status=400)

        # Build HTML Email Body (simulating the previous template rendering)
        cert_type = 'Winner Certificate' if is_winner else 'Certificate of Participation'
        html_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; color: #1e1e2e; background: #f9f9f9; padding: 0; margin: 0;">
          <div style="max-width: 600px; margin: 40px auto; background: #ffffff; border-radius: 12px; box-shadow: 0 4px 24px rgba(0,0,0,0.08); overflow: hidden;">
            <div style="background: linear-gradient(135deg, #1e3a5f 0%, #2563eb 100%); padding: 40px 32px; text-align: center;">
              <h1 style="color: #ffffff; font-size: 28px; margin: 0; letter-spacing: 3px; font-weight: 900;">TAARUNYAM 2026</h1>
            </div>
            <div style="padding: 40px 32px;">
              <p style="font-size: 16px; color: #374151; margin: 0 0 16px;">{greeting}</p>
              <p style="font-size: 16px; color: #374151; line-height: 1.7; margin: 0 0 20px;">{body_text}</p>
              <div style="background: {'linear-gradient(135deg, #fef9c3, #fde68a)' if is_winner else 'linear-gradient(135deg, #eff6ff, #dbeafe)'}; border-radius: 8px; padding: 20px 24px; margin: 24px 0;">
                <p style="margin: 0; font-size: 15px; font-weight: bold;">{cert_type}</p>
                <p style="margin: 8px 0 0; font-size: 14px;">Awarded to: <strong>{participant_name}</strong></p>
              </div>
              <p style="font-size: 14px; color: #6b7280; margin: 0 0 8px;">Your official certificate PDF is attached to this email.</p>
            </div>
            <div style="padding: 24px 32px; background: #f3f4f6; text-align: center;">
              <p style="color: #374151; font-size: 14px; margin: 0;">{closing}</p>
              <p style="color: #1d4ed8; font-size: 15px; font-weight: bold; margin: 6px 0 0;">{signature}</p>
            </div>
          </div>
        </body>
        </html>
        """

        try:
            from django.core.mail import EmailMultiAlternatives
            from django.conf import settings
            
            # Use Django's default EMAIL_BACKEND (which is set up in settings)
            msg = EmailMultiAlternatives(
                subject=subject,
                body=body_text, # text content fallback
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'no-reply@taarunyam.com'),
                to=[participant_email],
            )
            msg.attach_alternative(html_body, "text/html")
            
            # Attach the exact PDF received from the frontend
            pdf_data = pdf_file.read()
            safe_name = f"TAARUNYAM_2026_{participant_name.replace(' ', '_')}_Certificate.pdf"
            msg.attach(safe_name, pdf_data, 'application/pdf')
            msg.send(fail_silently=False)

            # Log success
            try:
                from apps.participants.models import Registration
                reg = Registration.objects.get(registration_id=participant_id)
                reg.certificate_issued = True
                reg.save(update_fields=['certificate_issued'])
            except:
                pass

            return _success({'registration_id': participant_id}, 'Email sent successfully.')
            
        except Exception as e:
            return Response({'success': False, 'data': {'registration_id': participant_id}, 'message': str(e)}, status=500)



class AdminEmailTaskStatusView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request, task_id):
        res = AsyncResult(task_id)
        data = {
            'task_id': task_id,
            'status': res.status,
            'result': res.result if res.ready() else None
        }
        return _success(data)


class AdminEmailStatsView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        total = EmailLog.objects.count()
        sent = EmailLog.objects.filter(status='sent').count()
        failed = EmailLog.objects.filter(status='failed').count()
        pending = EmailLog.objects.filter(status='pending').count()

        return _success({
            'total': total,
            'sent': sent,
            'failed': failed,
            'pending': pending
        })
