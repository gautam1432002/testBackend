from django.urls import path
from apps.contact.views import PublicContactView

urlpatterns = [
    path('contact/', PublicContactView.as_view(), name='public-contact'),
]
