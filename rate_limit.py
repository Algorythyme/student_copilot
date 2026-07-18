"""Shared SlowAPI limiter — Redis when configured, in-memory fallback in compute mode."""

from slowapi import Limiter
from slowapi.util import get_remote_address

import config

_storage_uri = config.REDIS_URL if config.REDIS_URL else "memory://"
limiter = Limiter(key_func=get_remote_address, storage_uri=_storage_uri)
