# tools_setup.py
import asyncio
from typing import List, Optional

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field
from tavily import TavilyClient

from config import TAVILY_KEY, logger
from privacy_utils import sanitize_web_results


class TavilySearchArgs(BaseModel):
    query: str = Field(..., description="Search query")
    include_domains: Optional[List[str]] = Field(default=None, description="Only include results from these domains")
    exclude_domains: Optional[List[str]] = Field(default=None, description="Exclude results from these domains")


# Cache the client ΓÇö no need to re-instantiate per call
_tavily_client = TavilyClient(api_key=TAVILY_KEY) if TAVILY_KEY else None


def _tavily_search(query: str, include_domains: Optional[List[str]] = None, exclude_domains: Optional[List[str]] = None):
    if not _tavily_client:
        raise ValueError("Tavily is not configured (missing TAVILY_API_KEY).")

    resp = _tavily_client.search(
        query=query,
        max_results=3,
        include_domains=include_domains,
        exclude_domains=exclude_domains,
    )
    return sanitize_web_results(resp)


async def _tavily_search_async(query: str, include_domains: Optional[List[str]] = None, exclude_domains: Optional[List[str]] = None):
    # TavilyClient is synchronous; run it in a worker thread so a slow search
    # cannot block the event loop while the agent awaits the tool.
    return await asyncio.to_thread(_tavily_search, query, include_domains, exclude_domains)


tavily_tool = (
    StructuredTool.from_function(
        func=_tavily_search,
        coroutine=_tavily_search_async,
        name="tavily_search",
        description="Search the web for current information and return sanitized result text.",
        args_schema=TavilySearchArgs,
    )
    if TAVILY_KEY
    else None
)

tools = [tavily_tool] if tavily_tool else []

if not tools:
    logger.warning("WARNING: No tools available for the agent as Tavily key is missing.") # Changed from print
else:
    logger.info("[startup] TavilySearch tool initialized.") # Changed from print
