"""Bounded successful-output cache and single flight for identical contexts."""
import hashlib
import json
import threading
import time
from collections import OrderedDict
from concurrent.futures import Future

from app.config import settings
from app.services.ollama_service import OllamaService

LOCK = threading.Lock()
CACHE = OrderedDict()
IN_FLIGHT = {}
TTL_SECONDS = 300
MAX_ENTRIES = 128


def configuration_key():
    return hashlib.sha256(json.dumps([
        settings.OLLAMA_API_URL, settings.OLLAMA_MODEL,
        settings.OLLAMA_API_KEY, 'questions-v13',
    ]).encode()).hexdigest()[:24]


def generate_suggestions(product, timings):
    key = (configuration_key(), json.dumps(product, sort_keys=True, ensure_ascii=False))
    lookup_started = time.perf_counter()
    with LOCK:
        cached = CACHE.get(key)
        if cached and time.monotonic() - cached[0] < TTL_SECONDS:
            CACHE.move_to_end(key)
            timings.update(cache='hit', ollama_ms=0,
                           cache_lookup_ms=round((time.perf_counter() - lookup_started) * 1000, 3))
            return cached[1].model_copy(deep=True)
        CACHE.pop(key, None)
        future = IN_FLIGHT.get(key)
        owner = future is None
        if owner:
            if len(IN_FLIGHT) >= MAX_ENTRIES:
                raise RuntimeError('Suggestion service is busy')
            future = IN_FLIGHT[key] = Future()
    timings['cache_lookup_ms'] = round((time.perf_counter() - lookup_started) * 1000, 3)
    if not owner:
        started = time.perf_counter()
        timings['cache'] = 'in_flight'
        result = future.result(timeout=settings.SUGGESTION_TIMEOUT_SECONDS + 5)
        timings['in_flight_wait_ms'] = round((time.perf_counter() - started) * 1000, 3)
        return result.model_copy(deep=True)
    timings['cache'] = 'miss'
    generation_started = time.perf_counter()
    try:
        result = OllamaService().generate_suggestions(product, timings=timings)
        with LOCK:
            CACHE[key] = (time.monotonic(), result.model_copy(deep=True))
            while len(CACHE) > MAX_ENTRIES:
                CACHE.popitem(last=False)
        future.set_result(result)
        return result
    except BaseException as exc:
        if 'ollama_started' in timings and 'ollama_ms' not in timings:
            timings['ollama_ms'] = round((time.perf_counter() - generation_started) * 1000, 3)
        future.set_exception(exc)
        raise
    finally:
        with LOCK:
            IN_FLIGHT.pop(key, None)
