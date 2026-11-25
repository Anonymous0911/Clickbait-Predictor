from django.contrib.auth import login, logout, update_session_auth_hash
from django.db import IntegrityError
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import serializers
from rest_framework.authentication import SessionAuthentication
from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from scans.services import claim_guest_scans

from .models import User
from .serializers import (
    ChangePasswordSerializer,
    LoginSerializer,
    RegisterSerializer,
    UserSerializer,
)
from .throttles import AuthThrottle, PasswordChangeThrottle


@method_decorator(ensure_csrf_cookie, name="dispatch")
class CsrfView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response(status=204)


class AnonymousCsrfMixin:
    """DRF only checks CSRF for signed-in sessions. Register and login are anonymous,
    so check here too; otherwise a third-party page could log a victim into the
    attacker's account."""

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        SessionAuthentication().enforce_csrf(request)


def sign_in(request, user):
    # login() rotates the session key, so read the guest's key first.
    guest_key = request.session.session_key
    login(request, user)
    claim_guest_scans(guest_key, user)


class RegisterView(AnonymousCsrfMixin, APIView):
    permission_classes = [AllowAny]
    throttle_classes = [AuthThrottle]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            user = User.objects.create_user(username=data["username"], password=data["password"])
        except IntegrityError:
            # Lost a race with the same username between validation and insert.
            raise serializers.ValidationError("That username is already in use.")
        sign_in(request, user)
        return Response({"user": UserSerializer(user).data}, status=201)


class LoginView(AnonymousCsrfMixin, APIView):
    permission_classes = [AllowAny]
    throttle_classes = [AuthThrottle]

    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        sign_in(request, user)
        return Response({"user": UserSerializer(user).data})


class LogoutView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        logout(request)
        return Response(status=204)


class MeView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        user = request.user if request.user.is_authenticated else None
        return Response({"user": UserSerializer(user).data if user else None})


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [PasswordChangeThrottle]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        request.user.set_password(serializer.validated_data["new_password"])
        request.user.save(update_fields=["password"])
        # Changing the password invalidates sessions; keep this one alive.
        update_session_auth_hash(request, request.user)
        return Response({"message": "Password changed successfully."})


class AdminUserListView(ListAPIView):
    permission_classes = [IsAdminUser]
    serializer_class = UserSerializer
    queryset = User.objects.order_by("id")
