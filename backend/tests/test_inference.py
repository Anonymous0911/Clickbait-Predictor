import pytest


def test_run_prediction_returns_api_shape(fake_detector):
    from scans import inference
    from scans.tasks import run_prediction
    reply = run_prediction.delay("You won't believe this", None).get()
    assert reply["model_version"] == inference.current_model_version()
    out = reply["result"]
    assert out["label"] == "clickbait"
    assert out["clickbait_probability"] == 0.9
    assert abs(out["not_clickbait_probability"] - 0.1) < 1e-9
    assert set(out["signals"]) == {"curiosity_gap", "sensational_wording", "excessive_capitalization", "question_style", "exclamation_emphasis"}


def test_model_version_is_12_hex(settings, tmp_path):
    from scans import inference
    f = tmp_path / "m.joblib"; f.write_bytes(b"abc")
    settings.CLICKBAIT_MODEL_PATH = str(f)
    assert inference.current_model_version() == "ba7816bf8f01"


def test_model_version_follows_file_change(settings, tmp_path):
    from scans import inference
    f = tmp_path / "m.joblib"; f.write_bytes(b"abc")
    settings.CLICKBAIT_MODEL_PATH = str(f)
    first = inference.current_model_version()
    f.write_bytes(b"abcdef")
    assert inference.current_model_version() != first


def test_model_version_missing_file(settings, tmp_path):
    from scans import inference
    settings.CLICKBAIT_MODEL_PATH = str(tmp_path / "nope.joblib")
    assert inference.current_model_version() == "unknown"


def test_unknown_version_is_not_cached(settings, tmp_path):
    from scans import inference
    f = tmp_path / "m.joblib"
    settings.CLICKBAIT_MODEL_PATH = str(f)
    assert inference.current_model_version() == "unknown"
    f.write_bytes(b"abc")
    assert inference.current_model_version() == "ba7816bf8f01"


def test_worker_start_exits_when_model_cannot_load(monkeypatch):
    from scans import tasks

    def boom():
        raise FileNotFoundError("nope")

    monkeypatch.setattr("scans.inference.get_detector", boom)
    with pytest.raises(SystemExit):
        tasks.load_model_on_start()


def test_web_modules_never_import_the_model():
    import subprocess, sys
    code = ("import django, os; os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings'); django.setup();"
            "import scans.views, scans.tasks, scans.services, accounts.views, sys;"
            "assert 'clickbait_model' not in sys.modules and 'torch' not in sys.modules")
    assert subprocess.run([sys.executable, "-c", code]).returncode == 0
