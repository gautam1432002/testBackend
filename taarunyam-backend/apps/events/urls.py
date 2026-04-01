from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import EventViewSet, PublicEventListView

router = DefaultRouter()
router.register('events', EventViewSet, basename='events')

# Public endpoint (no auth)
public_urlpatterns = [
    path('events/', PublicEventListView.as_view(), name='public-events-list'),
]

# Admin endpoints via router
urlpatterns = [
    path('', include(router.urls)),
]
