from django.urls import path
from . import views

urlpatterns = [
    path('verify/<uuid:qr_token>/', views.PublicVerifyView.as_view(), name='public-verify'),
]
