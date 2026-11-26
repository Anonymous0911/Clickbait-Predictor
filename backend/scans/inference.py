import hashlib
import os
from functools import cache, lru_cache

from django.conf import settings


@lru_cache(maxsize=1)
def _file_version(path, mtime_ns, size):
    # mtime and size are only cache keys: a changed file gets re-hashed.
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()[:12]


def current_model_version() -> str:
    path = settings.CLICKBAIT_MODEL_PATH
    try:
        st = os.stat(path)
        return _file_version(path, st.st_mtime_ns, st.st_size)
    except FileNotFoundError:
        # Not cached, so it fixes itself once the file shows up.
        return "unknown"


@cache
def get_detector():
    # Imported here so only the Celery worker ever pulls in torch.
    from clickbait_model import ClickbaitDetector

    # Read the version right at load time: it names the copy in memory,
    # even if the file changes later.
    version = current_model_version()
    return ClickbaitDetector.load(settings.CLICKBAIT_MODEL_PATH), version
