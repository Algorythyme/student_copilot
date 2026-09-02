# config.py
from dotenv import load_dotenv
import os
import sys
import pathlib
import logging
import hashlib
import re
import warnings
from typing import Optional

# --- Suppress unfixable 3rd-party noise ---
warnings.filterwarnings("ignore", category=UserWarning, module="pydantic.*")
warnings.filterwarnings("ignore", category=FutureWarning, module="google.api_core.*")
warnings.filterwarnings("ignore", category=FutureWarning, module="langchain_google_genai.*")

# --- Logging Configuration ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("AI_Tutor_App")

# Load .env
project_dir = pathlib.Path.cwd()
logger.info(f"[startup] cwd={project_dir}")
load_dotenv(dotenv_path=project_dir / ".env")

# --- Read Environment Variables ---
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini").lower()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL_NAME = os.getenv("OPENAI_MODEL_NAME", "gpt-4o")

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_MODEL_NAME = os.getenv("DEEPSEEK_MODEL_NAME", "deepseek-v4-flash")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

# ─── MODEL CONFIGURATION ────────────────────────────────────────────────────
# Chat model names (overridable via .env)
GEMINI_MODEL_NAME = os.getenv("GEMINI_MODEL_NAME", "gemini-2.5-flash-lite")
# Embedding model names
GEMINI_EMBEDDING_MODEL = os.getenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001")
# LLM temperature (shared across providers)
try:
    LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.7"))
except (ValueError, TypeError):
    logger.warning("[startup] Invalid LLM_TEMPERATURE value. Defaulting to 0.7.")
    LLM_TEMPERATURE = 0.7

# Per-call LLM timeout so a hung provider request cannot hold a compute
# request open indefinitely (the Nest client itself times out at ~120s).
try:
    LLM_TIMEOUT_SECONDS = float(os.getenv("LLM_TIMEOUT_SECONDS", "90"))
except (ValueError, TypeError):
    logger.warning("[startup] Invalid LLM_TIMEOUT_SECONDS value. Defaulting to 90.")
    LLM_TIMEOUT_SECONDS = 90.0

PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "student-copilot")
PINECONE_CLOUD = os.getenv("PINECONE_CLOUD", "aws")
PINECONE_REGION = os.getenv("PINECONE_REGION", "us-east-1")

TAVILY_KEY = os.getenv("TAVILY_API_KEY")
REDIS_URL = os.getenv("REDIS_URL")

# ─── DATABASE CONFIGURATION ────────────────────────────────────────────────────
DATABASE_URL = os.getenv("DATABASE_URL")

# ─── DEPLOY MODE ───────────────────────────────────────────────────────────────
DEPLOY_MODE = os.getenv("DEPLOY_MODE", "full").lower()
_VALID_DEPLOY_MODES = {"compute", "web", "full"}
if DEPLOY_MODE not in _VALID_DEPLOY_MODES:
    logger.error(
        "ERROR: DEPLOY_MODE must be one of compute, web, full (got %r).",
        DEPLOY_MODE,
    )
    sys.exit(1)

IS_COMPUTE_MODE = DEPLOY_MODE == "compute"
IS_WEB_MODE = DEPLOY_MODE == "web"
IS_FULL_MODE = DEPLOY_MODE == "full"
LEGACY_ROUTES_ENABLED = DEPLOY_MODE in ("web", "full")
COMPUTE_ROUTES_ENABLED = DEPLOY_MODE in ("compute", "full")

def _env_bool(name: str, default: str) -> bool:
    return os.getenv(name, default).lower() == "true"

SERVE_WEB = _env_bool(
    "SERVE_WEB",
    "true" if DEPLOY_MODE in ("web", "full") else "false",
)
ENABLE_NEST_AUTH = _env_bool(
    "ENABLE_NEST_AUTH",
    "true" if DEPLOY_MODE in ("compute", "full") else "false",
)
ENABLE_SUPABASE_AUTH = _env_bool(
    "ENABLE_SUPABASE_AUTH",
    "true" if DEPLOY_MODE in ("web", "full") else "false",
)
ENABLE_STANDALONE_AUTH = _env_bool(
    "ENABLE_STANDALONE_AUTH",
    "true" if DEPLOY_MODE in ("web", "full") else "false",
)

REQUIRE_DATABASE = _env_bool(
    "REQUIRE_DATABASE",
    "true" if DEPLOY_MODE in ("web", "full") else "false",
)
REQUIRE_WEB_SEARCH = _env_bool(
    "REQUIRE_WEB_SEARCH",
    "true" if DEPLOY_MODE == "compute" else "false",
)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")

if ENABLE_SUPABASE_AUTH and not SUPABASE_JWT_SECRET and DEPLOY_MODE in ("web", "full"):
    logger.warning(
        "WARNING: ENABLE_SUPABASE_AUTH=true but SUPABASE_JWT_SECRET is not set."
    )

