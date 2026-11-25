import hashlib

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

from .models import Scan

# Some phone JPEGs (MPO trailers) are reported as MPO.
EXTENSIONS = {"JPEG": "jpg", "MPO": "jpg", "PNG": "png", "WEBP": "webp"}


def predict_cache_key(headline: str, image_bytes: bytes | None, model_version: str) -> str:
    digest = hashlib.sha256(headline.encode() + b"\0" + (image_bytes or b"")).hexdigest()
    return f"scan:v1:{model_version}:{digest}"


def store_thumbnail(image_bytes: bytes, pillow_format: str) -> str:
    # Content-hash name only, so a user-supplied filename never touches the disk.
    name = f"thumbnails/{hashlib.sha256(image_bytes).hexdigest()}.{EXTENSIONS[pillow_format]}"
    if not default_storage.exists(name):
        default_storage.save(name, ContentFile(image_bytes))
    return name


def ensure_session_key(request) -> str:
    if not request.session.session_key:
        request.session.save()
    return request.session.session_key


def claim_guest_scans(session_key: str | None, user) -> int:
    """Move a guest session's scans onto the account that just signed in."""
    if not session_key:
        return 0
    return Scan.objects.filter(user=None, session_key=session_key).update(
        user=user, session_key=""
    )
