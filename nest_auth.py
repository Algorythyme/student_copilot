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

STUDENT_COPILOT_ROLES = {
    "STUDENT",
    "student",
}

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
    email: Optional[str]
    claims: Dict[str, Any]
    source: str

    @property
    def is_admin(self) -> bool:
        return self.role in ADMIN_ROLES or self.role.upper() in ADMIN_ROLES


_cached_public_key: Optional[str] = None


def is_student_copilot_role(role: str) -> bool:
    normalized = (role or "").upper()
    return normalized in {r.upper() for r in STUDENT_COPILOT_ROLES} or role in STUDENT_COPILOT_ROLES


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
        import json
        import urllib.request

        with urllib.request.urlopen(NEST_JWT_PUBLIC_KEY_URL, timeout=5) as resp:
            body = resp.read().decode("utf-8")
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
        logger.warning("[auth] Could not fetch Nest JWT public key: %s", exc)

    return None


def _identity_from_claims(claims: Dict[str, Any], source: str) -> VerifiedIdentity:
    user_id = claims.get("sub") or claims.get("userId") or claims.get("user_id")
    if not user_id:
        raise jwt.InvalidTokenError("Token missing subject claim")
    school_id = claims.get("schoolId") or claims.get("tenantId") or claims.get("school_id")
    return VerifiedIdentity(
        user_id=str(user_id),
        role=str(claims.get("role") or "student"),
        school_id=str(school_id) if school_id else None,
        email=claims.get("email"),
        claims=claims,
        source=source,
    )


def identity_from_token_unverified(token: str) -> VerifiedIdentity:
    """Read Nest claims without signature check — staging/dev only when AUTH_DISABLED."""
    claims = jwt.decode(
        token,
        options={
            "verify_signature": False,
            "verify_exp": False,
            "verify_aud": False,
            "verify_iss": False,
        },
    )
    return _identity_from_claims(claims, "disabled")


def verify_bearer_token(token: str) -> VerifiedIdentity:
    decode_opts = {
        "issuer": JWT_ISSUER,
        "audience": JWT_AUDIENCE,
    }

    try:
        header = jwt.get_unverified_header(token)
    except jwt.DecodeError as exc:
        raise jwt.InvalidTokenError("Invalid token header") from exc

    alg = (header.get("alg") or "").upper()

    if alg == "RS256":
        public_key = _load_public_key()
        if not public_key:
            raise jwt.InvalidTokenError(
                "Token is RS256 but Nest public key is not configured "
                "(set JWT_PUBLIC_KEY or NEST_JWT_PUBLIC_KEY_URL)"
            )
        claims = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            **decode_opts,
        )
        return _identity_from_claims(claims, "nest-rs256")

    if alg == "HS256":
        if JWT_SECRET:
            try:
                claims = jwt.decode(
                    token,
                    JWT_SECRET,
                    algorithms=["HS256"],
                    **decode_opts,
                )
                return _identity_from_claims(claims, "nest-hs256")
            except jwt.InvalidTokenError:
                pass
        try:
            claims = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
            return _identity_from_claims(claims, "legacy-local")
        except jwt.InvalidTokenError as exc:
            raise jwt.InvalidTokenError(
                "Signature verification failed — JWT_SECRET must match school_management_backend"
            ) from exc

    raise jwt.InvalidTokenError(f"Unsupported JWT algorithm: {alg or 'unknown'}")
