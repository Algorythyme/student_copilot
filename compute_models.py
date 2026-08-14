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
    # Web URLs used by the agent (Nest merges them into the done-event sources).
    sources: List[str] = Field(default_factory=list)


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
