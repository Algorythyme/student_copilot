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
    difficulty: float = Field(..., ge=0.0, le=1.0)
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


def cognitive_rubric_for_difficulty(difficulty: float) -> tuple[str, str]:
    """Returns (tier_label, rubric_instructions) for calibrated Bloom's difficulty tiers."""
    d = round(difficulty, 1)
    if d <= 0.2:
        return (
            "Tier 1: Foundational Recall & Recognition",
            "COGNITIVE RUBRIC - TIER 1 (Recall & Direct Recognition):\n"
            "- Stems: Direct, concise, unambiguous prompts (e.g. 'What is...', 'Which term denotes...', 'Identify the formula for...'). Test verbatim definitions, basic terminology, units, symbols, or core facts explicitly stated in context.\n"
            "- Options: 4 clearly distinct concepts from the same subject. No confusing grammatical tricks, no double negatives, no 'all of the above'.\n"
            "- Distractors: Simple, plausible alternative terms without calculation traps or subtle edge cases.\n"
            "- Target Cognitive Demand: Single-step memory retrieval.",
        )
    elif d <= 0.4:
        return (
            "Tier 2: Conceptual Understanding & Classification",
            "COGNITIVE RUBRIC - TIER 2 (Understanding & Classification):\n"
            "- Stems: Require students to explain principles, categorize examples vs non-examples, identify reasons, or describe a mechanism (e.g. 'Which of the following best exemplifies...', 'Why does process X occur under condition Y?').\n"
            "- Options: 4 homogeneous options of approximately equal length and sentence structure.\n"
            "- Distractors: Describe related but distinct concepts or common surface-level confusions.\n"
            "- Target Cognitive Demand: Concept comprehension beyond verbatim memorization.",
        )
    elif d <= 0.6:
        return (
            "Tier 3: Applied Problem Solving",
            "COGNITIVE RUBRIC - TIER 3 (Application & Calculation):\n"
            "- Stems: Realistic vignettes, short practical scenarios, or single-step mathematical/scientific calculations (e.g. 'A student observes that...', 'Calculate the value of X when Y=... and Z=...').\n"
            "- Options: Concrete numerical values with proper units or specific situational decisions.\n"
            "- Distractors: MUST include authentic calculation or execution traps (e.g. sign errors, inverted fractions, off-by-one, formula misapplications). Every distractor must look mathematically or logically plausible.\n"
            "- Target Cognitive Demand: Independent execution of a rule, formula, or procedure in a novel scenario.",
        )
    elif d <= 0.8:
        return (
            "Tier 4: Analysis & Multi-Step Deduction",
            "COGNITIVE RUBRIC - TIER 4 (Analysis & Multi-Step Deduction):\n"
            "- Stems: Multi-part conditions, cause-and-effect chains, comparative analysis between two cases, experimental data/table interpretation, or diagnosing experimental errors (e.g. 'If factor A increases while B remains constant, what is the net impact on C?').\n"
            "- Options: Nuanced statements explaining reasons or outcomes.\n"
            "- Distractors: Formulated based on widespread student misconceptions. Each distractor must represent a plausible partial deduction or false assumption.\n"
            "- Target Cognitive Demand: Deconstructing a problem, evaluating relationships, and eliminating plausible falsehoods.",
        )
    else:
        return (
            "Tier 5: Exam Distinction & Synthesis",
            "COGNITIVE RUBRIC - TIER 5 (Evaluation & Exam Distinction):\n"
            "- Stems: Model after distinction-grade challenge questions in regional national examinations (e.g. WAEC Section A advanced tier, KCSE Paper 1 higher difficulty). Feature multi-concept synthesis, conflicting variables, counter-intuitive phenomena, or evaluating competing hypotheses.\n"
            "- Options: Thoroughly vetted, precise academic language.\n"
            "- Distractors: Sophisticated options that would be true under standard conditions, but fail specifically under the edge case or constraints specified in this stem.\n"
            "- Target Cognitive Demand: Synthesis of multiple principles and deep critical evaluation under rigorous exam conditions.",
        )


def practice_system_prompt(payload: ComputePracticeGenerateRequest) -> str:
    """System prompt including {context}. Never interpolates user_profile.full_name."""
    learning_method = (payload.user_profile.learning_method if payload.user_profile else None) or ""
    pedagogy = (
        f"Student learning method: {_escape_tmpl(learning_method)}\n\n" if learning_method else ""
    )
    term = _escape_tmpl(payload.term) if payload.term is not None else "unspecified"
    week = payload.week if payload.week is not None else "unspecified"
    tier_label, rubric_text = cognitive_rubric_for_difficulty(payload.difficulty)
    difficulty_pct = int(round(payload.difficulty * 100))

    return (
        "You are an Elite Exam Designer and Psychometrician. Generate high-quality MCQs strictly aligned to the provided curriculum context.\n\n"
        "OUTPUT REQUIREMENT:\n"
        "Output EXACTLY a JSON object with this key: 'questions' (a list of question objects).\n"
        "Each question object MUST have:\n"
        "  - 'id': string (unique identifier e.g. 'q1')\n"
        "  - 'type': 'mcq'\n"
        "  - 'text': string (the question stem)\n"
        "  - 'options': list of exactly 4 strings\n"
        "  - 'correct_answer': string (MUST exactly match one of the 4 strings in options)\n"
        f"  - 'cognitive_tier': '{_escape_tmpl(tier_label)}'\n"
        "  - 'explanation': string (1-2 clear sentences explaining why correct_answer is right and clarifying the common misconception in the distractors)\n\n"
        f"TARGET DIFFICULTY LEVEL: {difficulty_pct}% ({tier_label})\n\n"
        f"{rubric_text}\n\n"
        f"Exam body style: {_escape_tmpl(exam_body_hint(payload.country))}\n\n"
        f"{pedagogy}"
        f"{_exclude_stems_block(payload.exclude_stems)}"
        f"Generate {payload.mcq_count} MCQs.\n"
        f"Subject: {_escape_tmpl(payload.subject)}\n"
        f"Class: {_escape_tmpl(payload.class_id or 'unspecified')}\n"
        f"Topics/Focus: {_escape_tmpl(payload.topics or 'General')}\n"
        f"Term: {term}\n"
        f"Week: {week}\n"
        f"Country: {_escape_tmpl(payload.country or 'unspecified')}\n\n"
        "CONTEXT USAGE GUIDELINES:\n"
        "1. If a 'Scheme week' chunk is present in the context, treat its stated learning objectives and activities as the primary syllabus mandate. Every question must directly test one of those objectives.\n"
        "2. Ground all answers and technical terms in the provided context.\n\n"
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
