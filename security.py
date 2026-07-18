"""Nest-first and Supabase auth for Student Copilot."""

from __future__ import annotations

from typing import Optional

import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from config import (
    AUTH_DISABLED,
    AUTH_DISABLED_ROLE,
    AUTH_DISABLED_USER_ID,
    DEPLOY_MODE,
    ENABLE_NEST_AUTH,
    ENABLE_STANDALONE_AUTH,
    ENABLE_SUPABASE_AUTH,
    IS_COMPUTE_MODE,
    SMS_SCHOOL_ID,
    logger,
    validate_safe_string,
)
from nest_auth import (
    VerifiedIdentity,
    identity_from_token_unverified,
    is_student_copilot_role,
    verify_bearer_token,
)
from supabase_auth import is_likely_supabase_token, verify_supabase_token

bearer_scheme = HTTPBearer(auto_error=False)


def ensure_user_profile(identity: VerifiedIdentity) -> None:
    """Upsert a minimal student row from Nest or Supabase JWT claims (web/full only)."""
    if IS_COMPUTE_MODE:
        return

    if identity.source not in ("nest-rs256", "nest-hs256", "disabled", "supabase"):
        return

    from database import get_db_store

    store = get_db_store()
    if not store:
        return

    user_id = validate_safe_string(identity.user_id, "user_id")
    full_name = (
        identity.email
        or identity.claims.get("name")
        or identity.claims.get("full_name")
        or user_id
    )
    metadata = identity.claims.get("user_metadata") or {}
    if isinstance(metadata, dict):
        full_name = metadata.get("full_name") or metadata.get("name") or full_name

    row = {
        "user_id": user_id,
        "username": user_id,
        "role": identity.role or "student",
        "full_name": str(full_name),
        "school_id": identity.school_id or SMS_SCHOOL_ID or "",
        "country": "",
        "class_id": "",
        "subjects": "",
        "learning_method": "",
    }
    existing = store.table("users").select("user_id").eq("user_id", user_id).execute()
    try:
        if existing.data:
            store.table("users").update(
                {
                    "role": row["role"],
                    "full_name": row["full_name"],
                    "school_id": row["school_id"],
                }
            ).eq("user_id", user_id).execute()
        else:
            store.table("users").insert(row).execute()
            logger.info("[auth] Created student_copilot user from JWT: %s", user_id)
    except Exception as exc:
        logger.error("[auth] Failed to ensure user profile for %s: %s", user_id, exc)


def _verify_nest_token(token: str) -> VerifiedIdentity:
    identity = verify_bearer_token(token)
    if not is_student_copilot_role(identity.role) and not identity.is_admin:
        raise HTTPException(
            status_code=403,
            detail="Role not permitted for Student Copilot",
        )
    return identity


def _resolve_identity_from_token(token: str) -> VerifiedIdentity:
    if ENABLE_SUPABASE_AUTH and is_likely_supabase_token(token):
        try:
            return verify_supabase_token(token)
        except jwt.InvalidTokenError:
            if DEPLOY_MODE == "web" and not ENABLE_NEST_AUTH and not ENABLE_STANDALONE_AUTH:
                raise HTTPException(status_code=401, detail="Invalid Supabase token.")

    if ENABLE_NEST_AUTH or ENABLE_STANDALONE_AUTH:
        return _verify_nest_token(token)

    raise HTTPException(status_code=401, detail="No auth provider enabled for this deploy mode.")


async def get_current_identity(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> VerifiedIdentity:
    token = credentials.credentials if credentials and credentials.credentials else None

    if AUTH_DISABLED:
        if not token:
            identity = VerifiedIdentity(
                user_id=AUTH_DISABLED_USER_ID,
                role=AUTH_DISABLED_ROLE,
                school_id=SMS_SCHOOL_ID,
                email="auth-disabled@pedagic.local",
                claims={},
                source="disabled-anonymous",
            )
        else:
            try:
                identity = identity_from_token_unverified(token)
                identity = VerifiedIdentity(
                    user_id=identity.user_id,
                    role=identity.role,
                    school_id=identity.school_id,
                    email=identity.email,
                    claims=identity.claims,
                    source="disabled",
                )
            except jwt.InvalidTokenError as exc:
                logger.warning("[auth] AUTH_DISABLED: invalid token, using anonymous: %s", exc)
                identity = VerifiedIdentity(
                    user_id=AUTH_DISABLED_USER_ID,
                    role=AUTH_DISABLED_ROLE,
                    school_id=SMS_SCHOOL_ID,
                    email="auth-disabled@pedagic.local",
                    claims={},
                    source="disabled-anonymous",
                )
    else:
        if not token:
            raise HTTPException(
                status_code=401,
                detail="Authentication required. Send a valid Bearer token.",
            )
        try:
            identity = _resolve_identity_from_token(token)
        except HTTPException:
            raise
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=401,
                detail="Token has expired. Please re-authenticate.",
            )
        except jwt.InvalidTokenError:
            raise HTTPException(status_code=401, detail="Invalid authentication token.")

    identity_user_id = validate_safe_string(identity.user_id, "user_id")
    request.state.user_role = identity.role
    request.state.school_id = identity.school_id
    request.state.auth_source = identity.source
    request.state.current_identity = identity

    if not IS_COMPUTE_MODE and identity.source in (
        "nest-rs256",
        "nest-hs256",
        "disabled",
        "supabase",
    ):
        ensure_user_profile(identity)

    return VerifiedIdentity(
        user_id=identity_user_id,
        role=identity.role,
        school_id=identity.school_id,
        email=identity.email,
        claims=identity.claims,
        source=identity.source,
    )


async def get_current_user(
    request: Request,
    identity: VerifiedIdentity = Depends(get_current_identity),
) -> str:
    return validate_safe_string(identity.user_id, "user_id")
