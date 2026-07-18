"""Stateless compute API routes for SMS integration."""

from fastapi import APIRouter, Depends, HTTPException, Request

import compute_service
from compute_models import (
    ComputeChatRequest,
    ComputeChatResponse,
    ComputeEvaluateSessionRequest,
    ComputeEvaluateSessionResponse,
    ComputeRevisionEvaluateRequest,
    ComputeRevisionEvaluateResponse,
    ComputeRevisionGenerateRequest,
    ComputeRevisionGenerateResponse,
    ComputeSummarizeRequest,
    ComputeSummarizeResponse,
)
from config import RATE_LIMIT_CHAT, RATE_LIMIT_GENERATE, logger
from nest_auth import VerifiedIdentity
from rate_limit import limiter
from security import get_current_identity

router = APIRouter(prefix="/api/v1/compute", tags=["Compute API"])


@router.post("/chat", response_model=ComputeChatResponse)
@limiter.limit(RATE_LIMIT_CHAT)
async def compute_chat(
    request: Request,
    payload: ComputeChatRequest,
    identity: VerifiedIdentity = Depends(get_current_identity),
) -> ComputeChatResponse:
    logger.info(
        "[compute] chat user=%s school=%s history_len=%d chunks=%d",
        identity.user_id,
        identity.school_id,
        len(payload.message_history),
        len(payload.context_chunks),
    )
    try:
        result = await compute_service.compute_chat(payload)
        return ComputeChatResponse(**result)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("[compute] chat failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Chat processing failed.") from exc


@router.post("/revision/generate", response_model=ComputeRevisionGenerateResponse)
@limiter.limit(RATE_LIMIT_GENERATE)
async def compute_revision_generate(
    request: Request,
    payload: ComputeRevisionGenerateRequest,
    identity: VerifiedIdentity = Depends(get_current_identity),
) -> ComputeRevisionGenerateResponse:
    logger.info(
        "[compute] revision/generate user=%s subject=%s",
        identity.user_id,
        payload.subject,
    )
    try:
        result = await compute_service.compute_revision_generate(payload)
        return ComputeRevisionGenerateResponse(**result)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("[compute] revision/generate failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Exam generation failed.") from exc


@router.post("/revision/evaluate", response_model=ComputeRevisionEvaluateResponse)
@limiter.limit(RATE_LIMIT_GENERATE)
async def compute_revision_evaluate(
    request: Request,
    payload: ComputeRevisionEvaluateRequest,
    identity: VerifiedIdentity = Depends(get_current_identity),
) -> ComputeRevisionEvaluateResponse:
    logger.info(
        "[compute] revision/evaluate user=%s subject=%s",
        identity.user_id,
        payload.subject,
    )
    try:
        result = await compute_service.compute_revision_evaluate(payload)
        return ComputeRevisionEvaluateResponse(**result)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("[compute] revision/evaluate failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Exam evaluation failed.") from exc


@router.post("/summarize", response_model=ComputeSummarizeResponse)
@limiter.limit(RATE_LIMIT_GENERATE)
async def compute_summarize(
    request: Request,
    payload: ComputeSummarizeRequest,
    identity: VerifiedIdentity = Depends(get_current_identity),
) -> ComputeSummarizeResponse:
    logger.info("[compute] summarize user=%s chars=%d", identity.user_id, len(payload.text))
    try:
        result = await compute_service.compute_summarize(payload)
        return ComputeSummarizeResponse(**result)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("[compute] summarize failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Summarization failed.") from exc


@router.post("/evaluate-session", response_model=ComputeEvaluateSessionResponse)
@limiter.limit(RATE_LIMIT_GENERATE)
async def compute_evaluate_session(
    request: Request,
    payload: ComputeEvaluateSessionRequest,
    identity: VerifiedIdentity = Depends(get_current_identity),
) -> ComputeEvaluateSessionResponse:
    logger.info(
        "[compute] evaluate-session user=%s messages=%d",
        identity.user_id,
        len(payload.message_history),
    )
    try:
        result = await compute_service.compute_evaluate_session(payload)
        return ComputeEvaluateSessionResponse(**result)
    except Exception as exc:
        logger.error("[compute] evaluate-session failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Session evaluation failed.") from exc
