"""Pydantic schemas for stateless /api/v1/compute/* endpoints."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator

from models import MAX_MESSAGE_LENGTH


class UserProfilePayload(BaseModel):
    full_name: Optional[str] = None
    age: Optional[int] = None
    country: Optional[str] = None
    class_id: Optional[str] = None
    subjects: Optional[str] = None
    learning_method: Optional[str] = None


class MessageHistoryItem(BaseModel):
    role: str
    content: str


class FileSummaryItem(BaseModel):
    filename: str
    summary: str


class ContextChunk(BaseModel):
    source: str
    content: str


class ComputeChatRequest(BaseModel):
    message: str
    user_profile: Optional[UserProfilePayload] = None
    message_history: List[MessageHistoryItem] = Field(default_factory=list)
    file_summaries: List[FileSummaryItem] = Field(default_factory=list)
    context_chunks: List[ContextChunk] = Field(default_factory=list)

    @field_validator("message", mode="before")
    @classmethod
    def validate_message(cls, v):
        if not v or not str(v).strip():
            raise ValueError("Message cannot be empty.")
        text = str(v).strip()
        if len(text) > MAX_MESSAGE_LENGTH:
            raise ValueError(f"Message exceeds maximum length of {MAX_MESSAGE_LENGTH} characters.")
        return text


class ComputeChatResponse(BaseModel):
    reply: str
    learning_method_suggestion: Optional[str] = None
    search_used: bool = False
    search_failed: bool = False


class ComputeRevisionGenerateRequest(BaseModel):
    subject: str
    class_id: Optional[str] = None
    topics: Optional[str] = None
    mcq_count: int = 5
    theory_count: int = 2
    context_chunks: List[ContextChunk] = Field(default_factory=list)
    user_profile: Optional[UserProfilePayload] = None


class ComputeRevisionGenerateResponse(BaseModel):
    questions: List[Dict[str, Any]]


class ComputePracticeGenerateRequest(BaseModel):
    subject: str
    class_id: Optional[str] = None
    topics: Optional[str] = None
    week: Optional[int] = None
    term: Optional[str] = None
    country: Optional[str] = None
    difficulty: float = Field(..., ge=0.1, le=1.0)
    mcq_count: int = 20
    theory_count: int = 0
    context_chunks: List[ContextChunk] = Field(..., min_length=1)
    user_profile: Optional[UserProfilePayload] = None
    exclude_stems: List[str] = Field(default_factory=list)

    @field_validator("term", mode="before")
    @classmethod
    def coerce_term(cls, v):
        if v is None:
            return None
        text = str(v).strip()
        return text or None

    @field_validator("exclude_stems", mode="before")
    @classmethod
    def coerce_exclude_stems(cls, v):
        if not v:
            return []
        if not isinstance(v, list):
            raise ValueError("exclude_stems must be a list of strings.")
        return [str(item).strip() for item in v if str(item).strip()]

    @field_validator("context_chunks")
    @classmethod
    def require_curriculum_content(cls, chunks):
        if not any((chunk.content or "").strip() for chunk in chunks):
            raise ValueError("context_chunks must include curriculum content.")
        return chunks


class ComputePracticeGenerateResponse(BaseModel):
    questions: List[Dict[str, Any]]


# Same idea as curriculum-builder AdaptiveQuestionService.COUNTRY_EXAM_BODY_MAP.
COUNTRY_EXAM_BODY_MAP = {
    "nigeria": ["WAEC", "NECO"],
    "ghana": ["WAEC"],
    "sierra leone": ["WAEC"],
    "liberia": ["WAEC"],
    "the gambia": ["WAEC"],
    "kenya": ["KCSE"],
    "south africa": ["NSC"],
    "tanzania": ["NECTA"],
    "uganda": ["UNEB"],
}

_EXCLUDE_STEM_CAP = 30
_EXCLUDE_STEM_CHARS = 140


def _escape_tmpl(value: Any) -> str:
    """Keep interpolated text from becoming extra ChatPromptTemplate variables."""
    return str(value).replace("{", "{{").replace("}", "}}")


def exam_body_hint(country: Optional[str]) -> str:
    """One-line exam-body style hint. Unknown country stays generic (no invented board)."""
    if not country or not str(country).strip():
        return "Match the national secondary-school exam style for the student's country if known."
    label = str(country).strip()
    bodies = COUNTRY_EXAM_BODY_MAP.get(label.lower())
    if not bodies:
        return f"Match the national secondary-school exam style used in {label}."
    return f"Write items in {'/'.join(bodies)} style."


def _exclude_stems_block(stems: List[str]) -> str:
    compact: List[str] = []
    for raw in stems:
        stem = raw.strip()
        if not stem:
            continue
        if len(stem) > _EXCLUDE_STEM_CHARS:
            stem = stem[:_EXCLUDE_STEM_CHARS].rstrip() + "…"
        compact.append(_escape_tmpl(stem))
        if len(compact) >= _EXCLUDE_STEM_CAP:
            break
    if not compact:
        return ""
    lines = "\n".join(f"- {stem}" for stem in compact)
    return f"Do not reuse or paraphrase these stems:\n{lines}\n\n"


def practice_system_prompt(payload: ComputePracticeGenerateRequest) -> str:
    """System prompt including {context}. Never interpolates user_profile.full_name."""
    learning_method = (payload.user_profile.learning_method if payload.user_profile else None) or ""
    pedagogy = (
        f"Student learning method: {_escape_tmpl(learning_method)}\n\n" if learning_method else ""
    )
    term = _escape_tmpl(payload.term) if payload.term is not None else "unspecified"
    week = payload.week if payload.week is not None else "unspecified"
    return (
        "You are an Elite Exam Designer. Generate high-quality MCQs based ONLY on the provided context. "
        "Output EXACTLY a JSON object with this key: 'questions' (a list of objects). "
        "Each question object must have: 'id' (string), 'type' ('mcq'), 'text' (string), "
        "'options' (list of four short strings), 'correct_answer' (string). "
        "MCQ-only. No theory. No explanations.\n\n"
        "Difficulty scale 0.1 to 1.0: 0.1 recall, 0.3 understand, 0.5 apply, "
        "0.7 analyze, 0.9 evaluate, 1.0 exam-hard.\n"
        f"Target difficulty: {payload.difficulty}\n"
        f"Exam body: {_escape_tmpl(exam_body_hint(payload.country))}\n\n"
        f"{pedagogy}"
        f"{_exclude_stems_block(payload.exclude_stems)}"
        f"Generate {payload.mcq_count} MCQs.\n"
        f"Subject: {_escape_tmpl(payload.subject)}\n"
        f"Class: {_escape_tmpl(payload.class_id or 'unspecified')}\n"
        f"Topics/Focus: {_escape_tmpl(payload.topics or 'General')}\n"
        f"Term: {term}\n"
        f"Week: {week}\n"
        f"Country: {_escape_tmpl(payload.country or 'unspecified')}\n\n"
        "Context:\n{context}"
    )


class ComputeRevisionEvaluateRequest(BaseModel):
    subject: str
    class_id: Optional[str] = None
    questions: List[Dict[str, Any]]
    answers: Dict[str, str]
    context_chunks: List[ContextChunk] = Field(default_factory=list)
    user_profile: Optional[UserProfilePayload] = None


class ComputeRevisionEvaluateResponse(BaseModel):
    feedback: str
    status: str = "evaluated"


class ComputeSummarizeRequest(BaseModel):
    text: str
    filename: Optional[str] = None

    @field_validator("text", mode="before")
    @classmethod
    def validate_text(cls, v):
        if not v or not str(v).strip():
            raise ValueError("text cannot be empty.")
        return str(v)


class ComputeSummarizeResponse(BaseModel):
    summary: str


class ComputeEvaluateSessionRequest(BaseModel):
    user_profile: Optional[UserProfilePayload] = None
    message_history: List[MessageHistoryItem] = Field(default_factory=list)
    current_learning_method: Optional[str] = None


class ComputeEvaluateSessionResponse(BaseModel):
    learning_method: str
    status: str = "evaluated"
