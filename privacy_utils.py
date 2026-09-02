"""Dependency-free privacy helpers for student-facing tutor responses."""

import json
import re
from typing import Any, Awaitable, Callable, Dict, List, Optional

_URL_RE = re.compile(r"https?://[^\s\"'<>\\)\]}]+|www\.\S+", re.IGNORECASE)
_MARKDOWN_LINK_RE = re.compile(r"\[([^\]]+)\]\(https?://[^)]+\)", re.IGNORECASE)
_SENSITIVE_QUERY_RE = re.compile(
    r"https?://\S+|\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b|"
    r"\b[0-9a-f]{8}-[0-9a-f-]{27,}\b|\+?\d[\d\s().-]{7,}\d",
    re.IGNORECASE,
)
_PRIVATE_QUERY_TERMS_RE = re.compile(
    r"\b(my|our)\s+(name|school|teacher|class|grade|score|address|phone|email|"
    r"assignment|report|record)\b",
    re.IGNORECASE,
)
_PRIVATE_CONTEXT_REFERENCE_RE = re.compile(
    r"\b(this|that|these|those|attached|uploaded|private|file|document|note|"
    r"handout|assignment|report|record|score|chapter|page)\b",
    re.IGNORECASE,
)
_MODEL_SOURCE_LABEL_RE = re.compile(
    r"\b(?:study material|uploaded material|web result)\s+\d+\b",
    re.IGNORECASE,
)
_BLOCKED_PUBLIC_KEYS = {
    "source",
    "sources",
    "sourceurl",
    "sourceurls",
    "sourcetitle",
    "sourcetitles",
    "contextsources",
    "url",
    "urls",
    "citation",
    "citations",
    "reference",
    "references",
    "provenance",
}


class WebSearchRequiredError(RuntimeError):
    """Raised when a required general-knowledge search cannot be completed."""


def sanitize_public_reply(value: Any) -> str:
    """Remove links, raw URLs and trailing source lists before returning text."""
    text = _MARKDOWN_LINK_RE.sub(r"\1", str(value or ""))
    text = _URL_RE.sub("", text)
    text = _MODEL_SOURCE_LABEL_RE.sub("the provided information", text)
    lines = []
    dropping_sources = False
    for line in text.splitlines():
        if re.match(
            r"^\s*(sources?|references?|further reading)\s*(?::.*)?$",
            line,
            re.I,
        ):
            dropping_sources = True
            continue
        if dropping_sources and re.match(r"^\s*([-*]|\d+\.)\s+", line):
            continue
        dropping_sources = False
        lines.append(line.rstrip())
    return "\n".join(lines).strip()


def sanitize_search_query(value: str) -> str:
    segments = [
        part.strip()
        for part in re.split(r"(?<=[.!?])\s+", value or "")
        if part.strip()
    ]
    query = next(
        (part for part in segments if "?" in part),
        segments[0] if segments else "",
    )
    query = _SENSITIVE_QUERY_RE.sub(" ", query)
    query = re.sub(r"[^\w\s?'’-]", " ", query, flags=re.UNICODE)
    query = re.sub(r"\s+", " ", query).strip()
    return " ".join(query.split()[:16])[:180]


def requires_deterministic_search(input_dict: dict, required: bool) -> bool:
    if not required:
        return False
    text = str(input_dict.get("input") or "").strip().lower()
    if not text or re.fullmatch(
        r"(hi|hello|hey|thanks|thank you|good (morning|afternoon|evening))[!. ]*",
        text,
    ):
        return False
    if _PRIVATE_QUERY_TERMS_RE.search(text):
        return False
    if input_dict.get("has_private_context") and _PRIVATE_CONTEXT_REFERENCE_RE.search(
        text
    ):
        return False
    return True


def sanitize_web_results(resp: Any) -> List[dict]:
    """Keep result text only; never pass URLs or source labels to the LLM."""
    raw_results = resp.get("results") if isinstance(resp, dict) else None
    safe_results = []
    for index, item in enumerate(raw_results or []):
        if not isinstance(item, dict):
            continue
        content = sanitize_public_reply(
            str(item.get("content") or item.get("snippet") or "")
        )
        content = re.sub(r"\s+", " ", content).strip()
        if content:
            safe_results.append(
                {"label": f"Web result {index + 1}", "content": content[:2000]}
            )
    return safe_results


async def run_required_web_search(
    input_dict: dict,
    required: bool,
    search: Optional[Callable[[str], Awaitable[Any]]],
) -> tuple[str, bool]:
    if not requires_deterministic_search(input_dict, required):
        return "", False
    if search is None:
        raise WebSearchRequiredError(
            "Required web search is unavailable. Please try again later."
        )
    query = sanitize_search_query(str(input_dict.get("input") or ""))
    if len(query.split()) < 2:
        raise WebSearchRequiredError(
            "This question cannot be searched safely. Remove personal details and try again."
        )
    try:
        results = await search(query)
    except Exception as exc:
        raise WebSearchRequiredError(
            "Required web search failed. Please try again later."
        ) from exc
    if not results:
        raise WebSearchRequiredError(
            "Required web search returned no usable results. Please try again later."
        )
    return json.dumps(results, ensure_ascii=False), True


def public_chat_result(result: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "reply": sanitize_public_reply(
            result.get("output", "I'm sorry, I couldn't process that request.")
        ),
        "learning_method_suggestion": None,
        "search_used": bool(result.get("search_used")),
        "search_failed": bool(result.get("search_failed")),
    }


def sanitize_public_data(value: Any) -> Any:
    """Recursively remove provenance keys and links from public compute data."""
    if isinstance(value, str):
        return sanitize_public_reply(value)
    if isinstance(value, list):
        return [sanitize_public_data(item) for item in value]
    if isinstance(value, dict):
        return {
            key: sanitize_public_data(item)
            for key, item in value.items()
            if re.sub(r"[-_\s]", "", str(key).lower())
            not in _BLOCKED_PUBLIC_KEYS
        }
    return value
