# agent_core.py - Production-hardened agent with direct user_id routing
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables.history import RunnableWithMessageHistory

from typing import Dict, Any, Optional, Callable
from functools import partial

from llm_setup import llm
from tools_setup import tools
from session_manager import get_conversation_history, SESSIONS
from config import logger, AGENT_VERBOSE


SYSTEM_PROMPT = """
You are a friendly and knowledgeable AI tutor designed to answer children's questions appropriately for their age, country, and school grade.

**How to Answer:**
1.  **Student Context:** Tailor your language, examples, and depth to the `user_profile` (age, country, class). Default to an elementary school level if no profile is provided.
2.  **File Summaries:** If the user references an uploaded document, prioritize its summary from `{file_summaries}`. Cite the filename when relevant.
3.  **Web Search:** If you lack information, need current data, or the topic is time-sensitive, use the `tavily_search` tool. Synthesize results into a clear, child-friendly answer and include relevant source URLs.
4.  **Direct Answer:** Otherwise, answer directly from your knowledge base or conversation history.
5.  **Clarity & Conciseness:** Use simple words and concepts. Avoid jargon or explain it clearly. Be concise, but expand if a deeper explanation genuinely aids understanding.
6.  **Safety:** Ensure all answers are safe, appropriate for children, and avoid harmful/inappropriate content. You may recommend further safe reading or resources.

**Current Context:**
- User Profile: `{user_profile}`
- Uploaded Summaries: `{file_summaries}`
"""

prompt = ChatPromptTemplate.from_messages(
    [
        ("system", SYSTEM_PROMPT),
        MessagesPlaceholder(variable_name="chat_history"),
        ("user", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ]
)

# ─── RESILIENT AGENT CONSTRUCTION ──────────────────────────────────────────
# langchain.agents API is extremely volatile. We pivot through multiple layers:
# 1. Modern unified create_agent (if available)
# 2. LangGraph prebuilt (The modern standard)
# 3. LangChain Classic (Legacy fallback)
# 4. Direct tool-bound chain (Minimal fallback)

_agent_executor = None

try:
    # Attempt 1: Modern create_agent (unified factory)
    from langchain.agents import create_agent
    _agent_executor = create_agent(llm, tools, system_prompt=SYSTEM_PROMPT)
    logger.info("[agent_core] Agent initialized via langchain.agents.create_agent factory.")
except (ImportError, AttributeError):
    try:
        # Attempt 2: LangGraph React Agent (Modern standard for tool loops)
        from langgraph.prebuilt import create_react_agent
        # Note: LangGraph agents handle prompts differently; we use a simple wrapper or binding
        _agent_executor = create_react_agent(llm, tools, state_modifier=SYSTEM_PROMPT)
        logger.info("[agent_core] Agent initialized via langgraph.prebuilt.create_react_agent.")
    except (ImportError, Exception):
        try:
            # Attempt 3: Legacy AgentExecutor (via Classic or standard)
            try:
                from langchain.agents import create_tool_calling_agent, AgentExecutor
            except ImportError:
                from langchain_classic.agents import create_tool_calling_agent, AgentExecutor
            
            agent = create_tool_calling_agent(llm, tools, prompt)
            _agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=AGENT_VERBOSE, handle_parsing_errors=True)
            logger.info("[agent_core] Agent initialized via AgentExecutor (Classic/Legacy path).")
        except (ImportError, Exception) as e:
            logger.warning(f"[agent_core] All agent factories failed ({e}); using direct LLM chain (minimal tools).")

if _agent_executor is None:
    # Final fallback: direct LLM chain with tools bound. No agent loop/reasoning.
    from langchain_core.runnables import RunnableLambda
    _llm_with_tools = llm.bind_tools(tools) if tools else llm
    _direct_prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        MessagesPlaceholder(variable_name="chat_history"),
        ("user", "{input}"),
    ])
    _agent_executor = (
        _direct_prompt
        | _llm_with_tools
        | StrOutputParser()
        | RunnableLambda(lambda x: {"output": x})
    )
    logger.info("[agent_core] Agent initialized via direct LLM chain fallback.")

agent_executor = _agent_executor


# --- FIX C1: Direct O(1) lookup instead of O(n) linear scan ---
# The user_id is passed via the LangChain config["configurable"]["user_id"]
# and extracted here to avoid scanning all SESSIONS.
def get_session_history(session_id: str, user_id: str):
    """
    Get session history for a given session_id (conversation_id).
    """

    if not user_id:
        logger.error(f"[agent_core] Could not resolve user_id for session_id {session_id}.")
        raise RuntimeError(f"Session owner not found for conversation {session_id}")

    logger.info(f"[agent_core] Resolved user_id={user_id} for session_id={session_id}")
    return get_conversation_history(user_id, session_id)


# Create the RunnableWithMessageHistory instance with user_id passthrough
with_message_history = RunnableWithMessageHistory(
    agent_executor,
    get_session_history,
    input_messages_key="input",
    history_messages_key="chat_history",
    history_factory_config=[
        {
            "id": "session_id",
            "annotation": str,
            "is_shared": True,
        },
        {
            "id": "user_id",
            "annotation": str,
            "is_shared": True,
        },
    ],
)
