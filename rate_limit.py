"""Shared SlowAPI limiter — Redis when configured, in-memory fallback in compute mode.

Rate-limit key prefers the JWT subject over the client IP: on the compute path
every request arrives from the Nest backend's IP, so IP-based buckets would
throttle all students together instead of per user. The unverified decode is
safe here because it only picks the bucket; signature verification still
happens in the auth dependency.
"""

import jwt
from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

import config


def _rate_limit_key(request: Request) -> str:
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        token = auth[7:].strip()
        try:
            claims = jwt.decode(token, options={"verify_signature": False})
            sub = claims.get("sub")
            if sub:
                return f"user:{sub}"
        except jwt.PyJWTError:
            pass
    return get_remote_address(request)


_storage_uri = config.REDIS_URL if config.REDIS_URL else "memory://"
limiter = Limiter(key_func=_rate_limit_key, storage_uri=_storage_uri)
