import mimetypes
from django.http import HttpResponse, FileResponse
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from celery.result import AsyncResult, allow_join_result

from apps.authentication.permissions import IsAdmin
from .models import Certificate
from .serializers import CertificateSerializer, GenerateCertificateSerializer, BulkGenerateSerializer
from .tasks import generate_single_certificate, start_bulk_generation
from apps.settings_app.models import SiteSettings


def _success(data, message='', status_code=status.HTTP_200_OK):
    return Response({'success': True, 'data': data, 'message': message}, status=status_code)


class AdminCertificateListView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        qs = Certificate.objects.select_related('registration__participant', 'registration__event', 'issued_by').all()

        type_filter = request.query_params.get('type')
        if type_filter:
            qs = qs.filter(type=type_filter)

        event_filter = request.query_params.get('event')
        if event_filter:
            qs = qs.filter(registration__event_id=event_filter)

        from taarunyam.pagination import StandardPagination
        paginator = StandardPagination()
        page = paginator.paginate_queryset(qs, request)
        serializer = CertificateSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class AdminCertificateGenerateView(APIView):
    permission_classes = [IsAdmin]

    def post(self, request):
        serializer = GenerateCertificateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Trigger async task
        task = generate_single_certificate.delay(
            serializer.validated_data['registration_id'],
            serializer.validated_data['type'],
            serializer.validated_data.get('prize_position', ''),
            str(request.user.id)
        )
        return _success({'task_id': task.id}, 'Certificate generation started.', status.HTTP_202_ACCEPTED)


class AdminCertificateBulkGenerateView(APIView):
    permission_classes = [IsAdmin]

    def post(self, request):
        serializer = BulkGenerateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        task_id = start_bulk_generation(
            serializer.validated_data['event_id'],
            serializer.validated_data['type'],
            str(request.user.id)
        )

        if not task_id:
            return Response({'success': False, 'data': {}, 'message': 'No eligible participants found.'}, status=400)

        return _success({'task_id': task_id}, 'Bulk generation started.', status.HTTP_202_ACCEPTED)


class AdminCertificateTaskStatusView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request, task_id):
        res = AsyncResult(task_id)
        data = {
            'task_id': task_id,
            'status': res.status,
            'result': res.result if res.ready() else None
        }
        return _success(data)


class AdminCertificateDownloadView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request, pk):
        try:
            cert = Certificate.objects.get(pk=pk)
        except Certificate.DoesNotExist:
            return Response({'success': False, 'data': {}, 'message': 'Not found.'}, status=404)

        if not cert.pdf_path:
            return Response({'success': False, 'data': {}, 'message': 'PDF not generated yet.'}, status=400)

        try:
            return FileResponse(cert.pdf_path.open('rb'), as_attachment=True, filename=f"certificate_{cert.registration.registration_id}.pdf")
        except Exception as e:
             return Response({'success': False, 'data': {}, 'message': str(e)}, status=500)


class AdminCertificateRevokeView(APIView):
    permission_classes = [IsAdmin]

    def post(self, request, pk):
        try:
            cert = Certificate.objects.get(pk=pk)
        except Certificate.DoesNotExist:
            return Response({'success': False, 'data': {}, 'message': 'Not found.'}, status=404)
        cert.is_valid = False
        cert.save()
        return _success(CertificateSerializer(cert).data, 'Certificate revoked.')


class AdminCertificateReinstateView(APIView):
    permission_classes = [IsAdmin]

    def post(self, request, pk):
        try:
            cert = Certificate.objects.get(pk=pk)
        except Certificate.DoesNotExist:
            return Response({'success': False, 'data': {}, 'message': 'Not found.'}, status=404)
        cert.is_valid = True
        cert.save()
        return _success(CertificateSerializer(cert).data, 'Certificate reinstated.')


class AdminCertSettingsView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        settings_obj = SiteSettings.objects.first()
        if not settings_obj:
             return _success({})
        return _success(settings_obj.cert_settings)

    def put(self, request):
        settings_obj, _ = SiteSettings.objects.get_or_create(id=1)
        settings_obj.cert_settings = request.data
        settings_obj.save()
        return _success(settings_obj.cert_settings, 'Settings updated.')

class AdminCertificateStatsView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        total = Certificate.objects.count()
        participation = Certificate.objects.filter(type='participation').count()
        winner = Certificate.objects.filter(type='winner').count()
        sent = Certificate.objects.filter(email_logs__status='sent').distinct().count()

        return _success({
            'total': total,
            'sent': sent,
            'pending': total - sent,
            'byType': {
                'participation': participation,
                'winner': winner
            }
        })


class AdminCertificatePreviewDownloadView(APIView):
    """
    Issue 3 fix: Generate (or re-use) the SAME ReportLab PDF that the email system
    attaches, then stream it as a download.

    POST /api/admin/certificates/preview-download/
    Body: { "registration_id": "TAR-2026-001" }
           optional: { "cert_type": "winner" | "participation" }

    This guarantees Preview == Email attachment because both use CertificateService.
    """
    permission_classes = [IsAdmin]

    def post(self, request):
        from apps.participants.models import Registration
        from apps.emails.distribute import _ensure_certificate_pdf

        registration_id = request.data.get('registration_id', '').strip()
        cert_type = request.data.get('cert_type')  # optional override

        if not registration_id:
            return Response(
                {'success': False, 'data': {}, 'message': 'registration_id is required.'},
                status=400
            )

        try:
            reg = Registration.objects.select_related('participant', 'event').get(
                registration_id=registration_id
            )
        except Registration.DoesNotExist:
            return Response(
                {'success': False, 'data': {}, 'message': f'Registration {registration_id!r} not found.'},
                status=404
            )

        cert, error = _ensure_certificate_pdf(reg, cert_type=cert_type)
        if error or not cert:
            return Response(
                {'success': False, 'data': {}, 'message': error or 'PDF generation failed.'},
                status=500
            )

        try:
            safe_name = (
                f"TAARUNYAM_2026_{reg.participant.full_name.replace(' ', '_')}"
                f"_{'Winner' if cert.type == 'winner' else 'Participation'}_Certificate.pdf"
            )
            return FileResponse(
                cert.pdf_path.open('rb'),
                as_attachment=True,
                filename=safe_name,
                content_type='application/pdf',
            )
        except Exception as e:
            return Response(
                {'success': False, 'data': {}, 'message': str(e)},
                status=500
            )
