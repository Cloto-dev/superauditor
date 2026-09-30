"""Talk to one MCP server: open a session over stdio or streamable HTTP, list tools, call one."""

from __future__ import annotations

import json
import os
from contextlib import asynccontextmanager

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import create_mcp_http_client, streamable_http_client


class ToolError(Exception):
    """The server answered the call with an error, or with something that is not a JSON object."""


@asynccontextmanager
async def open_session(command: list[str] | None = None, url: str | None = None, headers: dict | None = None):
    if url:
        async with create_mcp_http_client(headers=headers or {}) as http:
            async with streamable_http_client(url, http_client=http) as streams:
                async with ClientSession(streams[0], streams[1]) as session:
                    await session.initialize()
                    yield session
    else:
        # The server gets this process's environment: a server configured by
        # environment variables (a database path, a key) is checked as configured.
        params = StdioServerParameters(command=command[0], args=command[1:], env=dict(os.environ))
        async with stdio_client(params) as streams:
            async with ClientSession(streams[0], streams[1]) as session:
                await session.initialize()
                yield session


async def find_tool(session: ClientSession, name: str):
    listed = await session.list_tools()
    for tool in listed.tools:
        if tool.name == name:
            return tool
    return None


async def call_json(session: ClientSession, name: str, arguments: dict) -> dict:
    result = await session.call_tool(name, arguments)
    if getattr(result, "is_error", False):
        text = " ".join(getattr(c, "text", "") for c in result.content or [])
        raise ToolError(f"{name}({arguments}) returned an error: {text[:300]}")
    structured = getattr(result, "structured_content", None)
    if isinstance(structured, dict) and "findings" in structured:
        return structured
    for content in result.content or []:
        text = getattr(content, "text", None)
        if text is None:
            continue
        try:
            value = json.loads(text)
        except ValueError:
            continue
        if isinstance(value, dict):
            return value
    raise ToolError(f"{name}({arguments}) returned no JSON object")
