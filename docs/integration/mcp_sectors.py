# Copyright 2026 Sectors Hackathon
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""MCP Streamable HTTP for Sectors MCP.

Endpoint: https://sectors-mcp.supertype.ai/mcp
Auth: Authorization: Bearer <SECTORS_API_KEY>

Uses apiKey header pattern - mirrors adk-go-skill/apiKeyTransport but
in Python ADK via McpToolset(StreamableHTTPConnectionParams(headers=...)).

Ref: references/sectors-api-and-mcp.md, plan.md §6, https://adk.dev/mcp,
     https://docs.sectors.app/recipes/sectors-for-ai-agents/00-sectors-mcp-guide
"""

from __future__ import annotations

import os
from typing import Any

from google.adk.tools.mcp_tool.mcp_toolset import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPConnectionParams

SECTORS_MCP_URL = os.getenv("SECTORS_MCP_URL", "https://sectors-mcp.supertype.ai/mcp")


def sectors_mcp_toolset(
    api_key: str | None = None,
    *,
    url: str | None = None,
    tool_filter: list[str] | None = None,
    tool_list_cache_ttl_seconds: float | None = 60.0,
) -> McpToolset:
    """Create an McpToolset connected to the Sectors MCP streamable HTTP server.

    Args:
        api_key: Sectors API key. Defaults to SECTORS_API_KEY env.
        url: MCP endpoint override. Defaults to SECTORS_MCP_URL / known endpoint.
        tool_filter: Optional allowlist of MCP tool names to expose.
        tool_list_cache_ttl_seconds: Cache tools/list for this many seconds.

    Returns:
        McpToolset - pass as LlmAgent(tools=[..., toolset]) or via toolsets.
    """
    key = api_key or os.getenv("SECTORS_API_KEY") or os.getenv("SECTORS_MCP_API_KEY") or ""
    if not key:
        raise ValueError(
            "SECTORS_API_KEY is not set - required for Sectors MCP. "
            "Set SECTORS_API_KEY env or pass api_key=."
        )
    endpoint = url or SECTORS_MCP_URL
    headers: dict[str, Any] = {
        "Authorization": f"Bearer {key}",
    }
    return McpToolset(
        connection_params=StreamableHTTPConnectionParams(
            url=endpoint,
            headers=headers,
        ),
        tool_filter=tool_filter,
        tool_list_cache_ttl_seconds=tool_list_cache_ttl_seconds,
    )


def maybe_sectors_mcp_toolset(**kw) -> McpToolset | None:
    """Best-effort: return McpToolset if SECTORS_API_KEY is set, else None."""
    try:
        return sectors_mcp_toolset(**kw)
    except ValueError:
        return None
