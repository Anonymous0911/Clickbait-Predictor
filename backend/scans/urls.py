from django.urls import path

from .views import AdminHistoryView, HealthView, HistoryView, PredictView

urlpatterns = [
    path("predict", PredictView.as_view()),
    path("history", HistoryView.as_view()),
    path("admin/history", AdminHistoryView.as_view()),
    path("health", HealthView.as_view()),
]
