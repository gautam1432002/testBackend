from django.urls import path
from apps.contact.views import AdminContactListView, AdminContactReadView

urlpatterns = [
    path('contact/', AdminContactListView.as_view(), name='admin-contact-list'),
    path('contact/<uuid:pk>/read/', AdminContactReadView.as_view(), name='admin-contact-read'),
]
