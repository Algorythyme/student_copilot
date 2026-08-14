"""Stateless compute API routes for SMS integration."""

import json
import time
from typing import Any, Awaitable, Dict

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

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


async def _run_compute(
    action: str,
    identity: VerifiedIdentity,
    coro: Awaitable[Dict[str, Any]],
    failure_detail: str,
) -> Dict[str, Any]:
    """Run a compute service call with uniform timing, logging and error mapping."""
    started = time.monotonic()
    try:
        result = await coro
    except ValueError as exc:
        logger.warning(
            "[compute] %s rejected after %.1fs (user=%s): %s",
            action, time.monotonic() - started, identity.user_id, exc,
        )
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.error(
            "[compute] %s failed after %.1fs (user=%s): %s",
            action, time.monotonic() - started, identity.user_id, exc,
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail=failure_detail) from exc

    logger.info(
        "[compute] %s completed in %.1fs (user=%s school=%s)",
        action, time.monotonic() - started, identity.user_id, identity.school_id,
    )
    return result


@router.post("/chat", response_model=ComputeChatResponse)
@limiter.limit(RATE_LIMIT_CHAT)
async def compute_chat(
    request: Request,
    payload: ComputeChatRequest,
    identity: VerifiedIdentity = Depends(get_current_identity),
) -> ComputeChatResponse:
    logger.info(
        "[compute] chat started user=%s school=%s history_len=%d chunks=%d",
        identity.user_id,
        identity.school_id,
        len(payload.message_history),
        len(payload.context_chunks),
    )
    result = await _run_compute(
        "chat", identity, compute_service.compute_chat(payload), "Chat processing failed."
    )
    return ComputeChatResponse(**result)


@router.post("/chat/stream")
@limiter.limit(RATE_LIMIT_CHAT)
async def compute_chat_stream(
    request: Request,
    payload: ComputeChatRequest,
    identity: VerifiedIdentity = Depends(get_current_identity),
) -> StreamingResponse:
    """
    SSE chat stream for Nest proxy.
    Events: token {text}, done {reply, sources}, error {detail}
    """
    logger.info(
        "[compute] chat/stream started user=%s school=%s history_len=%d chunks=%d",
        identity.user_id,
        identity.school_id,
        len(payload.message_history),
        len(payload.context_chunks),
    )
    started = time.monotonic()

    async def event_stream():
        parts: list[str] = []
        sources: list[str] = []
        try:
            async for token in compute_service.compute_chat_stream(payload, sources_out=sources):
                parts.append(token)
                yield f"data: {json.dumps({'type': 'token', 'text': token}, ensure_ascii=False)}\n\n"
            reply = "".join(parts).strip() or "I'm sorry, I couldn't process that request."
            yield f"data: {json.dumps({'type': 'done', 'reply': reply, 'sources': sources}, ensure_ascii=False)}\n\n"
            logger.info(
                "[compute] chat/stream completed in %.1fs (user=%s school=%s)",
                time.monotonic() - started,
                identity.user_id,
                identity.school_id,
            )
        except ValueError as exc:
            logger.warning(
                "[compute] chat/stream rejected after %.1fs (user=%s): %s",
                time.monotonic() - started,
                identity.user_id,
                exc,
            )
            yield f"data: {json.dumps({'type': 'error', 'detail': str(exc)}, ensure_ascii=False)}\n\n"
        except Exception as exc:
            logger.error(
                "[compute] chat/stream failed after %.1fs (user=%s): %s",
                time.monotonic() - started,
                identity.user_id,
                exc,
                exc_info=True,
            )
            yield f"data: {json.dumps({'type': 'error', 'detail': 'Chat processing failed.'}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/revision/generate", response_model=ComputeRevisionGenerateResponse)
@limiter.limit(RATE_LIMIT_GENERATE)
async def compute_revision_generate(
    request: Request,
    payload: ComputeRevisionGenerateRequest,
    identity: VerifiedIdentity = Depends(get_current_identity),
) -> ComputeRevisionGenerateResponse:
    logger.info(
        "[compute] revision/generate started user=%s subject=%s",
        identity.user_id,
        payload.subject,
    )
    result = await _run_compute(
        "revision/generate",
        identity,
        compute_service.compute_revision_generate(payload),
        "Exam generation failed.",
    )
    return ComputeRevisionGenerateResponse(**result)


@router.post("/revision/evaluate", response_model=ComputeRevisionEvaluateResponse)
@limiter.limit(RATE_LIMIT_GENERATE)
async def compute_revision_evaluate(
    request: Request,
    payload: ComputeRevisionEvaluateRequest,
    identity: VerifiedIdentity = Depends(get_current_identity),
) -> ComputeRevisionEvaluateResponse:
    logger.info(
        "[compute] revision/evaluate started user=%s subject=%s",
        identity.user_id,
        payload.subject,
    )
    result = await _run_compute(
        "revision/evaluate",
        identity,
        compute_service.compute_revision_evaluate(payload),
        "Exam evaluation failed.",
    )
    return ComputeRevisionEvaluateResponse(**result)


@router.post("/summarize", response_model=ComputeSummarizeResponse)
@limiter.limit(RATE_LIMIT_GENERATE)
async def compute_summarize(
    request: Request,
    payload: ComputeSummarizeRequest,
    identity: VerifiedIdentity = Depends(get_current_identity),
) -> ComputeSummarizeResponse:
    logger.info(
        "[compute] summarize started user=%s chars=%d", identity.user_id, len(payload.text)
    )
    result = await _run_compute(
        "summarize", identity, compute_service.compute_summarize(payload), "Summarization failed."
    )
    return ComputeSummarizeResponse(**result)


@router.post("/evaluate-session", response_model=ComputeEvaluateSessionResponse)
@limiter.limit(RATE_LIMIT_GENERATE)
async def compute_evaluate_session(
    request: Request,
    payload: ComputeEvaluateSessionRequest,
    identity: VerifiedIdentity = Depends(get_current_identity),
) -> ComputeEvaluateSessionResponse:
    logger.info(
        "[compute] evaluate-session started user=%s messages=%d",
        identity.user_id,
        len(payload.message_history),
    )
    result = await _run_compute(
        "evaluate-session",
        identity,
        compute_service.compute_evaluate_session(payload),
        "Session evaluation failed.",
    )
    return ComputeEvaluateSessionResponse(**result)
