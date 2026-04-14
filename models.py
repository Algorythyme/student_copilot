# models.py
from pydantic import BaseModel, field_validator
from typing import Optional, Dict, Any, List

# --- Production limits ---
MAX_MESSAGE_LENGTH = 4000  # ~4k chars Γëê ~1k tokens. Prevents LLM overflow and abuse.


class ChatRequest(BaseModel):
    conversation_id: str
    message: str
    user_profile: Optional[Dict[str, Any]] = None

    @field_validator("conversation_id", mode="before")
    @classmethod
    def sanitize_conversation_id(cls, v):
        from config import validate_safe_string
        return validate_safe_string(v, "conversation_id")

    @field_validator("message", mode="before")
    @classmethod
    def validate_message_length(cls, v):
        if not v or not v.strip():
            raise ValueError("Message cannot be empty.")
        if len(v) > MAX_MESSAGE_LENGTH:
            raise ValueError(f"Message exceeds maximum length of {MAX_MESSAGE_LENGTH} characters.")
        return v.strip()


# For listing conversations with titles
class ConversationItem(BaseModel):
    id: str
    title: str


# For the /conversations/new endpoint request body
class NewConversationRequest(BaseModel):
    initial_message: Optional[str] = None
    suggested_title: Optional[str] = None
