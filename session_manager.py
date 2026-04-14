# session_manager.py
from typing import Dict, Any, Optional, List
from langchain_redis import RedisChatMessageHistory
from llm_setup import redis_client  # Import the pre-initialized redis_client
from config import logger, CONVERSATION_TTL_SECONDS, LEARNING_METHOD_TTL_SECONDS
import json
import uuid

# Global SESSIONS dictionary to cache history objects, profiles, and summaries
# Structure: {
#   user_id: {
#     conversation_id: {
#       "chat_history_redis": RedisChatMessageHistory,
#       "profile": dict,
#       "summaries": list,
#       "title": str
#     },
#   },
# }
SESSIONS: Dict[str, Dict[str, Dict[str, Any]]] = {}
MAX_CACHED_SESSIONS = 500  # Hard cap on total cached conversations (across all users)

def _enforce_session_bounds():
    """Evicts oldest cached sessions to prevent unbounded memory growth.
    Safe because Redis is the source of truth ΓÇö evicted sessions re-hydrate on next access."""
    total = sum(len(convs) for convs in SESSIONS.values())
    if total <= MAX_CACHED_SESSIONS:
        return
    target = int(MAX_CACHED_SESSIONS * 0.8)
    while total > target and SESSIONS:
        largest_user = max(SESSIONS, key=lambda uid: len(SESSIONS[uid]))
        user_convs = SESSIONS[largest_user]
        if not user_convs:
            del SESSIONS[largest_user]
            continue
        oldest_conv = next(iter(user_convs))
        del user_convs[oldest_conv]
        total -= 1
        if not user_convs:
            del SESSIONS[largest_user]
    logger.info(f"[session_manager] Cache eviction: {total} conversations retained.")


# --- Redis Key Helpers ---
def _get_user_conversations_key(user_id: str) -> str:
    return f"user:{user_id}:conversations"

def _get_profile_key(conversation_id: str) -> str:
    return f"conversation:{conversation_id}:profile"

def _get_summaries_key(conversation_id: str) -> str:
    return f"conversation:{conversation_id}:summaries"

def _get_title_key(conversation_id: str) -> str:
    return f"conversation:{conversation_id}:title"


# --- Redis Data Load/Save Functions ---
def load_conversation_data_from_redis(conversation_id: str) -> Dict[str, Any]:
    """Loads user profile and summaries for a specific conversation from Redis."""
    if redis_client is None:
        logger.error("[session_manager] Redis client not initialized when attempting to load conversation data.")
        return {"profile": {}, "summaries": [], "title": "Untitled Chat"}

    profile = {}
    summaries = []
    title = "Untitled Chat"

    try:
        profile_json = redis_client.get(_get_profile_key(conversation_id))
        if profile_json:
            profile = json.loads(profile_json)
            logger.info(f"[session_manager] Loaded profile for conversation {conversation_id} from Redis.")

        summaries_json = redis_client.get(_get_summaries_key(conversation_id))
        if summaries_json:
            summaries = json.loads(summaries_json)
            logger.info(f"[session_manager] Loaded summaries for conversation {conversation_id} from Redis.")

        title_bytes = redis_client.get(_get_title_key(conversation_id))
        if title_bytes:
            title = title_bytes.decode('utf-8')
            logger.info(f"[session_manager] Loaded title for conversation {conversation_id} from Redis.")

    except Exception as e:
        logger.error(f"[session_manager] Error loading conversation data for {conversation_id} from Redis: {e}")
        profile = {}
        summaries = []

    return {"profile": profile, "summaries": summaries, "title": title}


