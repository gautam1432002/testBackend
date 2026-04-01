import random
import string
import hashlib
import uuid
import threading

from django.conf import settings
from django.contrib.auth import authenticate
from django.core.mail import EmailMultiAlternatives
from django.core.cache import cache
from django.utils.html import strip_tags
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError

from .models import AdminUser
from .serializers import (
    LoginSerializer, AdminUserSerializer,
    OTPRequestSerializer, OTPVerifySerializer, OTPResetSerializer
)

COOKIE_NAME = 'taarunyam_refresh'
COOKIE_MAX_AGE = 7 * 24 * 60 * 60  # 7 days in seconds


def _success(data, message='', status_code=status.HTTP_200_OK):
    return Response({'success': True, 'data': data, 'message': message}, status=status_code)


def _error(message, status_code=status.HTTP_400_BAD_REQUEST):
    return Response({'success': False, 'data': {}, 'message': message}, status=status_code)


def lockout_response(request, credentials, *args, **kwargs):
    from rest_framework.response import Response
    return Response(
        {'success': False, 'data': {}, 'message': 'Account locked due to too many failed login attempts. Try again in 1 hour.'},
        status=status.HTTP_403_FORBIDDEN
    )


def send_otp_email(email, otp):
    """Sends a professional HTML email in a background thread."""
    subject = 'TAARUNYAM Admin — Security OTP'
    
    # Professional HTML Content
    html_content = f"""
    <div style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; max-width: 600px; margin: auto; padding: 40px; border: 1px solid #e0e0e0; border-radius: 12px; background-color: #ffffff;">
        <div style="text-align: center; margin-bottom: 30px;">
            <h1 style="color: #6366f1; margin: 0; font-size: 28px; letter-spacing: 1px;">TAARUNYAM 2026</h1>
            <p style="color: #64748b; font-size: 14px; margin-top: 5px;">Secure Administration Portal</p>
        </div>
        <div style="padding: 20px; background-color: #f8fafc; border-radius: 8px; text-align: center;">
            <p style="color: #334155; font-size: 16px; margin-bottom: 20px;">You requested a password reset for your admin account. Please use the following One-Time Password (OTP):</p>
            <div style="font-size: 36px; font-weight: 800; color: #6366f1; letter-spacing: 8px; margin: 20px 0; padding: 10px; background: #eef2ff; border-radius: 6px; display: inline-block;">
                {otp}
            </div>
            <p style="color: #ef4444; font-size: 13px; font-weight: 600; margin-top: 20px;">This code will expire in 10 minutes.</p>
        </div>
        <div style="margin-top: 30px; color: #94a3b8; font-size: 12px; line-height: 1.5; text-align: center;">
            <p>If you did not request this code, please secure your account immediately or contact the system administrator.</p>
            <p style="margin-top: 20px;">&copy; 2026 TAARUNYAM. All rights reserved.</p>
        </div>
    </div>
    """
    text_content = f"Your TAARUNYAM Admin OTP is: {otp}. This code expires in 10 minutes."
    
    def _send():
        try:
            msg = EmailMultiAlternatives(subject, text_content, settings.DEFAULT_FROM_EMAIL, [email])
            msg.attach_alternative(html_content, "text/html")
            msg.send(fail_silently=False)
        except Exception as e:
            print(f"Failed to send email: {e}")

    # Run in background to eliminate API delay
    threading.Thread(target=_send).start()


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = authenticate(
            request,
            username=serializer.validated_data['username'],
            password=serializer.validated_data['password'],
        )

        if not user:
            return _error('Invalid username or password.', status.HTTP_401_UNAUTHORIZED)

        if not user.is_active:
            return _error('This account is disabled.', status.HTTP_403_FORBIDDEN)

        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)

        response = _success({
            'access': access_token,
            'user': AdminUserSerializer(user).data,
        }, message='Login successful.')

        # Set HttpOnly refresh token cookie
        response.set_cookie(
            key=COOKIE_NAME,
            value=str(refresh),
            max_age=COOKIE_MAX_AGE,
            httponly=True,
            secure=not settings.DEBUG,
            samesite='Lax',
        )
        return response


