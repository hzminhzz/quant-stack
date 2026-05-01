from __future__ import annotations

import asyncio
import json
import os
import shutil
from contextlib import AsyncExitStack
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


DEFAULT_PAPER_SEARCH_MCP_COMMAND = "/root/.local/bin/paper-search-mcp"


def resolve_paper_search_mcp_command(command: str | None = None) -> str:
    if command:
        return command

    env_command = os.getenv("PAPER_SEARCH_MCP_COMMAND", "").strip()
    if env_command:
        return env_command

    discovered = shutil.which("paper-search-mcp")
    if discovered:
        return discovered

    return DEFAULT_PAPER_SEARCH_MCP_COMMAND


class PaperSearchMCPClient:
    def __init__(
        self,
        command: str | None = None,
        args: list[str] | None = None,
        env: dict[str, str] | None = None,
    ) -> None:
        self.command = resolve_paper_search_mcp_command(command)
        self.args = args or []
        self.env = env or dict(os.environ)
        self._stack: AsyncExitStack | None = None
        self._session: ClientSession | None = None

    async def __aenter__(self) -> "PaperSearchMCPClient":
        await self.connect()
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        await self.close()

    @property
    def session(self) -> ClientSession:
        if self._session is None:
            raise RuntimeError("PaperSearchMCPClient is not connected. Call connect() first.")
        return self._session

    async def connect(self) -> None:
        if self._session is not None:
            return

        server_params = StdioServerParameters(
            command=self.command,
            args=self.args,
            env=self.env,
        )

        stack = AsyncExitStack()
        try:
            read_stream, write_stream = await stack.enter_async_context(stdio_client(server_params))
            session = await stack.enter_async_context(ClientSession(read_stream, write_stream))
            await session.initialize()
        except Exception:
            await stack.aclose()
            raise

        self._stack = stack
        self._session = session

    async def close(self) -> None:
        if self._stack is not None:
            await self._stack.aclose()
        self._stack = None
        self._session = None

    async def list_tools(self) -> list[str]:
        tools = await self.session.list_tools()
        return [tool.name for tool in tools.tools]

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> Any:
        result = await self.session.call_tool(name, arguments=arguments or {})

        structured = getattr(result, "structured_content", None)
        if structured is None:
            structured = getattr(result, "structuredContent", None)
        if structured is not None:
            return structured

        for item in getattr(result, "content", []):
            text = getattr(item, "text", None)
            if not text:
                continue
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return text

        raise RuntimeError(f"Tool {name!r} returned no usable content")

    async def search_papers(
        self,
        query: str,
        max_results_per_source: int = 5,
        sources: str = "all",
        year: str | None = None,
    ) -> Any:
        arguments: dict[str, Any] = {
            "query": query,
            "max_results_per_source": max_results_per_source,
            "sources": sources,
        }
        if year:
            arguments["year"] = year

        return await self.call_tool("search_papers", arguments)


def search_papers_sync(
    query: str,
    max_results_per_source: int = 5,
    sources: str = "all",
    year: str | None = None,
    command: str | None = None,
) -> Any:
    async def _run() -> Any:
        async with PaperSearchMCPClient(command=command) as client:
            return await client.search_papers(
                query=query,
                max_results_per_source=max_results_per_source,
                sources=sources,
                year=year,
            )

    return asyncio.run(_run())
