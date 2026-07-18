"""Supabase JWT verification for web-mode demo auth."""

from __future__ import annotations

from typing import Optional

import jwt

from config import SUPABASE_JWT_SECRET, logger
from nest_auth import VerifiedIdentity


def verify_supabase_token(token: str) -> VerifiedIdentity:
    if not SUPABASE_JWT_SECRET:
        raise jwt.InvalidTokenError(
            "Supabase auth is not configured (SUPABASE_JWT_SECRET missing)."
        )

    claims = jwt.decode(
        token,
        SUPABASE_JWT_SECRET,
        algorithms=["HS256"],
        audience="authenticated",
        options={"require": ["sub", "exp"]},
    )
    user_id = claims.get("sub")
    if not user_id:
        raise jwt.InvalidTokenError("Supabase token missing subject claim.")

    role = str(claims.get("role") or "authenticated")
    email = claims.get("email")
    metadata = claims.get("user_metadata") or {}
    if isinstance(metadata, dict):
        full_name = metadata.get("full_name") or metadata.get("name")
    else:
        full_name = None

    return VerifiedIdentity(
        user_id=str(user_id),
        role="student",
        school_id=None,
        email=str(email or full_name or user_id),
        claims=claims,
        source="supabase",
    )


def is_likely_supabase_token(token: str) -> bool:
    """Heuristic: Supabase access tokens are HS256; Nest production tokens are RS256."""
    try:
        header = jwt.get_unverified_header(token)
        return (header.get("alg") or "").upper() == "HS256"
    except jwt.DecodeError:
        return False
