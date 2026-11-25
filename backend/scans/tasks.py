import logging
from dataclasses import asdict

from celery import shared_task
from celery.signals import worker_ready
from django.conf import settings

from . import inference

logger = logging.getLogger(__name__)


@worker_ready.connect
def load_model_on_start(**kwargs):
    # Celery's Signal.send swallows handler exceptions, so a plain raise would
    # still leave a "ready" worker. SystemExit isn't an Exception, so it gets through.
    try:
        _, version = inference.get_detector()
    except Exception:
        logger.exception("Could not load the model from %s", settings.CLICKBAIT_MODEL_PATH)
        raise SystemExit(1)
    logger.info("Model loaded (version %s)", version)


@shared_task
def run_prediction(headline: str, thumbnail_path: str | None) -> dict:
    row = {"headline": headline, "thumbnail_path": thumbnail_path}
    detector, version = inference.get_detector()
    result = detector.predict([row])[0]
    # The web files the answer under the version of the model that produced it.
    return {"result": asdict(result), "model_version": version}
