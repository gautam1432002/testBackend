import csv
import io
from django.http import HttpResponse
from django.db.models import Q
from rest_framework import status, generics
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from apps.authentication.permissions import IsAdmin
from apps.events.models import Event
from .models import Participant, Registration
from .serializers import FlatParticipantSerializer, PublicRegisterSerializer


def _success(data, message='', status_code=status.HTTP_200_OK):
    return Response({'success': True, 'data': data, 'message': message}, status=status_code)


# ─── PUBLIC: Register ─────────────────────────────────────────────────────────

class PublicRegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PublicRegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        # Map frontend year strings to model choices
        year_map = {'1st Year': '1st', '2nd Year': '2nd', '3rd Year': '3rd', '4th Year': '4th'}
        year_choice = year_map.get(data['year'], '1st')

        # Get or create participant (idempotent by email)
        participant, _ = Participant.objects.get_or_create(
            email=data['email'],
            defaults={
                'full_name': data['name'],
                'phone': data['mobile'],
                'college': data['college'],
                'department': data['course'],
                'year_of_study': year_choice,
            }
        )

        registrations_created = []
        found_events = []
        for event_id in data['events']:
            # Search by UUID first, then slug, then title
            import uuid as _uuid
            event = None
            try:
                event_uuid = _uuid.UUID(str(event_id))
                event = Event.objects.filter(id=event_uuid, is_active=True).first()
            except (ValueError, AttributeError):
                pass  # Not a valid UUID — fall through to slug/title lookup

            if not event:
                event = Event.objects.filter(
                    Q(slug=event_id) | Q(title__iexact=event_id),
                    is_active=True
                ).first()
            
            if not event:
                continue
            
            found_events.append(event)
            reg, created = Registration.objects.get_or_create(
                participant=participant,
                event=event
            )
            registrations_created.append(reg)

        if not found_events:
            return Response({
                'success': False,
                'data': {},
                'message': f"Selected events ({', '.join(data['events'])}) were not found in the system.",
            }, status=status.HTTP_404_NOT_FOUND)

        if not registrations_created:
            # This case happens if found_events has items but get_or_create didn't add anything new?
            # Actually get_or_create always returns something.
            # But the original code was checking if it was NEWLY created?
            # "registrations_created" in original code was only appending if created=True.
            # If the user already registered, it returned error.
            pass

        # Re-check logic to match user expectation: "Already registered" vs "Success"
        # If any reg was found/created, we return the first one as success.
        reg = registrations_created[0]
        flat = FlatParticipantSerializer(reg)
        return _success({'participant': flat.data}, 'Registered successfully.', status.HTTP_201_CREATED)


class PublicParticipantLookupView(APIView):
    permission_classes = [AllowAny]
    
    def get(self, request):
        query = request.query_params.get('q', '').strip()
        if not query:
            return Response({'success': False, 'data': {'found': False}}, status=400)
        
        # Look up by Registration ID or Email
        reg = Registration.objects.select_related('participant', 'certificate').filter(
            Q(registration_id__iexact=query) |
            Q(participant__email__iexact=query)
        ).first()

        if reg:
            cert_id = str(reg.certificate.qr_token) if hasattr(reg, 'certificate') and reg.certificate else reg.registration_id
            return _success({
                'found': True,
                'participant': {
                    'id': reg.registration_id,
                    'name': reg.participant.full_name,
                    'certificateId': cert_id
                }
            })
            
        # Also try by Certificate UUID if it matches the format
        try:
            from uuid import UUID
            UUID(query)
            from apps.certificates.models import Certificate
            cert = Certificate.objects.select_related('registration__participant').filter(qr_token=query).first()
            if cert:
                return _success({
                    'found': True,
                    'participant': {
                        'id': cert.registration.registration_id,
                        'name': cert.registration.participant.full_name,
                        'certificateId': str(cert.qr_token)
                    }
                })
        except ValueError:
            pass

        return _success({'found': False}, 'Not found.')



# ─── ADMIN: Participants List ── ───────────────────────────────────────────────