# ─── AUTH & SECURITY ─────────────────────────────────────────────────────────
AUTH_DISABLED = os.getenv("AUTH_DISABLED", "false").lower() == "true"
AUTH_DISABLED_USER_ID = os.getenv(
    "AUTH_DISABLED_USER_ID", "00000000-0000-0000-0000-000000000002"
)
AUTH_DISABLED_ROLE = os.getenv("AUTH_DISABLED_ROLE", "STUDENT")
SMS_SCHOOL_ID: Optional[str] = os.getenv("SMS_SCHOOL_ID")

JWT_SECRET_ENV = os.getenv("JWT_SECRET")
ENFORCE_STRONG_JWT_SECRET = os.getenv("ENFORCE_STRONG_JWT_SECRET", "true").lower() == "true"
DEFAULT_JWT_SECRET_MARKERS = {
    "change_me_in_production",
    "default",
    "sovereign_default_key",
}

if not JWT_SECRET_ENV:
    if AUTH_DISABLED:
        import secrets

        JWT_SECRET = secrets.token_urlsafe(32)
        logger.warning(
            "AUTH_DISABLED=true — JWT_SECRET not required for Nest JWT verify bypass."
        )
    elif IS_COMPUTE_MODE and ENABLE_NEST_AUTH and not ENABLE_STANDALONE_AUTH:
        import secrets

        JWT_SECRET = secrets.token_urlsafe(32)
        logger.info(
            "Compute mode: Nest JWT primary — auto-generated JWT_SECRET for HS256 fallback only."
        )
    elif ENFORCE_STRONG_JWT_SECRET:
        logger.error("ERROR: JWT_SECRET not set and ENFORCE_STRONG_JWT_SECRET=true. Refusing to start.")
        sys.exit(1)
    else:
        logger.warning("WARNING: JWT_SECRET not set. Using temporary random key. Sessions will be invalidated upon restart.")
        import secrets
        JWT_SECRET = secrets.token_urlsafe(32)
else:
    JWT_SECRET = JWT_SECRET_ENV

if ENFORCE_STRONG_JWT_SECRET and not AUTH_DISABLED:
    secret_lower = (JWT_SECRET_ENV or "").lower()
    if any(marker in secret_lower for marker in DEFAULT_JWT_SECRET_MARKERS):
        logger.error("ERROR: JWT_SECRET appears to be a placeholder/default value and ENFORCE_STRONG_JWT_SECRET=true. Refusing to start.")
        sys.exit(1)

JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = int(os.getenv("JWT_EXPIRY_HOURS", "24"))
JWT_PUBLIC_KEY = os.getenv("JWT_PUBLIC_KEY")
JWT_ISSUER = os.getenv("JWT_ISSUER", "Pedagic School Management")
JWT_AUDIENCE = os.getenv("JWT_AUDIENCE", "school-users")
NEST_JWT_PUBLIC_KEY_URL = os.getenv("NEST_JWT_PUBLIC_KEY_URL")
NEST_API_URL = os.getenv("NEST_API_URL")
AUTO_INGEST_SERVICE_TOKEN: Optional[str] = os.getenv("AUTO_INGEST_SERVICE_TOKEN")
PEDAGIC_PROVISION_SECRET: Optional[str] = os.getenv("PEDAGIC_PROVISION_SECRET")

CORS_ALLOW_ORIGINS_RAW = os.getenv("CORS_ALLOW_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
CORS_ALLOW_ORIGINS = [o.strip() for o in CORS_ALLOW_ORIGINS_RAW.split(",") if o.strip()]



# ΓöÇΓöÇΓöÇ OPERATIONAL LIMITS ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ
# Redis TTL for conversation data (seconds). Default: 30 days.
CONVERSATION_TTL_SECONDS = int(os.getenv("CONVERSATION_TTL_SECONDS", str(30 * 24 * 3600)))
# Learning method persists longer ΓÇö 365 days default.
LEARNING_METHOD_TTL_SECONDS = int(os.getenv("LEARNING_METHOD_TTL_SECONDS", str(365 * 24 * 3600)))
# Enrollment persists until manually removed (no TTL).
ENROLLMENT_TTL_SECONDS = int(os.getenv("ENROLLMENT_TTL_SECONDS", "0"))  # 0 = no expiry
# Teacher content is ground truth ΓÇö persists much longer (default: 365 days). 0 = no expiry.
TEACHER_CONTENT_TTL_SECONDS = int(os.getenv("TEACHER_CONTENT_TTL_SECONDS", str(365 * 24 * 3600)))

# Rate limits (requests per minute)
RATE_LIMIT_CHAT = os.getenv("RATE_LIMIT_CHAT", "20/minute")
RATE_LIMIT_GENERATE = os.getenv("RATE_LIMIT_GENERATE", "10/minute")
RATE_LIMIT_UPLOAD = os.getenv("RATE_LIMIT_UPLOAD", "5/minute")
RATE_LIMIT_AUTH = os.getenv("RATE_LIMIT_AUTH", "10/minute")

# Agent execution logging
AGENT_VERBOSE = os.getenv("AGENT_VERBOSE", "false").lower() == "true"

# ΓöÇΓöÇΓöÇ INPUT SANITIZATION ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ
# Strict pattern for IDs/keys: alphanumeric, underscores, hyphens, spaces, dots. Max 100 chars.
SAFE_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_\-. ]{1,100}$")
# Broad pattern for display names: blocks injection chars but allows Unicode.
_BLOCKED_NAME_CHARS = re.compile(r'[<>&;"\'\\]|\x00')