def save_conversation_data_to_redis(conversation_id: str, profile: Dict[str, Any], summaries: List[Dict[str, Any]], title: str):
    """Saves user profile and summaries for a specific conversation to Redis."""
    if redis_client is None:
        logger.error("[session_manager] Redis client not initialized when attempting to save conversation data.")
        return

    ttl = CONVERSATION_TTL_SECONDS if CONVERSATION_TTL_SECONDS > 0 else None
    try:
        profile_key = _get_profile_key(conversation_id)
        redis_client.set(profile_key, json.dumps(profile), ex=ttl)

        summaries_key = _get_summaries_key(conversation_id)
        redis_client.set(summaries_key, json.dumps(summaries), ex=ttl)

        title_key = _get_title_key(conversation_id)
        redis_client.set(title_key, title, ex=ttl)

        logger.info(f"[session_manager] Saved conversation data for {conversation_id} (TTL={ttl}s).")
    except Exception as e:
        logger.error(f"[session_manager] Error saving conversation data for {conversation_id} to Redis: {e}")


# --- User Global Data ---
def _get_user_learning_method_key(user_id: str) -> str:
    return f"user:{user_id}:learning_method"

def load_user_learning_method(user_id: str) -> Optional[str]:
    """Loads a user's globally shared learning method from Redis."""
    if redis_client is None:
        return None
    try:
        val = redis_client.get(_get_user_learning_method_key(user_id))
        return val.decode('utf-8') if val else None
    except Exception as e:
        logger.error(f"[session_manager] Error loading global learning method for {user_id}: {e}")
        return None

def save_user_learning_method(user_id: str, method: str):
    """Saves a user's globally shared learning method to Redis."""
    if redis_client is None:
        return
    lm_ttl = LEARNING_METHOD_TTL_SECONDS if LEARNING_METHOD_TTL_SECONDS > 0 else None
    try:
        if method:
            redis_client.set(_get_user_learning_method_key(user_id), method, ex=lm_ttl)
            logger.info(f"[session_manager] Saved global learning method for {user_id} (TTL={lm_ttl}s).")
    except Exception as e:
        logger.error(f"[session_manager] Error saving global learning method for {user_id}: {e}")


# --- Conversation Management ---
def create_new_conversation_id(user_id: str, initial_title: str = "Untitled Chat") -> str:
    """Generates a new conversation ID and associates it with the user."""
    if redis_client is None:
        logger.error("[session_manager] Redis client not initialized. Cannot create new conversation.")
        raise RuntimeError("Redis client is not initialized.")

    conversation_id = str(uuid.uuid4())
    ttl = CONVERSATION_TTL_SECONDS if CONVERSATION_TTL_SECONDS > 0 else None
    try:
        redis_client.sadd(_get_user_conversations_key(user_id), conversation_id)
        redis_client.set(_get_title_key(conversation_id), initial_title, ex=ttl)
        logger.info(f"[session_manager] Created conversation {conversation_id} for {user_id} (TTL={ttl}s).")
        return conversation_id
    except Exception as e:
        logger.error(f"[session_manager] Error creating conversation {conversation_id} for {user_id}: {e}")
        raise RuntimeError(f"Failed to create new conversation for user {user_id}: {e}")


def get_user_conversation_ids(user_id: str) -> List[Dict[str, str]]:
    """Retrieves all conversation IDs for a given user, pruning expired ghosts."""
    if redis_client is None:
        logger.error("[session_manager] Redis client not initialized. Cannot list conversations.")
        return []

    try:
        user_key = _get_user_conversations_key(user_id)
        conv_ids_bytes = redis_client.smembers(user_key)
        conv_ids = [c.decode('utf-8') for c in conv_ids_bytes]

        if not conv_ids:
            return []

        # M10 fix: batch fetch all titles in a single pipeline round-trip
        pipe = redis_client.pipeline(transaction=False)
        for conv_id in conv_ids:
            pipe.get(_get_title_key(conv_id))
        titles = pipe.execute()

        conversations_with_titles = []
        ghost_ids = []

        for conv_id, title in zip(conv_ids, titles):
            if title is not None:
                conversations_with_titles.append({
                    "id": conv_id,
                    "title": title.decode('utf-8') if title else "Untitled Chat"
                })
            else:
                ghost_ids.append(conv_id)

        # Prune ghost IDs from the user's set to prevent unbounded growth
        if ghost_ids:
            redis_client.srem(user_key, *ghost_ids)
            logger.info(f"[session_manager] Pruned {len(ghost_ids)} expired conversations for user {user_id}.")

        logger.info(f"[session_manager] Retrieved {len(conversations_with_titles)} active conversations for user {user_id}.")
        return conversations_with_titles
    except Exception as e:
        logger.error(f"[session_manager] Error retrieving conversations for user {user_id}: {e}")
        return []


