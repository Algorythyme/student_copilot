# agent_core.py — Sovereign tool-calling agent (zero framework dependency)
# All langchain agent factories (create_agent, create_tool_calling_agent,
# create_react_agent) now internally produce LangGraph CompiledStateGraphs
# that expect {"messages": [...]} input. This is fundamentally incompatible
# with the RunnableWithMessageHistory wrapping that passes dict-based inputs
# {"input", "chat_history", "user_profile", "file_summaries"}.
#
# Solution: Manual tool-calling loop via RunnableLambda. Full control,
# zero volatility, proper prompt rendering, complete tool execution.

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableLambda
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from typing import Any, AsyncIterator, Dict, List, Optional

from llm_setup import llm
from tools_setup import tavily_tool, tools
from session_manager import get_conversation_history, SESSIONS
from config import logger, REQUIRE_WEB_SEARCH
from privacy_utils import (
    WebSearchRequiredError,
    run_required_web_search,
    sanitize_public_reply,
)

# ─── SYSTEM PROMPT ──────────────────────────────────────────────────────────
SYSTEM_PROMPT = """\
You are a friendly and knowledgeable AI tutor designed to answer children's questions appropriately for their age, country, and school grade.

**How to Answer:**
1.  **Student Context:** Tailor your language, examples, and depth to the `user_profile` (age, country, class). Default to an elementary school level if no profile is provided.
2.  **File Summaries:** If the user references an uploaded document, prioritize its summary from `{file_summaries}`.
3.  **Web Search:** When sanitized web context is provided, use it to answer current or general-knowledge questions.
4.  **Direct Answer:** Otherwise, answer directly from your knowledge base or conversation history.
5.  **Clarity & Conciseness:** Use simple words and concepts. Avoid jargon or explain it clearly. Be concise, but expand if a deeper explanation genuinely aids understanding.
6.  **Safety:** Ensure all answers are safe, appropriate for children, and avoid harmful/inappropriate content.
7.  **No Inline Citations:** NEVER include citations, URLs, links, filenames, footnotes, or source references (e.g. "[source]", "according to example.com", "(see chapter 3 of ...)") in your reply body. Source provenance is retained internally.

**Current Context:**
- User Profile: `{user_profile}`
- Uploaded Summaries: `{file_summaries}`
- Sanitized Web Context: `{web_context}`\
"""

# Prompt template: system + history + user input (no agent_scratchpad needed)
_prompt = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_PROMPT),
    MessagesPlaceholder(variable_name="chat_history"),
    ("user", "{input}"),
])

# ─── SOVEREIGN TOOL-CALLING LOOP ───────────────────────────────────────────
_llm_with_tools = llm
_tool_map: Dict[str, Any] = {t.name: t for t in tools} if tools else {}
_MAX_TOOL_ITERATIONS = 5

async def _required_web_context(input_dict: dict) -> tuple[str, bool]:
    async def search(query: str):
        if tavily_tool is None:
            raise WebSearchRequiredError(
                "Required web search is unavailable. Please try again later."
            )
        return await tavily_tool.ainvoke({"query": query})

    try:
        context, used = await run_required_web_search(
            input_dict,
            REQUIRE_WEB_SEARCH,
            search if tavily_tool is not None else None,
        )
    except WebSearchRequiredError:
        logger.error(
            "[agent_core] required web search unavailable search_failed=true"
        )
        raise
    if used:
        logger.info("[agent_core] required web search completed search_used=true")
    return context, used


async def _sovereign_agent(input_dict: dict, config=None) -> dict:
    """
    Manual tool-calling agent loop.
    Renders prompt → calls LLM → executes any tool calls → loops until text response.
    Fully compatible with RunnableWithMessageHistory's dict-based input.
    """
    web_context, search_used = await _required_web_context(input_dict)

    # 1. Render the prompt template into messages
    rendered = _prompt.invoke({
        "input": input_dict.get("input", ""),
        "chat_history": input_dict.get("chat_history", []),
        "user_profile": input_dict.get("user_profile", "no profile provided"),
        "file_summaries": input_dict.get("file_summaries", "no uploaded file summaries"),
        "web_context": web_context or "none",
    })
    messages = list(rendered.to_messages())

    # 2. Tool-calling loop (bounded)
    response = None
    for iteration in range(_MAX_TOOL_ITERATIONS):
        response = await _llm_with_tools.ainvoke(messages, config=config)
        messages.append(response)

        tool_calls = getattr(response, "tool_calls", None)
        if not tool_calls:
            break  # No tool calls — we have the final text response

        logger.info(f"[agent_core] Iteration {iteration + 1}: executing {len(tool_calls)} tool call(s).")
        for tc in tool_calls:
            tool_fn = _tool_map.get(tc["name"])
            if tool_fn:
                try:
                    result = await tool_fn.ainvoke(tc["args"])
                    if tc["name"] == "tavily_search":
                        search_used = True
                except Exception as e:
                    logger.error(f"[agent_core] Tool '{tc['name']}' error: {e}")
                    if REQUIRE_WEB_SEARCH and tc["name"] == "tavily_search":
                        raise WebSearchRequiredError(
                            "Required web search failed. Please try again later."
                        ) from e
                    result = f"Tool execution failed: {e}"
            else:
                logger.warning(f"[agent_core] Unknown tool requested: {tc['name']}")
                result = f"Unknown tool: {tc['name']}"
            messages.append(
                ToolMessage(
                    content=sanitize_public_reply(str(result)),
                    tool_call_id=tc["id"],
                )
            )

    # 3. Extract final text output
    output = ""
    if response is not None:
        output = getattr(response, "content", "") or ""
    if not output:
        output = "I couldn't generate a response. Please try again."

    return {
        "output": sanitize_public_reply(output),
        "search_used": search_used,
        "search_failed": False,
    }


