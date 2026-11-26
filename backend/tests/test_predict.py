import io
from unittest.mock import MagicMock

import pytest
from celery.exceptions import TimeoutError as CeleryTimeoutError
from django.core.files.uploadedfile import SimpleUploadedFile
from kombu.exceptions import OperationalError
from django.conf import settings as django_settings
from PIL import Image
from redis.exceptions import ConnectionError as RedisConnectionError
from rest_framework.test import APIClient

from accounts.models import User
from scans.models import Scan
from scans.throttles import ScanAnonThrottle

URL = "/api/predict"
EMPTY = "Add a headline or a thumbnail before analyzing."
LENGTH = "Headlines can be at most 500 characters."
SIZE = "Images can be at most 5 MB."
FORMAT = "Upload a PNG, JPEG or WebP image."
TOO_LARGE = "That image is too large to process."
LOADING = "The model is still loading or busy. Try again in a minute."
DOWN = "The prediction service isn't running right now."


@pytest.fixture
def client():
    return APIClient()


def png_bytes(size=(10, 10), mode="RGB"):
    buf = io.BytesIO()
    Image.new(mode, size).save(buf, format="PNG")
    return buf.getvalue()


def png_upload(name="t.png", **kw):
    return SimpleUploadedFile(name, png_bytes(**kw), content_type="image/png")


@pytest.mark.django_db
def test_headline_only(client, fake_detector):
    r = client.post(URL, {"headline": "You won't believe this"}, format="multipart")
    assert r.status_code == 200
    assert r.json()["label"] == "clickbait"
    scan = Scan.objects.get()
    assert scan.headline == "You won't believe this"
    assert scan.session_key


@pytest.mark.django_db
def test_image_only(client, fake_detector):
    r = client.post(URL, {"thumbnail": png_upload()}, format="multipart")
    assert r.status_code == 200
    name = Scan.objects.get().thumbnail.name
    assert name.startswith("thumbnails/") and name.endswith(".png")


@pytest.mark.django_db
def test_headline_and_image(client, fake_detector):
    r = client.post(URL, {"headline": "hello", "thumbnail": png_upload()}, format="multipart")
    assert r.status_code == 200


@pytest.mark.django_db
@pytest.mark.parametrize("headline", ["", "   "])
def test_empty_and_whitespace_rejected(client, fake_detector, headline):
    r = client.post(URL, {"headline": headline}, format="multipart")
    assert r.status_code == 400
    assert r.json()["detail"] == EMPTY
    assert fake_detector.calls == 0


@pytest.mark.django_db
def test_headline_length_boundary(client, fake_detector):
    assert client.post(URL, {"headline": "a" * 500}, format="multipart").status_code == 200
    r = client.post(URL, {"headline": "a" * 501}, format="multipart")
    assert r.status_code == 400
    assert r.json()["detail"] == LENGTH


@pytest.mark.django_db
def test_fake_image_rejected(client, fake_detector):
    f = SimpleUploadedFile("x.jpg", b"not an image", content_type="image/jpeg")
    r = client.post(URL, {"thumbnail": f}, format="multipart")
    assert r.status_code == 400
    assert r.json()["detail"] == FORMAT
    assert fake_detector.calls == 0


@pytest.mark.django_db
def test_oversized_upload_rejected(client, fake_detector):
    f = SimpleUploadedFile("big.png", b"\0" * (5 * 1024 * 1024 + 1), content_type="image/png")
    r = client.post(URL, {"thumbnail": f}, format="multipart")
    assert r.status_code == 400
    assert r.json()["detail"] == SIZE
    assert fake_detector.calls == 0


@pytest.mark.django_db
def test_pixel_bomb_rejected(client, fake_detector):
    data = png_bytes(size=(10000, 5000), mode="1")
    assert len(data) < 5 * 1024 * 1024
    f = SimpleUploadedFile("bomb.png", data, content_type="image/png")
    r = client.post(URL, {"thumbnail": f}, format="multipart")
    assert r.status_code == 400
    assert r.json()["detail"] == TOO_LARGE
    assert fake_detector.calls == 0


@pytest.mark.django_db
def test_unicode_headline(client, fake_detector):
    r = client.post(URL, {"headline": "यह खबर आपको चौंका देगी 😱"}, format="multipart")
    assert r.status_code == 200


@pytest.mark.django_db
def test_cache_hit_skips_model(client, fake_detector):
    for _ in range(2):
        assert client.post(URL, {"headline": "same one"}, format="multipart").status_code == 200
    assert fake_detector.calls == 1
    assert Scan.objects.count() == 2


@pytest.mark.django_db
def test_model_file_change_misses_cache(client, fake_detector, settings, tmp_path):
    f = tmp_path / "m.joblib"
    f.write_bytes(b"old model")
    settings.CLICKBAIT_MODEL_PATH = str(f)
    client.post(URL, {"headline": "same one"}, format="multipart")
    f.write_bytes(b"a different, longer model file")
    client.post(URL, {"headline": "same one"}, format="multipart")
    assert fake_detector.calls == 2


@pytest.mark.django_db
def test_worker_version_stamps_row(client, fake_detector, settings, tmp_path, monkeypatch):
    f = tmp_path / "m.joblib"
    f.write_bytes(b"web sees this file")
    settings.CLICKBAIT_MODEL_PATH = str(f)
    monkeypatch.setattr("scans.inference.get_detector", lambda: (fake_detector, "aaaaaaaaaaaa"))
    client.post(URL, {"headline": "same one"}, format="multipart")
    assert Scan.objects.get().model_version == "aaaaaaaaaaaa"
    # Filed under the worker's stamp, not the file's, so the lookup misses.
    client.post(URL, {"headline": "same one"}, format="multipart")
    assert fake_detector.calls == 2


