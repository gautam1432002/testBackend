from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import redirect
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView
from apps.events.urls import public_urlpatterns as events_public_urls

urlpatterns = [
    # Root redirect to docs
    path('', lambda request: redirect('api/docs/', permanent=False)),
    
    # Django admin
    path('django-admin/', admin.site.urls),

    # API documentation
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),

    # Authentication
    path('api/auth/', include('apps.authentication.urls')),

    # Public endpoints
    path('api/', include('apps.participants.urls.public')),
    path('api/', include('apps.verification.urls')),
    path('api/', include('apps.contact.urls.public')),
    path('api/', include('apps.settings_app.urls.public')),
    path('api/', include(events_public_urls)),          # ← public events: GET /api/events/

    # Admin endpoints
    path('api/admin/', include('apps.events.urls')),
    path('api/admin/', include('apps.participants.urls.admin')),
    path('api/admin/', include('apps.certificates.urls')),
    path('api/admin/', include('apps.emails.urls')),
    path('api/admin/', include('apps.analytics.urls')),
    path('api/admin/', include('apps.settings_app.urls.admin')),
    path('api/admin/', include('apps.contact.urls.admin')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