# --- Conversation History ---
def get_conversation_history(user_id: str, conversation_id: str) -> Optional[RedisChatMessageHistory]:
    """
    Retrieves or creates a RedisChatMessageHistory instance for a given user and conversation ID.
    Manages the session entry in the global SESSIONS dictionary.
    Also loads profile and summaries from Redis if conversation is new to in-memory cache.
    Returns None if IDs are invalid or cannot be processed.
    Raises RuntimeError if Redis connection fails during instantiation.
    """
    if not user_id or not conversation_id:
        logger.warning(f"[session] get_conversation_history called with invalid IDs. User: {user_id}, Conv: {conversation_id}.")
        return None

    if redis_client is None:
        logger.error("[session] Redis client not initialized. Cannot manage session history.")
        raise RuntimeError("Redis client is not initialized. Cannot manage session history.")

    # Enforce ownership: conversation_id must belong to the user
    try:
        if not redis_client.sismember(_get_user_conversations_key(user_id), conversation_id):
            logger.warning(f"[session] Conversation {conversation_id} not found for user {user_id}.")
            return None
    except Exception as e:
        logger.error(f"[session] Error validating conversation ownership for {user_id}/{conversation_id}: {e}")
        raise RuntimeError(f"Failed to validate conversation ownership: {e}") from e

    # Ensure user_id entry exists in SESSIONS
    if user_id not in SESSIONS:
        SESSIONS[user_id] = {}
        logger.info(f"[session] Initializing new user entry in SESSIONS for: {user_id}")

    # Load or retrieve conversation data
    if conversation_id not in SESSIONS[user_id]:
        logger.info(f"[session] Initializing new conversation entry for user {user_id}, conversation: {conversation_id}")

        persisted_data = load_conversation_data_from_redis(conversation_id)

        try:
            redis_history = RedisChatMessageHistory(session_id=conversation_id, redis_client=redis_client)
        except Exception as e:
            logger.error(f"[session] ERROR creating RedisChatMessageHistory for conv {conversation_id}: {e}")
            raise RuntimeError(f"Failed to initialize RedisChatMessageHistory for conversation {conversation_id}: {e}") from e

        _enforce_session_bounds()
        SESSIONS[user_id][conversation_id] = {
            "chat_history_redis": redis_history,
            "profile": persisted_data["profile"],
            "summaries": persisted_data["summaries"],
            "title": persisted_data["title"]
        }
        return redis_history
    else:
        conversation_data = SESSIONS[user_id][conversation_id]
        redis_history = conversation_data.get("chat_history_redis")

        # Re-create history object if missing or wrong type
        if redis_history is None or not isinstance(redis_history, RedisChatMessageHistory):
            logger.warning(f"[session] Re-initializing RedisChatMessageHistory for conv: {conversation_id}")
            try:
                redis_history = RedisChatMessageHistory(session_id=conversation_id, redis_client=redis_client)
                conversation_data["chat_history_redis"] = redis_history
            except Exception as e:
                logger.error(f"[session] ERROR re-initializing RedisChatMessageHistory for conv {conversation_id}: {e}")
                raise RuntimeError(f"Failed to re-initialize RedisChatMessageHistory: {e}") from e

        if "profile" not in conversation_data:
            conversation_data["profile"] = {}
        if "summaries" not in conversation_data:
            conversation_data["summaries"] = []

        return redis_history
