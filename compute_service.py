"""Stateless LLM orchestration for SMS compute API — no Redis/DB side effects."""

from __future__ import annotations

import json
from typing import Any, AsyncIterator, Dict, List, Optional

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.output_parsers import JsonOutputParser, StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from agent_core import run_agent_inline, run_agent_inline_stream
from ai_summarizer import evaluate_session_learning_method
from compute_models import (
    ComputeChatRequest,
    ComputeEvaluateSessionRequest,
    ComputeRevisionEvaluateRequest,
    ComputeRevisionGenerateRequest,
    ComputeSummarizeRequest,
    ContextChunk,
    FileSummaryItem,
    UserProfilePayload,
)
from config import logger
from llm_setup import llm


def _format_user_profile(profile: Optional[UserProfilePayload]) -> str:
    if not profile:
        return "no profile provided"
    data = profile.model_dump(exclude_none=True)
    if not data:
        return "no profile provided"
    return ", ".join(f"{k}={v}" for k, v in data.items())


def _format_file_summaries(summaries: List[FileSummaryItem]) -> str:
    if not summaries:
        return "no uploaded file summaries"
    return "\n".join(f"{item.filename}: {item.summary}" for item in summaries)


def _format_context_chunks(chunks: List[ContextChunk]) -> str:
    if not chunks:
        return ""
    parts = [f"[{chunk.source}]\n{chunk.content}" for chunk in chunks]
    return "Retrieved context from SMS vector search:\n" + "\n\n---\n\n".join(parts)


def _history_to_langchain(messages: List[Dict[str, str]]) -> list:
    converted = []
    for msg in messages:
        role = (msg.get("role") or "user").lower()
        content = msg.get("content") or ""
        if role == "assistant":
            converted.append(AIMessage(content=content))
        else:
            converted.append(HumanMessage(content=content))
    return converted


def _build_context_text(chunks: List[ContextChunk]) -> str:
    if not chunks:
        return ""
    if len(chunks) == 1:
        return chunks[0].content
    parent_texts = [f"[{c.source}]\n{c.content}" for c in chunks]
    return "\n\n---\n\n".join(parent_texts)


def _build_chat_input(payload: ComputeChatRequest) -> Dict[str, Any]:
    profile_text = _format_user_profile(payload.user_profile)
    summaries_text = _format_file_summaries(payload.file_summaries)
    context_text = _format_context_chunks(payload.context_chunks)

    combined_context = summaries_text
    if context_text:
        combined_context = f"{summaries_text}\n\n{context_text}" if summaries_text else context_text

    history = [item.model_dump() for item in payload.message_history]
    return {
        "input": payload.message,
        "user_profile": profile_text,
        "file_summaries": combined_context or "no uploaded file summaries",
        "chat_history": _history_to_langchain(history),
    }


async def compute_chat(payload: ComputeChatRequest) -> Dict[str, Any]:
    input_dict = _build_chat_input(payload)
    result = await run_agent_inline(input_dict)
    reply = result.get("output", "I'm sorry, I couldn't process that request.")
    return {"reply": reply, "learning_method_suggestion": None}


async def compute_chat_stream(payload: ComputeChatRequest) -> AsyncIterator[str]:
    """Yield plain-text reply tokens for SSE proxying by Nest."""
    input_dict = _build_chat_input(payload)
    async for token in run_agent_inline_stream(input_dict):
        if token:
            yield token


async def compute_revision_generate(payload: ComputeRevisionGenerateRequest) -> Dict[str, Any]:
    context = _build_context_text(payload.context_chunks)
    if not context.strip():
        raise ValueError(
            "No context_chunks provided. SMS must supply retrieved study material."
        )

    learning_method = (payload.user_profile.learning_method if payload.user_profile else None) or ""
    pedagogy = f"Student learning method: {learning_method}\n\n" if learning_method else ""

    prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            "You are an Elite Exam Designer. Generate a high-quality exam based ONLY on the provided context. "
            "Output EXACTLY a JSON object with this key: 'questions' (a list of objects). "
            "Each question object must have: 'id' (string), 'type' ('mcq' or 'theory'), 'text' (string), "
            "'options' (list of strings, for mcq only), 'correct_answer' (string, for mcq only).\n\n"
            f"{pedagogy}"
            f"Generate {payload.mcq_count} MCQs and {payload.theory_count} Theory questions.\n"
            f"Subject: {payload.subject}\n"
            f"Class: {payload.class_id or 'unspecified'}\n"
            f"Topics/Focus: {payload.topics or 'General'}\n\n"
            "Context:\n{context}",
        ),
        ("user", "Generate the exam now."),
    ])

    chain = prompt | llm | JsonOutputParser()
    exam = await chain.ainvoke({"context": context})
    questions = exam.get("questions") if isinstance(exam, dict) else exam
    if not isinstance(questions, list):
        raise ValueError("LLM did not return a valid questions list.")
    return {"questions": questions}


async def compute_revision_evaluate(payload: ComputeRevisionEvaluateRequest) -> Dict[str, Any]:
    context = _build_context_text(payload.context_chunks)
    if not context.strip():
        raise ValueError(
            "No context_chunks provided. SMS must supply ground-truth study material."
        )

    learning_method = (payload.user_profile.learning_method if payload.user_profile else None) or ""

    eval_prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            "You are a Sovereign Educator. Grade this exam submission against the ground truth context. "
            "Be strict but fair. For every failed question, provide a deep explanation using the student's LEARNING METHOD. "
            "Also, provide a 'summary' of their strengths and weaknesses.\n\n"
            f"STUDENT LEARNING METHOD: {learning_method or 'Not yet established'}\n\n"
            "GROUND TRUTH CONTEXT:\n{context}",
        ),
        ("user", "QUESTIONS: {questions}\n\nANSWERS: {answers}"),
    ])

    chain = eval_prompt | llm
    result = await chain.ainvoke({
        "context": context,
        "questions": json.dumps(payload.questions),
        "answers": json.dumps(payload.answers),
    })
    feedback_text = result.content if hasattr(result, "content") else str(result)
    return {"feedback": feedback_text, "status": "evaluated"}


async def compute_summarize(payload: ComputeSummarizeRequest) -> Dict[str, Any]:
    clipped = payload.text[:16000]
    label = payload.filename or "document"

    summary_prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            "You are a helpful assistant that summarizes uploaded documents for later use.",
        ),
        (
            "user",
            "Please produce a concise (max 120 words) summary of this document ({filename}). "
            "If the document is meant for a child, note age-appropriate vocabulary:\n\n{document_content}",
        ),
    ])
    chain = summary_prompt | llm | StrOutputParser()
    summary = await chain.ainvoke({"filename": label, "document_content": clipped})
    logger.info("[compute_service] Generated summary for %s", label)
    return {"summary": summary.strip()}


async def compute_evaluate_session(payload: ComputeEvaluateSessionRequest) -> Dict[str, Any]:
    profile_dict = payload.user_profile.model_dump(exclude_none=True) if payload.user_profile else {}
    history_lines = []
    for item in payload.message_history:
        role = "user" if item.role == "user" else "assistant"
        history_lines.append(f"{role}: {item.content}")
    chat_history_str = "\n".join(history_lines)

    current_method = payload.current_learning_method or profile_dict.get("learning_method") or ""
    new_method = await evaluate_session_learning_method(profile_dict, chat_history_str, current_method)

    status = "updated" if new_method and new_method != current_method else "unchanged"
    return {"learning_method": new_method or current_method, "status": status}
