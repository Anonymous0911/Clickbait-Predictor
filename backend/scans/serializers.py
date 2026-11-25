import io

from PIL import Image, UnidentifiedImageError
from rest_framework import serializers

from .models import Scan
from .services import EXTENSIONS

MAX_HEADLINE_CHARS = 500
MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_PIXELS = 40_000_000


class PredictInputSerializer(serializers.Serializer):
    """Validation only. validate() leaves headline (stripped), image_bytes and image_format."""

    headline = serializers.CharField(required=False, allow_blank=True, trim_whitespace=False)
    thumbnail = serializers.FileField(required=False, allow_empty_file=True)

    def validate(self, attrs):
        raw = attrs.get("headline", "")
        upload = attrs.get("thumbnail")
        headline = raw.strip()

        if not headline and upload is None:
            raise serializers.ValidationError("Add a headline or a thumbnail before analyzing.")
        if len(raw) > MAX_HEADLINE_CHARS:
            raise serializers.ValidationError("Headlines can be at most 500 characters.")

        image_bytes = image_format = None
        if upload is not None:
            # Size first, so we never read an oversized body into memory.
            if upload.size > MAX_UPLOAD_BYTES:
                raise serializers.ValidationError("Images can be at most 5 MB.")
            image_bytes = upload.read()
            image_format = self._check_image(image_bytes)

        return {"headline": headline, "image_bytes": image_bytes, "image_format": image_format}

    @staticmethod
    def _check_image(data: bytes) -> str:
        bad_format = serializers.ValidationError("Upload a PNG, JPEG or WebP image.")
        try:
            image = Image.open(io.BytesIO(data))
            image_format = image.format
            width, height = image.size  # from the header, no decoding
            image.verify()
        except Image.DecompressionBombError:
            raise serializers.ValidationError("That image is too large to process.")
        except (UnidentifiedImageError, OSError, SyntaxError, ValueError):
            raise bad_format
        if image_format not in EXTENSIONS:
            raise bad_format
        if width * height > MAX_PIXELS:
            raise serializers.ValidationError("That image is too large to process.")
        return image_format


class ScanHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Scan
        fields = ["id", "headline", "label", "clickbait_probability", "confidence", "created_at"]
        read_only_fields = fields


class AdminScanSerializer(ScanHistorySerializer):
    username = serializers.CharField(source="user.username", default=None, read_only=True)

    class Meta(ScanHistorySerializer.Meta):
        fields = ScanHistorySerializer.Meta.fields + ["username"]
        read_only_fields = fields
