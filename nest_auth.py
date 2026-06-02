from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

import jwt

from config import (
    JWT_AUDIENCE,
    JWT_ISSUER,
    JWT_PUBLIC_KEY,
    JWT_SECRET,
    NEST_JWT_PUBLIC_KEY_URL,
    logger,
)


ADMIN_ROLES = {
    "admin",
    "teacher",
    "PLATFORM_OWNER",
    "SCHOOL_OWNER",
    "SCHOOL_ADMIN",
    "ASSISTANT_ADMIN",
    "CLASS_TEACHER",
    "SUBJECT_TEACHER",
    "STAFF",
}


@dataclass(frozen=True)
class VerifiedIdentity:
    user_id: str
    role: str
    school_id: Optional[str]
    claims: Dict[str, Any]
    source: str

    @property
    def is_admin(self) -> bool:
        return self.role in ADMIN_ROLES or self.role.upper() in ADMIN_ROLES


_cached_public_key: Optional[str] = None


def _load_public_key() -> Optional[str]:
    global _cached_public_key
    if _cached_public_key:
        return _cached_public_key

    if JWT_PUBLIC_KEY and JWT_PUBLIC_KEY.strip():
        _cached_public_key = JWT_PUBLIC_KEY.replace("\\n", "\n").strip()
        return _cached_public_key

    if not NEST_JWT_PUBLIC_KEY_URL:
        return None

    try:
        import urllib.request

        with urllib.request.urlopen(NEST_JWT_PUBLIC_KEY_URL, timeout=5) as resp:
            body = resp.read().decode("utf-8")
        import json

        payload = json.loads(body)
        data = payload.get("data") if isinstance(payload, dict) else None
        public_key = None
        if isinstance(data, dict):
            public_key = data.get("publicKey") or data.get("public_key")
        if not public_key and isinstance(payload, dict):
            public_key = payload.get("publicKey") or payload.get("public_key")
        if public_key:
            _cached_public_key = str(public_key).replace("\\n", "\n").strip()
            return _cached_public_key
    except Exception as exc:
        logger.warning(f"[auth] Could not fetch Nest JWT public key: {exc}")

    return None


def _identity_from_claims(claims: Dict[str, Any], source: str) -> VerifiedIdentity:
    user_id = claims.get("sub") or claims.get("userId") or claims.get("user_id")
    if not user_id:
        raise jwt.InvalidTokenError("Token missing subject claim")
    role = str(claims.get("role") or "student")
    school_id = claims.get("schoolId") or claims.get("tenantId") or claims.get("school_id")
    return VerifiedIdentity(
        user_id=str(user_id),
        role=role,
        school_id=str(school_id) if school_id else None,
        claims=claims,
        source=source,
    )


def verify_bearer_token(token: str) -> VerifiedIdentity:
    """Verify either a Nest-issued JWT or the legacy local Student Copilot JWT."""
    public_key = _load_public_key()
    if public_key:
        try:
            claims = jwt.decode(
                token,
                public_key,
                algorithms=["RS256"],
                issuer=JWT_ISSUER,
                audience=JWT_AUDIENCE,
            )
            return _identity_from_claims(claims, "nest-rs256")
        except jwt.InvalidTokenError as exc:
            logger.debug(f"[auth] RS256 verification did not match token: {exc}")

    try:
        claims = jwt.decode(
            token,
            JWT_SECRET,
            algorithms=["HS256"],
            issuer=JWT_ISSUER,
            audience=JWT_AUDIENCE,
        )
        return _identity_from_claims(claims, "nest-hs256")
    except jwt.InvalidTokenError:
        pass

    claims = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    return _identity_from_claims(claims, "legacy-local")

