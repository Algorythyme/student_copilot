# llm_setup.py — Modular provider registry. Switch LLM via .env only.
from config import (
    OPENAI_API_KEY, OPENAI_MODEL_NAME, REDIS_URL, logger, LLM_PROVIDER,
    GEMINI_API_KEY, PINECONE_API_KEY, PINECONE_INDEX_NAME, PINECONE_CLOUD, PINECONE_REGION,
    GEMINI_MODEL_NAME, GEMINI_EMBEDDING_MODEL, LLM_TEMPERATURE,
    DEEPSEEK_API_KEY, DEEPSEEK_MODEL_NAME, DEEPSEEK_BASE_URL,
)
import sys
import time

# For Redis client
try:
    import redis
except ImportError:
    logger.error("ERROR: 'redis' package not found. Please install it with `pip install redis`.")
    sys.exit(1)


# ─── PROVIDER REGISTRY ─────────────────────────────────────────────────────
# Each entry: { "chat_factory": callable() -> llm, "embeddings_factory": callable() -> embeddings | None }
# If embeddings_factory returns None, Gemini embeddings are used as universal fallback.
# Adding a new OpenAI-compatible provider = one new entry here + env vars in config.py.

def _gemini_chat():
    from langchain_google_genai import ChatGoogleGenerativeAI
    return ChatGoogleGenerativeAI(
        model=GEMINI_MODEL_NAME,
        google_api_key=GEMINI_API_KEY,
        temperature=LLM_TEMPERATURE,
    )

def _gemini_embeddings():
    from langchain_google_genai import GoogleGenerativeAIEmbeddings
    return GoogleGenerativeAIEmbeddings(
        model=GEMINI_EMBEDDING_MODEL,
        google_api_key=GEMINI_API_KEY,
    )

def _openai_chat():
    from langchain_openai import ChatOpenAI
    return ChatOpenAI(
        api_key=OPENAI_API_KEY,
        model=OPENAI_MODEL_NAME,
        temperature=LLM_TEMPERATURE,
        streaming=True,
    )

def _deepseek_chat():
    from langchain_openai import ChatOpenAI
    return ChatOpenAI(
        api_key=DEEPSEEK_API_KEY,
        base_url=DEEPSEEK_BASE_URL,
        model=DEEPSEEK_MODEL_NAME,
        temperature=LLM_TEMPERATURE,
        streaming=True,
    )

# All providers use Gemini embeddings (universal). embeddings_factory=None → Gemini fallback.
PROVIDER_REGISTRY = {
    "gemini": {
        "chat_factory": _gemini_chat,
        "embeddings_factory": _gemini_embeddings,
    },
    "openai": {
        "chat_factory": _openai_chat,
        "embeddings_factory": None,  # → Gemini embeddings
    },
    "deepseek": {
        "chat_factory": _deepseek_chat,
        "embeddings_factory": None,  # → Gemini embeddings
    },
}


# ─── INITIALIZATION ─────────────────────────────────────────────────────────
def _init_provider(provider_name: str):
    """Instantiate LLM + embeddings from the registry. Returns (llm, embeddings)."""
    entry = PROVIDER_REGISTRY.get(provider_name)
    if not entry:
        logger.error(f"[startup] Unknown LLM_PROVIDER: '{provider_name}'. Registered: {', '.join(PROVIDER_REGISTRY)}")
        sys.exit(1)

    chat = entry["chat_factory"]()
    logger.info(f"[startup] LLM initialized: provider={provider_name}")

    emb_factory = entry.get("embeddings_factory")
    if emb_factory:
        emb = emb_factory()
        logger.info(f"[startup] Embeddings initialized: provider={provider_name}")
    elif GEMINI_API_KEY:
        # Universal fallback — Gemini embeddings
        emb = _gemini_embeddings()
        logger.info(f"[startup] Embeddings initialized: Gemini fallback (provider={provider_name} has no embeddings)")
    else:
        emb = None
        logger.warning(f"[startup] No embeddings available for provider={provider_name} and GEMINI_API_KEY not set.")

    return chat, emb


llm = None
embeddings = None
try:
    llm, embeddings = _init_provider(LLM_PROVIDER)
except Exception as e:
    logger.error(f"[startup] Failed to initialize LLM/Embeddings ({LLM_PROVIDER}): {e}")
    sys.exit(1)

def _ensure_pinecone_index() -> None:
    if not PINECONE_API_KEY:
        return

    if not embeddings:
        logger.warning("[startup] Pinecone API key is set but embeddings are not initialized; skipping index provisioning.")
        return

    try:
        from pinecone import Pinecone, ServerlessSpec
    except Exception as e:
        logger.error(f"[startup] Pinecone client import failed: {e}")
        return

    try:
        test_embed = embeddings.embed_documents(["test"])
        dim = len(test_embed[0])
    except Exception as e:
        logger.warning(f"[startup] Dynamic dim detection failed. Fallback: {e}")
        dim = 768  # Gemini embedding-001 — universal embedding provider

    try:
        pc = Pinecone(api_key=PINECONE_API_KEY)

        existing = pc.list_indexes().names()
        if PINECONE_INDEX_NAME not in existing:
            logger.info(f"[startup] Creating Pinecone index {PINECONE_INDEX_NAME!r} (dim={dim}, cloud={PINECONE_CLOUD}, region={PINECONE_REGION})")
            pc.create_index(
                name=PINECONE_INDEX_NAME,
                dimension=dim,
                metric="cosine",
                spec=ServerlessSpec(cloud=PINECONE_CLOUD, region=PINECONE_REGION),
            )

        deadline = time.time() + 60
        while time.time() < deadline:
            try:
                desc = pc.describe_index(PINECONE_INDEX_NAME)
                status = getattr(desc, "status", None) or {}
                ready = status.get("ready") if isinstance(status, dict) else None
                if ready is True:
                    logger.info(f"[startup] Pinecone index {PINECONE_INDEX_NAME!r} is ready")
                    return
            except Exception:
                pass
            time.sleep(2)

        logger.warning(f"[startup] Pinecone index {PINECONE_INDEX_NAME!r} provisioning not confirmed ready within timeout; continuing.")
    except Exception as e:
        logger.error(f"[startup] Pinecone index provisioning failed: {e}")

# --- Redis Client Initialization ---
redis_client = None # Make redis_client globally accessible within this module
try:
    if REDIS_URL:
        # Added socket_timeout and socket_connect_timeout to prevent complete service hang on Redis outage
        redis_client = redis.Redis.from_url(REDIS_URL, socket_timeout=5, socket_connect_timeout=5)
        redis_client.ping() # Test connection
        from config import redact_for_logs
        logger.info(f"[startup] Redis client initialized successfully (url_hash={redact_for_logs(REDIS_URL)})")
    else:
        logger.error("ERROR: REDIS_URL is not set. Cannot initialize Redis client.") # Changed from print
        sys.exit(1)
except Exception as e:
    logger.error(f"[startup] Failed to initialize Redis client: {e}")
    sys.exit(1)

_ensure_pinecone_index()
