import logging

from celery.exceptions import TimeoutError as CeleryTimeoutError
from django.conf import settings
from django.core.cache import cache
from django.core.files.storage import default_storage
from django.db import DatabaseError, connection
from kombu.exceptions import OperationalError
from redis.exceptions import ConnectionError as RedisConnectionError
from rest_framework.generics import ListAPIView
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from config import celery_app

from .inference import current_model_version
from .models import Scan
from .serializers import AdminScanSerializer, PredictInputSerializer, ScanHistorySerializer
from .services import ensure_session_key, predict_cache_key, store_thumbnail
from .tasks import run_prediction
from .throttles import ScanAnonThrottle, ScanUserThrottle

logger = logging.getLogger(__name__)

SERVICE_DOWN = "The prediction service isn't running right now."


class PredictView(APIView):
    parser_classes = [MultiPartParser, FormParser]
    throttle_classes = [ScanAnonThrottle, ScanUserThrottle]

    def post(self, request):
        serializer = PredictInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        headline = serializer.validated_data["headline"]
        image_bytes = serializer.validated_data["image_bytes"]

        version = current_model_version()
        thumbnail_name = ""
        if image_bytes is not None:
            thumbnail_name = store_thumbnail(image_bytes, serializer.validated_data["image_format"])

        key = predict_cache_key(headline, image_bytes, version)
        result = cache.get(key)
        if result is not None:
            model_version = version
        else:
            path = default_storage.path(thumbnail_name) if thumbnail_name else None
            try:
                # expires: a request that already timed out shouldn't leave work queued.
                pending = run_prediction.apply_async(
                    (headline, path), expires=settings.PREDICT_TIMEOUT_SECONDS
                )
                reply = pending.get(timeout=settings.PREDICT_TIMEOUT_SECONDS)
                result = reply["result"]
                model_version = reply["model_version"]
            except (OperationalError, RedisConnectionError):
                return Response({"detail": SERVICE_DOWN}, status=503)
            except CeleryTimeoutError:
                return Response(
                    {"detail": "The model is still loading or busy. Try again in a minute."},
                    status=503,
                )
            except Exception:
                # get() re-raises worker-side errors; keep the response JSON.
                logger.exception("Prediction task failed")
                return Response(
                    {"detail": "Something went wrong while analyzing this. Try again."},
                    status=500,
                )
            # Filed under the worker's stamp, not the web's own view of the file.
            cache.set(
                predict_cache_key(headline, image_bytes, model_version),
                result,
                settings.PREDICT_CACHE_TTL,
            )

        owner = (
            {"user": request.user}
            if request.user.is_authenticated
            else {"session_key": ensure_session_key(request)}
        )
        Scan.objects.create(
            headline=headline,
            thumbnail=thumbnail_name,
            label=result["label"],
            confidence=result["confidence"],
            clickbait_probability=result["clickbait_probability"],
            headline_probability=result["headline_probability"],
            thumbnail_probability=result["thumbnail_probability"],
            signals=result["signals"],
            model_version=model_version,
            **owner,
        )
        return Response(result)


class HealthView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = []

    def get(self, request):
        try:
            connection.ensure_connection()
            database = True
        except DatabaseError:
            database = False
        try:
            worker = bool(celery_app.control.ping(timeout=1))
        except Exception:
            logger.warning("Worker ping failed", exc_info=True)
            worker = False
        return Response(
            {
                "status": "ok" if database and worker else "degraded",
                "database": database,
                "worker": worker,
                "model_version": current_model_version(),
            }
        )


class HistoryView(ListAPIView):
    serializer_class = ScanHistorySerializer

    def get_queryset(self):
        if self.request.user.is_authenticated:
            scans = Scan.objects.filter(user=self.request.user)
        else:
            # No session yet means no scans. Never match the empty key of user-owned rows.
            key = self.request.session.session_key
            if not key:
                return Scan.objects.none()
            scans = Scan.objects.filter(user=None, session_key=key)
        return scans.order_by("-created_at", "-id")


class AdminHistoryView(ListAPIView):
    permission_classes = [IsAdminUser]
    serializer_class = AdminScanSerializer

    def get_queryset(self):
        return Scan.objects.select_related("user").order_by("-created_at", "-id")
