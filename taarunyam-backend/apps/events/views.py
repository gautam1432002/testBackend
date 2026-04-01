from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from apps.authentication.permissions import IsAdmin
from .models import Event
from .serializers import EventSerializer


def _success(data, message='', status_code=status.HTTP_200_OK):
    return Response({'success': True, 'data': data, 'message': message}, status=status_code)


# ─── PUBLIC: List all active events (no auth required) ────────────────────────

class PublicEventListView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        events = Event.objects.filter(is_active=True).prefetch_related('registrations')
        serializer = EventSerializer(events, many=True)
        return _success(serializer.data)


# ─── ADMIN: Full CRUD ──────────────────────────────────────────────────────────

class EventViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdmin]
    serializer_class = EventSerializer
    search_fields = ['title', 'venue', 'description']
    ordering_fields = ['event_date', 'created_at', 'title']
    ordering = ['-event_date']

    def get_queryset(self):
        return Event.objects.all().prefetch_related('registrations')

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return _success(serializer.data, 'Event created.', status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return _success(serializer.data, 'Event updated.')

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return _success({}, 'Event deleted.')

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return _success(serializer.data)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return _success(serializer.data)

    @action(detail=True, methods=['get'], url_path='participants')
    def participants(self, request, pk=None):
        """GET /api/admin/events/<id>/participants/"""
        from apps.participants.models import Registration
        from apps.participants.serializers import FlatParticipantSerializer

        event = self.get_object()
        registrations = Registration.objects.filter(event=event).select_related(
            'participant'
        ).prefetch_related('certificate__email_logs')

        page = self.paginate_queryset(registrations)
        if page is not None:
            serializer = FlatParticipantSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = FlatParticipantSerializer(registrations, many=True)
        return _success(serializer.data)
