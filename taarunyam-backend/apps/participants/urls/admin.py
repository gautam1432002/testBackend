from django.urls import path
from apps.participants import views

urlpatterns = [
    # Bulk operations — MUST come before <str:registration_id>/ to avoid URL conflicts
    path('participants/bulk-delete/', views.AdminBulkDeleteView.as_view(), name='admin-participants-bulk-delete'),
    path('participants/export/', views.AdminExportView.as_view(), name='admin-participants-export'),

    # List
    path('participants/', views.AdminParticipantsView.as_view(), name='admin-participants-list'),

    # Detail (CRUD) — dynamic path MUST come after all static paths
    path('participants/<str:registration_id>/', views.AdminParticipantDetailView.as_view(), name='admin-participant-detail'),

    # Registration-specific actions
    path('participants/<str:registration_id>/toggle-winner/', views.AdminWinnerToggleView.as_view(), name='admin-registration-winner'),
    path('participants/<str:registration_id>/attendance/', views.AdminAttendanceView.as_view(), name='admin-registration-attendance'),
]
