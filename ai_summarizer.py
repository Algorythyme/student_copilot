# ai_summarizer.py
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from llm_setup import llm
from config import logger


async def generate_conversation_title(initial_message: str) -> str:
    """Generates a concise title for a conversation based on its initial message."""
    if not initial_message.strip():
        return "New Chat"

    title_prompt = ChatPromptTemplate.from_messages([
        ("system", "You are an assistant that creates a very concise (max 5 words) title for a conversation. "
                   "The title should capture the main topic of the initial user message. "
                   "Respond with ONLY the title, no extra text or punctuation beyond the title itself. "
                   "If the message is generic, use a generic title like 'General Chat' or 'New Chat'."),
        ("user", "Initial message: {initial_message}\n\nTitle:")
    ])
    title_chain = title_prompt | llm | StrOutputParser()

    try:
        title = await title_chain.ainvoke({"initial_message": initial_message})
        title = title.strip().replace('"', '').replace("'", "").replace('.', '')
        if len(title.split()) > 7:
            title = " ".join(title.split()[:7]) + "..."
        logger.info(f"[ai_summarizer] Generated title: '{title}'")
        return title
    except Exception as e:
        logger.error(f"[ai_summarizer] Failed to generate conversation title: {e}")
        return "Untitled Chat"


async def generate_learning_method(profile: dict) -> str:
    """Generates an initial personalized learning strategy based on user profile."""
    if not profile:
        return ""

    profile_str = ", ".join(f"{k}: {v}" for k, v in profile.items())

    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are an expert pedagogical AI. Based on the provided user profile (age, country, role, grade, etc.), "
                   "generate a highly effective, concise (2-3 sentences), and personalized learning strategy for this user. "
                   "This strategy will be appended to their context to help the tutor adapt better. Do NOT output anything other than the strategy."),
        ("user", "User Profile:\n{profile_str}\n\nLearning Strategy:")
    ])

    chain = prompt | llm | StrOutputParser()

    try:
        method = await chain.ainvoke({"profile_str": profile_str})
        logger.info("[ai_summarizer] Generated initial learning method.")
        return method.strip()
    except Exception as e:
        logger.error(f"[ai_summarizer] Failed to generate initial learning method: {e}")
        return ""


async def evaluate_session_learning_method(profile: dict, chat_history: str, current_method: str) -> str:
    """
    Evaluates the current learning method at the end of a session against the chat history
    and returns an updated learning strategy if there's something to add.
    """
    profile_str = ", ".join(f"{k}: {v}" for k, v in profile.items()) if profile else "Unknown"

    # Truncate chat history to prevent LLM token overflow (~6000 chars Γëê ~1500 tokens)
    MAX_HISTORY_CHARS = 6000
    if len(chat_history) > MAX_HISTORY_CHARS:
        chat_history = "...[earlier messages truncated]...\n" + chat_history[-MAX_HISTORY_CHARS:]

    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are an expert pedagogical AI reviewing a student's session. "
                   "Your goal is to optimize the student's personalized 'Learning Strategy'.\n"
                   "Review the provided Chat History. Does the student exhibit new learning behaviors, "
                   "struggles, or preferences that should modify their current Learning Strategy?\n"
                   "If YES: Output an updated, slightly expanded (3-4 sentences) Learning Strategy incorporating the new insights.\n"
                   "If NO: Output exactly the CURRENT strategy without any changes and no extra text.\n"
                   "Only output the strategy text. Do not output 'YES' or 'NO' prefixes."),
        ("user", "UserProfile: {profile_str}\n\n"
                 "CURRENT STRATEGY: {current_method}\n\n"
                 "CHAT HISTORY:\n{chat_history}\n\n"
                 "UPDATED STRATEGY (or exact same strategy if no update needed):")
    ])

    chain = prompt | llm | StrOutputParser()
    try:
        new_method = await chain.ainvoke({"profile_str": profile_str, "current_method": current_method, "chat_history": chat_history})
        return new_method.strip()
    except Exception as e:
        logger.error(f"[ai_summarizer] Failed to evaluate learning method: {e}")
        return current_method
