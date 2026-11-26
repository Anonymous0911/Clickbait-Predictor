import pytest
from django.core.cache import cache

from config import celery_app


@pytest.fixture(autouse=True)
def _locmem_cache(settings):
    # Tests never talk to Redis.
    settings.CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
    settings.CELERY_TASK_ALWAYS_EAGER = True
    cache.clear()


@pytest.fixture(autouse=True)
def _celery_eager():
    # Settings are already read into conf, so set it there too.
    conf = celery_app.conf
    old = (conf.task_always_eager, conf.task_eager_propagates)
    conf.task_always_eager = True
    conf.task_eager_propagates = True
    yield
    conf.task_always_eager, conf.task_eager_propagates = old


@pytest.fixture
def fake_detector(monkeypatch):
    from tests.fakes import FakeDetector

    from scans import inference

    detector = FakeDetector()
    # Same version the web reads from the file, so cache tests can hit.
    monkeypatch.setattr(
        "scans.inference.get_detector", lambda: (detector, inference.current_model_version())
    )
    return detector


@pytest.fixture(autouse=True)
def _clear_model_version_cache():
    # Cached version would leak between tests and break cache-key tests.
    from scans import inference

    inference._file_version.cache_clear()
    yield
    inference._file_version.cache_clear()


@pytest.fixture(autouse=True)
def _tmp_media(settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path / "media")
