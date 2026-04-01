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

class AdminBulkSendEmailView(APIView):
    """
    Accepts a list of registration IDs and an optional email template.
    Auto-generates PDFs if needed, then sends emails synchronously.
    Returns per-participant delivery results immediately.

    NOTE: This view is COMPLETELY SEPARATE from auth password reset.
    It uses distribute.py — no shared code with authentication.
    """
    permission_classes = [IsAdmin]

    def post(self, request):
        participant_ids = request.data.get('participant_ids', [])
        template = request.data.get('template', {})

        if not participant_ids:
            return Response({
                'success': False,
                'data': {},
                'message': 'No participant IDs provided.'
            }, status=400)

        if not isinstance(participant_ids, list):
            return Response({
                'success': False,
                'data': {},
                'message': '`participant_ids` must be a list of registration ID strings.'
            }, status=400)

        # Default template values
        template.setdefault('subject', 'Your TAARUNYAM 2026 Certificate')
        template.setdefault('greeting', 'Dear Participant,')
        template.setdefault('body', 'Please find your official TAARUNYAM 2026 certificate attached to this email. Thank you for your participation.')
        template.setdefault('closing', 'Best Regards,')
        template.setdefault('signature', 'The TAARUNYAM Organizing Team')

        # Import the standalone distributor — zero coupling to auth
        from .distribute import distribute_emails

        results = distribute_emails(registration_ids=participant_ids, template=template)

        sent_count = sum(1 for r in results if r['status'] == 'sent')
        failed_count = sum(1 for r in results if r['status'] == 'failed')

        return _success(
            data={
                'results': results,
                'sent': sent_count,
                'failed': failed_count,
                'total': len(results),
            },
            message=f'Distribution complete: {sent_count} sent, {failed_count} failed.',
            status_code=status.HTTP_200_OK,
        )


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
