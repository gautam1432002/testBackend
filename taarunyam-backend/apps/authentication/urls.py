from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.LoginView.as_view(), name='auth-login'),
    path('refresh/', views.RefreshView.as_view(), name='auth-refresh'),
    path('logout/', views.LogoutView.as_view(), name='auth-logout'),
    path('me/', views.MeView.as_view(), name='auth-me'),
    path('otp/request/', views.OTPRequestView.as_view(), name='auth-otp-request'),
    path('otp/verify/', views.OTPVerifyView.as_view(), name='auth-otp-verify'),
    path('otp/reset/', views.OTPResetView.as_view(), name='auth-otp-reset'),
]
