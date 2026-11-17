"""Optional, read-only public travel help through the Agents SDK MCP client."""

from agents import RunContextWrapper, function_tool
from agents.mcp import MCPServerStreamableHttp


UNAVAILABLE = (
    "Public help lookup is unavailable or returned no usable information. "
    "Tell the customer that the public guidance could not be verified; do not invent an answer or source."
)


def public_help_server() -> MCPServerStreamableHttp:
    return MCPServerStreamableHttp(
        name="Public travel help",
        params={
            "url": "https://mcp.parallel.ai/mcp",
            "headers": {"User-Agent": "openai-cs-agents-demo/public-help"},
            "timeout": 10,
            "sse_read_timeout": 30,
        },
        client_session_timeout_seconds=30,
    )


def _lookup_error(context: RunContextWrapper, error: Exception) -> str:
    return UNAVAILABLE


@function_tool(failure_error_function=_lookup_error)
async def public_help_lookup(search_terms: str) -> str:
    """Find public airline-travel help pages, with excerpts and original source URLs.

    Args:
        search_terms: A short public topic query, preferably naming an official source.
            Never include passenger names, booking references, account details, medical
            information, or other private conversation data. Do not use for mock airline
            policies, bookings, live flight status, or compensation decisions.
    """
    if not search_terms.strip():
        return UNAVAILABLE
    async with public_help_server() as server:
        result = await server.call_tool(
            "web_search",
            {
                "objective": (
                    "Find official public travel help pages about the following topic. "
                    "Return relevant guidance with original source URLs: " + search_terms
                ),
                "search_queries": [search_terms],
            },
        )
    # MCP's wire name is stable across Python SDK versions.
    if result.model_dump(by_alias=True).get("isError"):
        return UNAVAILABLE
    text = "\n".join(part.text for part in result.content if part.type == "text")
    return text or UNAVAILABLE
