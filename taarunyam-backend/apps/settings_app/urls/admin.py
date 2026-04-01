from django.urls import path
from apps.settings_app.views import AdminSettingsView, SMTPTestView

urlpatterns = [
    path('settings/', AdminSettingsView.as_view(), name='admin-settings'),
    path('settings/smtp-test/', SMTPTestView.as_view(), name='admin-smtp-test'),
]
