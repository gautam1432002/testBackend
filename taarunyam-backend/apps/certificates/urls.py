from django.urls import path
from . import views

urlpatterns = [
    # List
    path('certificates/', views.AdminCertificateListView.as_view(), name='admin-cert-list'),

    # Generate
    path('certificates/generate/', views.AdminCertificateGenerateView.as_view(), name='admin-cert-generate'),
    path('certificates/bulk-generate/', views.AdminCertificateBulkGenerateView.as_view(), name='admin-cert-bulk-generate'),

    # Task Status
    path('certificates/task/<str:task_id>/', views.AdminCertificateTaskStatusView.as_view(), name='admin-cert-task'),

    # Document / Actions
    path('certificates/<uuid:pk>/download/', views.AdminCertificateDownloadView.as_view(), name='admin-cert-download'),
    path('certificates/<uuid:pk>/revoke/', views.AdminCertificateRevokeView.as_view(), name='admin-cert-revoke'),
    path('certificates/<uuid:pk>/reinstate/', views.AdminCertificateReinstateView.as_view(), name='admin-cert-reinstate'),

    # Settings and Stats
    path('certificates/settings/', views.AdminCertSettingsView.as_view(), name='admin-cert-settings'),
    path('certificates/stats/', views.AdminCertificateStatsView.as_view(), name='admin-cert-stats'),

    # Issue 3: generate+download the same PDF the email attaches
    path('certificates/preview-download/', views.AdminCertificatePreviewDownloadView.as_view(), name='admin-cert-preview-download'),
]
