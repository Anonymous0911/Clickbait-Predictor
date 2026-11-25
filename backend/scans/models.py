from django.conf import settings
from django.db import models


class Scan(models.Model):
    LABEL_CHOICES = [("clickbait", "Clickbait"), ("not_clickbait", "Not clickbait")]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.CASCADE)
    session_key = models.CharField(max_length=40, blank=True)
    headline = models.CharField(max_length=500, blank=True)
    thumbnail = models.ImageField(upload_to="thumbnails/", blank=True)
    label = models.CharField(max_length=20, choices=LABEL_CHOICES)
    confidence = models.FloatField()
    clickbait_probability = models.FloatField()
    headline_probability = models.FloatField()
    thumbnail_probability = models.FloatField()
    signals = models.JSONField()
    model_version = models.CharField(max_length=12)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["session_key", "-created_at"]),
        ]