class AdminParticipantsView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        qs = Registration.objects.select_related(
            'participant', 'event'
        ).prefetch_related('certificate__email_logs')

        # Search
        search = request.query_params.get('search')
        if search:
            qs = qs.filter(
                participant__full_name__icontains=search
            ) | qs.filter(
                participant__email__icontains=search
            ) | qs.filter(registration_id__icontains=search)

        # Filters
        event_id = request.query_params.get('event')
        if event_id and event_id != 'all':
            qs = qs.filter(event__id=event_id)

        is_winner = request.query_params.get('isWinner')
        if is_winner is not None:
            want_winner = is_winner.lower() == 'true'
            if want_winner:
                qs = qs.filter(certificate__type='winner')
            else:
                qs = qs.exclude(certificate__type='winner')

        # Pagination
        from taarunyam.pagination import StandardPagination
        paginator = StandardPagination()
        page = paginator.paginate_queryset(qs, request)
        serializer = FlatParticipantSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class AdminParticipantDetailView(APIView):
    permission_classes = [IsAdmin]

    # Maps frontend year strings to model choices
    YEAR_MAP = {
        '1st Year': '1st', '2nd Year': '2nd', '3rd Year': '3rd', '4th Year': '4th',
        # Also accept model values directly (idempotent)
        '1st': '1st', '2nd': '2nd', '3rd': '3rd', '4th': '4th',
    }

    def _get_registration(self, registration_id):
        try:
            return Registration.objects.select_related(
                'participant', 'event'
            ).prefetch_related('certificate__email_logs').get(
                registration_id=registration_id
            )
        except Registration.DoesNotExist:
            return None

    def _apply_update(self, p, data):
        """Apply update data to a Participant instance and save."""
        if 'name' in data:
            p.full_name = data['name']
        if 'email' in data:
            p.email = data['email']
        if 'mobile' in data:
            p.phone = data['mobile']
        if 'college' in data:
            p.college = data['college']
        if 'course' in data:
            p.department = data['course']
        if 'year' in data:
            p.year_of_study = self.YEAR_MAP.get(data['year'], data['year'])
        p.save()

    def get(self, request, registration_id):
        reg = self._get_registration(registration_id)
        if not reg:
            return Response({'success': False, 'data': {}, 'message': 'Participant not found.'}, status=404)
        return _success(FlatParticipantSerializer(reg).data)

    def put(self, request, registration_id):
        reg = self._get_registration(registration_id)
        if not reg:
            return Response({'success': False, 'data': {}, 'message': 'Participant not found.'}, status=404)
        self._apply_update(reg.participant, request.data)
        reg.refresh_from_db()
        return _success(FlatParticipantSerializer(reg).data, 'Participant updated.')

    def patch(self, request, registration_id):
        """Partial update — same as PUT but accepts any subset of fields."""
        reg = self._get_registration(registration_id)
        if not reg:
            return Response({'success': False, 'data': {}, 'message': 'Participant not found.'}, status=404)
        self._apply_update(reg.participant, request.data)
        reg.refresh_from_db()
        return _success(FlatParticipantSerializer(reg).data, 'Participant updated.')

    def delete(self, request, registration_id):
        reg = self._get_registration(registration_id)
        if not reg:
            return Response({'success': False, 'data': {}, 'message': 'Participant not found.'}, status=404)
        participant = reg.participant
        reg.delete()
        # Delete participant if they have no other registrations
        if not participant.registrations.exists():
            participant.delete()
        return _success({}, 'Participant deleted.')


class AdminBulkDeleteView(APIView):
    permission_classes = [IsAdmin]

    def post(self, request):
        ids = request.data.get('ids', [])
        if not ids:
            return Response({'success': False, 'data': {}, 'message': 'No IDs provided.'}, status=400)
        deleted, _ = Registration.objects.filter(registration_id__in=ids).delete()
        return _success({'deleted': deleted}, f'{deleted} participant(s) deleted.')


class AdminWinnerToggleView(APIView):
    permission_classes = [IsAdmin]

    def patch(self, request, registration_id):
        try:
            reg = Registration.objects.select_related('event').prefetch_related('certificate').get(
                registration_id=registration_id
            )
        except Registration.DoesNotExist:
            return Response({'success': False, 'data': {}, 'message': 'Registration not found.'}, status=404)

        from apps.certificates.models import Certificate
        prize_position = request.data.get('prizePosition', '')

        if hasattr(reg, 'certificate'):
            cert = reg.certificate
            old_type = cert.type

            if cert.type == 'winner':
                # Toggle off: downgrade to participant
                cert.type = 'participation'
                cert.prize_position = ''
            else:
                cert.type = 'winner'
                cert.prize_position = prize_position

            # If cert type changed, delete the stale PDF so it regenerates correctly
            if old_type != cert.type and cert.pdf_path:
                try:
                    cert.pdf_path.delete(save=False)
                except Exception:
                    pass
                cert.pdf_path = None

            cert.save()
        else:
            # Generate the certificate on the fly as a winner!
            Certificate.objects.create(
                registration=reg,
                type='winner',
                prize_position=prize_position,
                issued_by=request.user
            )

        reg.refresh_from_db()
        return _success(FlatParticipantSerializer(reg).data, 'Winner status updated.')


class AdminAttendanceView(APIView):
    permission_classes = [IsAdmin]

    def patch(self, request, registration_id):
        try:
            reg = Registration.objects.get(registration_id=registration_id)
        except Registration.DoesNotExist:
            return Response({'success': False, 'data': {}, 'message': 'Registration not found.'}, status=404)
        reg.is_present = request.data.get('isPresent', not reg.is_present)
        reg.save()
        return _success({'isPresent': reg.is_present}, 'Attendance updated.')


class AdminExportView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        fmt = request.query_params.get('format', 'csv')
        registrations = Registration.objects.select_related(
            'participant', 'event'
        ).prefetch_related('certificate__email_logs').all()

        rows = [FlatParticipantSerializer(r).data for r in registrations]

        if fmt == 'xlsx':
            import openpyxl
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = 'Participants'
            if rows:
                ws.append(list(rows[0].keys()))
                for row in rows:
                    ws.append([str(v) if v is not None else '' for v in row.values()])
            buf = io.BytesIO()
            wb.save(buf)
            buf.seek(0)
            response = HttpResponse(
                buf.read(),
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            response['Content-Disposition'] = 'attachment; filename=participants.xlsx'
            return response

        # Default CSV
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename=participants.csv'
        if rows:
            writer = csv.DictWriter(response, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
        return response