@pytest.mark.django_db
def test_cache_hit_still_records_scan_per_user(fake_detector):
    a = User.objects.create_user(username="a", password="pw-12345-xyz")
    b = User.objects.create_user(username="b", password="pw-12345-xyz")
    for user in (a, b):
        c = APIClient()
        c.force_login(user)
        assert c.post(URL, {"headline": "shared"}, format="multipart").status_code == 200
    assert Scan.objects.filter(user=a).count() == 1
    assert Scan.objects.filter(user=b).count() == 1
    assert fake_detector.calls == 1


@pytest.mark.django_db
def test_predict_timeout_returns_503(client, fake_detector, monkeypatch):
    pending = MagicMock()
    pending.get.side_effect = CeleryTimeoutError()
    monkeypatch.setattr("scans.views.run_prediction.apply_async", lambda *a, **k: pending)
    r = client.post(URL, {"headline": "hi"}, format="multipart")
    assert r.status_code == 503
    assert r.json()["detail"] == LOADING


@pytest.mark.django_db
def test_predict_broker_down_returns_503(client, fake_detector, monkeypatch):
    def boom(*a, **k):
        raise OperationalError("redis is gone")

    monkeypatch.setattr("scans.views.run_prediction.apply_async", boom)
    r = client.post(URL, {"headline": "hi"}, format="multipart")
    assert r.status_code == 503
    assert r.json()["detail"] == DOWN


@pytest.mark.django_db
def test_guest_throttle(client, fake_detector, monkeypatch):
    monkeypatch.setattr(ScanAnonThrottle, "THROTTLE_RATES", {"scan_anon": "2/min"})
    responses = [client.post(URL, {"headline": f"h{i}"}, format="multipart") for i in range(3)]
    assert [r.status_code for r in responses] == [200, 200, 429]
    assert isinstance(responses[2].json()["detail"], str)


@pytest.mark.django_db
def test_health(client, monkeypatch):
    monkeypatch.setattr("config.celery_app.control.ping", lambda timeout=1: [{"w": {"ok": "pong"}}])
    body = client.get("/api/health").json()
    assert body["status"] == "ok" and body["database"] is True and body["worker"] is True
    assert "model_version" in body

    monkeypatch.setattr("config.celery_app.control.ping", lambda timeout=1: [])
    body = client.get("/api/health").json()
    assert body["status"] == "degraded" and body["worker"] is False


DEFAULT_RESULT = {
    "label": "clickbait",
    "confidence": 0.9,
    "clickbait_probability": 0.9,
    "not_clickbait_probability": 0.1,
    "headline_probability": 0.9,
    "thumbnail_probability": 0.5,
    "signals": {},
}


@pytest.mark.django_db
def test_task_failure_returns_json_500(client, fake_detector, monkeypatch):
    pending = MagicMock()
    pending.get.side_effect = RuntimeError("boom")
    monkeypatch.setattr("scans.views.run_prediction.apply_async", lambda *a, **k: pending)
    r = client.post(URL, {"headline": "hi"}, format="multipart")
    assert r.status_code == 500
    assert r["Content-Type"].startswith("application/json")
    assert r.json()["detail"] == "Something went wrong while analyzing this. Try again."


@pytest.mark.django_db
def test_result_backend_down_returns_503(client, fake_detector, monkeypatch):
    pending = MagicMock()
    pending.get.side_effect = RedisConnectionError("gone")
    monkeypatch.setattr("scans.views.run_prediction.apply_async", lambda *a, **k: pending)
    r = client.post(URL, {"headline": "hi"}, format="multipart")
    assert r.status_code == 503
    assert r.json()["detail"] == DOWN


@pytest.mark.django_db
def test_task_enqueued_with_expiry(client, fake_detector, monkeypatch):
    pending = MagicMock()
    pending.get.return_value = {"result": DEFAULT_RESULT, "model_version": "aaaaaaaaaaaa"}
    mock = MagicMock(return_value=pending)
    monkeypatch.setattr("scans.views.run_prediction.apply_async", mock)
    assert client.post(URL, {"headline": "hi"}, format="multipart").status_code == 200
    assert mock.call_args.kwargs["expires"] == django_settings.PREDICT_TIMEOUT_SECONDS


@pytest.mark.django_db
def test_mpo_jpeg_accepted(client, fake_detector):
    buf = io.BytesIO()
    img = Image.new("RGB", (10, 10))
    img.save(buf, format="MPO", save_all=True, append_images=[Image.new("RGB", (10, 10))])
    assert Image.open(io.BytesIO(buf.getvalue())).format == "MPO"
    f = SimpleUploadedFile("phone.jpg", buf.getvalue(), content_type="image/jpeg")
    r = client.post(URL, {"thumbnail": f}, format="multipart")
    assert r.status_code == 200
    assert Scan.objects.get().thumbnail.name.endswith(".jpg")


@pytest.mark.django_db
def test_health_ping_unexpected_error(client, monkeypatch):
    def boom(timeout=1):
        raise TimeoutError("slow")

    monkeypatch.setattr("config.celery_app.control.ping", boom)
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["worker"] is False and body["status"] == "degraded"


@pytest.mark.django_db
def test_redis_down_returns_json_503(client, settings):
    settings.CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": "redis://127.0.0.1:1/2",
        }
    }
    calls = [
        client.post(URL, {"headline": "hello there"}, format="multipart"),
        client.post("/api/auth/login", {"username": "a", "password": "b"}, format="json"),
    ]
    for r in calls:
        assert r.status_code == 503
        assert r["Content-Type"].startswith("application/json")
        assert isinstance(r.json()["detail"], str)
