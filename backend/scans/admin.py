from django.contrib import admin

from .models import Scan


@admin.register(Scan)
class ScanAdmin(admin.ModelAdmin):
    list_select_related = ("user",)
    list_display = ("headline", "label", "clickbait_probability", "user", "created_at")
