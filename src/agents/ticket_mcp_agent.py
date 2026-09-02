"""Ticket Agent backed by tools from the local Ticket MCP Server."""

import os
import sys
from pathlib import Path

from langchain.agents import create_agent
from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.sessions import Connection, StdioConnection
from langgraph.graph.state import CompiledStateGraph

from agents.lazy_agent import LazyLoadingAgent
from core import get_model, settings

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_PATH = PROJECT_ROOT / "src"

TICKET_MCP_PROMPT = """
You are AcmeTech's support ticket assistant.

Use the available MCP tools to answer questions about customer tickets,
devices, and repair history.

Important rules:
- Use get_customer_tickets for questions about a customer's tickets.
- Use get_device_repair_history for questions about a device's repair history.
- Do not invent customer IDs, serial numbers, tickets, or repair records.
- If a required customer ID or serial number is missing, ask the user for it.
- Base business-specific answers only on MCP tool results.
- Explain tool results clearly instead of showing raw tool responses.
"""


class TicketMCPAgent(LazyLoadingAgent):
    """Agent that loads ticket tools from a local MCP Server."""

    def __init__(self) -> None:
        super().__init__()
        self._mcp_client: MultiServerMCPClient | None = None
        self._mcp_tools: list[BaseTool] = []

    async def load(self) -> None:
        """Start the MCP Server, discover its tools, and create the Agent."""
        child_env = os.environ.copy()
        existing_pythonpath = child_env.get("PYTHONPATH")

        child_env["PYTHONPATH"] = (
            f"{SRC_PATH}{os.pathsep}{existing_pythonpath}" if existing_pythonpath else str(SRC_PATH)
        )

        connections: dict[str, Connection] = {
            "ticket": StdioConnection(
                transport="stdio",
                command=sys.executable,
                args=["-m", "mcp_servers.ticket_server"],
                cwd=str(PROJECT_ROOT),
                env=child_env,
            )
        }

        self._mcp_client = MultiServerMCPClient(connections)
        self._mcp_tools = await self._mcp_client.get_tools()
        self._graph = self._create_graph()
        self._loaded = True

    def _create_graph(self) -> CompiledStateGraph:
        """Create the executable Agent with the discovered MCP tools."""
        model = get_model(settings.DEFAULT_MODEL)

        return create_agent(
            model=model,
            tools=self._mcp_tools,
            name="ticket-mcp-agent",
            system_prompt=TICKET_MCP_PROMPT,
        )


ticket_mcp_agent = TicketMCPAgent()
