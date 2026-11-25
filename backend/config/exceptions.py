import logging

from kombu.exceptions import OperationalError
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError
from rest_framework.response import Response
from rest_framework.views import exception_handler

logger = logging.getLogger(__name__)

# Throttles and the cache hit Redis before a view's own try block runs.
BACKEND_DOWN = (RedisConnectionError, RedisTimeoutError, OperationalError)


def _first_message(data):
    """First message found, depth-first."""
    if isinstance(data, dict):
        for value in data.values():
            found = _first_message(value)
            if found:
                return found
    elif isinstance(data, (list, tuple)):
        for value in data:
            found = _first_message(value)
            if found:
                return found
    elif data is not None:
        return str(data)
    return None


def flat_exception_handler(exc, context):
    if isinstance(exc, BACKEND_DOWN):
        logger.warning("Redis or broker unreachable: %r", exc)
        return Response(
            {"detail": "The service is temporarily unavailable. Try again in a minute."},
            status=503,
        )
    response = exception_handler(exc, context)
    if response is None:
        return None
    data = response.data
    if isinstance(data, dict) and set(data) == {"detail"} and isinstance(data["detail"], str):
        return response
    response.data = {"detail": _first_message(data) or "Request failed."}
    return response
