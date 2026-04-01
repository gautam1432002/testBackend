from django.urls import path
from apps.settings_app.views import PublicSettingsView

urlpatterns = [
    path('settings/public/', PublicSettingsView.as_view(), name='public-settings'),
]