def validate_safe_string(value: str, field_name: str = "field") -> str:
    """Validates that a string is safe for use as Redis keys / Pinecone metadata."""
    if not value or not value.strip():
        raise ValueError(f"{field_name} cannot be empty.")
    cleaned = value.strip()
    if not SAFE_ID_PATTERN.match(cleaned):
        raise ValueError(
            f"{field_name} contains invalid characters. "
            f"Only letters, numbers, underscores, hyphens, spaces, and dots are allowed (max 100 chars)."
        )
    return cleaned

def validate_safe_name(value: str, field_name: str = "field") -> str:
    """Validates display names ΓÇö allows Unicode but blocks injection characters."""
    if not value or not value.strip():
        raise ValueError(f"{field_name} cannot be empty.")
    cleaned = value.strip()
    if len(cleaned) > 200:
        raise ValueError(f"{field_name} exceeds maximum length of 200 characters.")
    if _BLOCKED_NAME_CHARS.search(cleaned):
        raise ValueError(
            f"{field_name} contains disallowed characters "
            f"(angled brackets, quotes, semicolons, backslashes)."
        )
    return cleaned


def redact_for_logs(value: str) -> str:
    if value is None:
        return "-"
    s = str(value)
    digest = hashlib.sha256(s.encode("utf-8", errors="ignore")).hexdigest()
    return digest[:10]


# --- Initial Validation (registry-driven) ---
# Map each supported provider to its required API key variable name + value.
# Adding a new provider = one entry here + env vars above. No branching.
SUPPORTED_PROVIDERS = {
    "gemini":   ("GEMINI_API_KEY",   GEMINI_API_KEY),
    "openai":   ("OPENAI_API_KEY",   OPENAI_API_KEY),
    "deepseek": ("DEEPSEEK_API_KEY", DEEPSEEK_API_KEY),
}

if LLM_PROVIDER not in SUPPORTED_PROVIDERS:
    logger.error(f"ERROR: Unsupported LLM_PROVIDER: '{LLM_PROVIDER}'. Supported: {', '.join(SUPPORTED_PROVIDERS)}")
    sys.exit(1)

_required_key_name, _required_key_val = SUPPORTED_PROVIDERS[LLM_PROVIDER]
if not _required_key_val:
    logger.error(f"ERROR: {_required_key_name} is required when LLM_PROVIDER={LLM_PROVIDER}.")
    sys.exit(1)

# Gemini API key is also required as universal embedding fallback
if LLM_PROVIDER != "gemini" and not GEMINI_API_KEY:
    logger.warning("WARNING: GEMINI_API_KEY not set. Gemini embedding fallback will be unavailable — Pinecone vectorization may fail.")

if not TAVILY_KEY:
    if REQUIRE_WEB_SEARCH:
        logger.error(
            "ERROR: TAVILY_API_KEY is required when REQUIRE_WEB_SEARCH=true. "
            "Refusing to start without the advertised web-search capability."
        )
        sys.exit(1)
    logger.warning("WARNING: TAVILY_API_KEY not set. Tavily web search is disabled.")

if not PINECONE_API_KEY:
    if IS_COMPUTE_MODE:
        logger.info("[startup] PINECONE_API_KEY not set — expected in compute mode (SMS owns vectors).")
    else:
        logger.warning("WARNING: PINECONE_API_KEY not set. File uploads will not be vectorized.")

if not REDIS_URL:
    if IS_COMPUTE_MODE:
        logger.warning(
            "WARNING: REDIS_URL not set — using in-memory rate limiting in compute mode."
        )
    else:
        logger.error("ERROR: REDIS_URL is required for session/memory management.")
        sys.exit(1)

if not DATABASE_URL:
    if REQUIRE_DATABASE:
        logger.error("ERROR: DATABASE_URL is required (Postgres student_copilot schema).")
        sys.exit(1)
    logger.info("[startup] DATABASE_URL not set — OK for compute-only deploy.")

if DATABASE_URL and ".railway.internal" in DATABASE_URL:
    logger.warning(
        "DATABASE_URL uses *.railway.internal — use public *.proxy.rlwy.net when "
        "student_copilot is in a separate Railway project from Postgres."
    )

if AUTH_DISABLED:
    logger.warning(
        "AUTH_DISABLED=true — JWT signatures are not verified. "
        "Real SMS user id/school are read from Bearer token when sent."
    )

if not JWT_SECRET_ENV and not ENFORCE_STRONG_JWT_SECRET and not AUTH_DISABLED:
    logger.warning("WARNING: Using dynamically generated random JWT_SECRET. Set JWT_SECRET in .env for production.")

logger.info(
    "[startup] Config loaded. LLM=%s, DEPLOY_MODE=%s, ConvTTL=%ss",
    LLM_PROVIDER,
    DEPLOY_MODE,
    CONVERSATION_TTL_SECONDS,
)
