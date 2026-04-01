from django.urls import path
from apps.participants.views import PublicRegisterView, PublicParticipantLookupView

urlpatterns = [
    path('participants/register/', PublicRegisterView.as_view(), name='public-register'),
    path('participants/lookup/', PublicParticipantLookupView.as_view(), name='public-participant-lookup'),
]
