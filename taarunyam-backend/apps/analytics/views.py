from django.core.cache import cache
from django.db.models import Count, Func, Value, CharField
from django.db.models.functions import TruncDate
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response

from apps.authentication.permissions import IsAdmin
from apps.participants.models import Registration
from apps.events.models import Event
from apps.certificates.models import Certificate
from .tasks import refresh_analytics_cache


def _success(data, message='', status_code=status.HTTP_200_OK):
    return Response({'success': True, 'data': data, 'message': message}, status=status_code)


class AdminOverviewAnalyticsView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        data = cache.get('analytics_overview')
        if not data:
            data = refresh_analytics_cache()
            if not data:
                return Response({'success': False, 'data': {}, 'message': 'Failed to build analytics.'}, status=500)
        return _success(data)


class AdminEventsAnalyticsView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        events = Event.objects.annotate(
            participantCount=Count('registrations', distinct=True)
        ).all()

        results = []
        for e in events:
            # We must compute winners actively or annotate
            winner_count = Certificate.objects.filter(
                registration__event=e, type='winner'
            ).count()

            fill_rate = 0
            if e.capacity > 0:
                fill_rate = (e.participantCount / e.capacity) * 100

            results.append({
                'eventId': str(e.id),
                'eventTitle': e.title,
                'participantCount': e.participantCount,
                'winnerCount': winner_count,
                'fillRate': round(fill_rate, 2)
            })

        return _success(results)


class AdminRegistrationsTimelineView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        # Time series of registrations by date
        # Fallback to sqlite if postgres Date trunc isn't working
        daily_counts = Registration.objects.annotate(
            date=TruncDate('registration_date')
        ).values('date').annotate(
            newRegistrations=Count('id')
        ).order_by('date')

        results = []
        cumulative = 0
        for entry in daily_counts:
            # handle cases where date might be None
            if not entry['date']:
                continue
            cumulative += entry['newRegistrations']
            results.append({
                'date': entry['date'].isoformat(),
                'newRegistrations': entry['newRegistrations'],
                'cumulativeTotal': cumulative
            })

        return _success(results)