agent_executor = RunnableLambda(_sovereign_agent)
logger.info("[agent_core] Sovereign agent initialized (manual tool loop, zero agent-factory deps).")


def history_to_messages(message_history: Optional[List[Dict[str, str]]] = None) -> list:
    """Convert SMS/web inline {role, content} history to LangChain messages."""
    messages = []
    for msg in message_history or []:
        role = (msg.get("role") or "user").lower()
        content = msg.get("content") or ""
        if role == "assistant":
            messages.append(AIMessage(content=content))
        else:
            messages.append(HumanMessage(content=content))
    return messages


async def run_agent_inline(input_dict: dict) -> dict:
    """
    Run the sovereign agent with inline message history (no Redis session_id).
    Expects chat_history as LangChain messages or omits it for a fresh turn.
    """
    payload = {
        "input": input_dict.get("input", ""),
        "user_profile": input_dict.get("user_profile", "no profile provided"),
        "file_summaries": input_dict.get("file_summaries", "no uploaded file summaries"),
        "chat_history": input_dict.get("chat_history") or [],
        "has_private_context": bool(input_dict.get("has_private_context")),
    }
    return await _sovereign_agent(payload)


def _chunk_text(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text") or ""))
            else:
                text = getattr(item, "text", None)
                if text:
                    parts.append(str(text))
        return "".join(parts)
    return str(content)


async def run_agent_inline_stream(
    input_dict: dict,
    metadata_out: Optional[Dict[str, bool]] = None,
) -> AsyncIterator[str]:
    """
    Run the same agent and emit only the fully sanitized final answer.
    Buffering prevents a split URL from leaking across token boundaries.
    """
    web_context, search_used = await _required_web_context(input_dict)
    if metadata_out is not None:
        metadata_out.update(search_used=search_used, search_failed=False)

    rendered = _prompt.invoke({
        "input": input_dict.get("input", ""),
        "chat_history": input_dict.get("chat_history") or [],
        "user_profile": input_dict.get("user_profile", "no profile provided"),
        "file_summaries": input_dict.get("file_summaries", "no uploaded file summaries"),
        "web_context": web_context or "none",
    })
    messages = list(rendered.to_messages())
    final_output = ""

    for iteration in range(_MAX_TOOL_ITERATIONS):
        response = None

        async for chunk in _llm_with_tools.astream(messages):
            response = chunk if response is None else response + chunk

        if response is None:
            break

        messages.append(response)
        tool_calls = getattr(response, "tool_calls", None)
        if not tool_calls:
            final_output = _chunk_text(getattr(response, "content", None))
            break

        logger.info(
            f"[agent_core] Stream iteration {iteration + 1}: executing {len(tool_calls)} tool call(s)."
        )
        for tc in tool_calls:
            tool_fn = _tool_map.get(tc["name"])
            if tool_fn:
                try:
                    result = await tool_fn.ainvoke(tc["args"])
                    if tc["name"] == "tavily_search":
                        search_used = True
                except Exception as e:
                    logger.error(f"[agent_core] Tool '{tc['name']}' error: {e}")
                    if metadata_out is not None:
                        metadata_out["search_failed"] = tc["name"] == "tavily_search"
                    if REQUIRE_WEB_SEARCH and tc["name"] == "tavily_search":
                        raise WebSearchRequiredError(
                            "Required web search failed. Please try again later."
                        ) from e
                    result = "Tool execution failed."
            else:
                logger.warning(f"[agent_core] Unknown tool requested: {tc['name']}")
                result = f"Unknown tool: {tc['name']}"
            messages.append(
                ToolMessage(
                    content=sanitize_public_reply(str(result)),
                    tool_call_id=tc["id"],
                )
            )
    else:
        final_output = "I couldn't generate a response. Please try again."

    if metadata_out is not None:
        metadata_out["search_used"] = search_used
    safe_output = sanitize_public_reply(final_output)
    if safe_output:
        yield safe_output


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