class RefreshView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        token = request.COOKIES.get(COOKIE_NAME)
        if not token:
            return _error('Refresh token not found.', status.HTTP_401_UNAUTHORIZED)

        try:
            refresh = RefreshToken(token)
            access_token = str(refresh.access_token)

            response = _success({'access': access_token}, message='Token refreshed.')

            # Rotate: set new refresh cookie
            response.set_cookie(
                key=COOKIE_NAME,
                value=str(refresh),
                max_age=COOKIE_MAX_AGE,
                httponly=True,
                secure=not settings.DEBUG,
                samesite='Lax',
            )
            return response
        except TokenError as e:
            return _error(str(e), status.HTTP_401_UNAUTHORIZED)


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        token = request.COOKIES.get(COOKIE_NAME)
        if token:
            try:
                RefreshToken(token).blacklist()
            except TokenError:
                pass

        response = _success({}, message='Logged out successfully.')
        response.delete_cookie(COOKIE_NAME)
        return response


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return _success(AdminUserSerializer(request.user).data)


class OTPRequestView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = OTPRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email'].lower()

        # Explicit Authorization Check (as requested for "cross check")
        authorized_emails = [e.strip().lower() for e in settings.AUTHORIZED_ADMIN_EMAILS]
            
        if email not in authorized_emails:
            return _error('This email is not authorized for admin access. Please contact the system owner', status.HTTP_403_FORBIDDEN)

        # Generate 6-digit OTP
        otp = ''.join(random.choices(string.digits, k=settings.OTP_LENGTH))
        otp_hash = hashlib.sha256(otp.encode()).hexdigest()
        cache_key = f'otp:{email}'
        
        # Ensure 10-minute validation (600 seconds)
        cache.set(cache_key, otp_hash, timeout=settings.OTP_TTL_SECONDS)

        # Send professional email in background
        send_otp_email(email, otp)
        
        return _success({}, message='A secure OTP has been sent to your email.')


class OTPVerifyView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = OTPVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email'].lower()
        otp = serializer.validated_data['otp']

        cache_key = f'otp:{email}'
        stored_hash = cache.get(cache_key)

        if not stored_hash:
            return _error('OTP has expired or was never issued.', status.HTTP_400_BAD_REQUEST)

        if hashlib.sha256(otp.encode()).hexdigest() != stored_hash:
            return _error('Invalid OTP.', status.HTTP_400_BAD_REQUEST)

        # OTP correct — generate a one-time reset token
        reset_token = str(uuid.uuid4())
        cache.set(f'reset_token:{reset_token}', email, timeout=300)  # 5 min
        cache.delete(cache_key)  # Invalidate OTP immediately

        return _success({'reset_token': reset_token}, message='OTP verified.')


class OTPResetView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = OTPResetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        reset_token = serializer.validated_data['reset_token']
        email = cache.get(f'reset_token:{reset_token}')

        if not email:
            return _error('Reset token is invalid or has expired.', status.HTTP_400_BAD_REQUEST)

        try:
            user = AdminUser.objects.get(email__iexact=email)
        except AdminUser.DoesNotExist:
            return _error('No admin account found for this email.', status.HTTP_404_NOT_FOUND)

        # Check username uniqueness (excluding self)
        new_username = serializer.validated_data['new_username']
        if AdminUser.objects.exclude(pk=user.pk).filter(username=new_username).exists():
            return _error('Username is already taken.', status.HTTP_400_BAD_REQUEST)

        user.username = new_username
        user.set_password(serializer.validated_data['new_password'])
        user.save()

        cache.delete(f'reset_token:{reset_token}')

        return _success({}, message='Password and username updated successfully. Please log in.')
