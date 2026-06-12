from django.urls import path
from . import views

urlpatterns = [
    # List and Stats
    path('email/logs/', views.AdminEmailLogListView.as_view(), name='admin-email-logs'),
    path('email/stats/', views.AdminEmailStatsView.as_view(), name='admin-email-stats'),

    # Send Actions
    path('email/send/', views.AdminSendEmailView.as_view(), name='admin-email-send'),
    path('email/upload-send/', views.AdminUploadSendEmailView.as_view(), name='admin-email-upload-send'),

    # Celery Task Status
    path('email/task/<str:task_id>/', views.AdminEmailTaskStatusView.as_view(), name='admin-email-task'),
]
