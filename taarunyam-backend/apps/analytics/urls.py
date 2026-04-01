from django.urls import path
from . import views

urlpatterns = [
    path('analytics/overview/', views.AdminOverviewAnalyticsView.as_view(), name='admin-analytics-overview'),
    path('analytics/events/breakdown/', views.AdminEventsAnalyticsView.as_view(), name='admin-analytics-events'),
    path('analytics/registrations/', views.AdminRegistrationsTimelineView.as_view(), name='admin-analytics-registrations'),
]
