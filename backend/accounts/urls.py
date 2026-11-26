from django.urls import path

from .views import (
    AdminUserListView,
    ChangePasswordView,
    CsrfView,
    LoginView,
    LogoutView,
    MeView,
    RegisterView,
)

urlpatterns = [
    path("auth/csrf", CsrfView.as_view()),
    path("auth/register", RegisterView.as_view()),
    path("auth/login", LoginView.as_view()),
    path("auth/logout", LogoutView.as_view()),
    path("auth/me", MeView.as_view()),
    path("auth/change-password", ChangePasswordView.as_view()),
    path("admin/users", AdminUserListView.as_view()),
]
