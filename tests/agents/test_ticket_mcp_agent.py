import os
import sys
from unittest.mock import AsyncMock, Mock, patch

import pytest
from langchain_core.tools import BaseTool

from agents.ticket_mcp_agent import (
    PROJECT_ROOT,
    SRC_PATH,
    TICKET_MCP_PROMPT,
    TicketMCPAgent,
)
from core import settings


def test_ticket_mcp_agent_starts_unloaded() -> None:
    agent = TicketMCPAgent()

    assert agent._loaded is False
    assert agent._mcp_client is None
    assert agent._mcp_tools == []


@pytest.mark.asyncio
async def test_load_discovers_tools_and_creates_graph() -> None:
    agent = TicketMCPAgent()

    mock_tool = Mock(spec=BaseTool)
    mock_client = Mock()
    mock_client.get_tools = AsyncMock(return_value=[mock_tool])
    mock_graph = Mock()

    with (
        patch(
            "agents.ticket_mcp_agent.MultiServerMCPClient",
            return_value=mock_client,
        ) as mock_client_class,
        patch.object(
            agent,
            "_create_graph",
            return_value=mock_graph,
        ) as mock_create_graph,
    ):
        await agent.load()

    connections = mock_client_class.call_args.args[0]
    ticket_connection = connections["ticket"]

    assert ticket_connection["transport"] == "stdio"
    assert ticket_connection["command"] == sys.executable
    assert ticket_connection["args"] == [
        "-m",
        "mcp_servers.ticket_server",
    ]
    assert ticket_connection["cwd"] == str(PROJECT_ROOT)

    python_paths = ticket_connection["env"]["PYTHONPATH"].split(os.pathsep)
    assert str(SRC_PATH) in python_paths

    mock_client.get_tools.assert_awaited_once_with()
    mock_create_graph.assert_called_once_with()

    assert agent._mcp_client is mock_client
    assert agent._mcp_tools == [mock_tool]
    assert agent._loaded is True
    assert agent.get_graph() is mock_graph


def test_create_graph_binds_model_and_mcp_tools() -> None:
    agent = TicketMCPAgent()

    mock_model = Mock()
    mock_tool = Mock(spec=BaseTool)
    mock_graph = Mock()
    agent._mcp_tools = [mock_tool]

    with (
        patch(
            "agents.ticket_mcp_agent.get_model",
            return_value=mock_model,
        ) as mock_get_model,
        patch(
            "agents.ticket_mcp_agent.create_agent",
            return_value=mock_graph,
        ) as mock_create_agent,
    ):
        graph = agent._create_graph()

    mock_get_model.assert_called_once_with(settings.DEFAULT_MODEL)
    mock_create_agent.assert_called_once_with(
        model=mock_model,
        tools=[mock_tool],
        name="ticket-mcp-agent",
        system_prompt=TICKET_MCP_PROMPT,
    )

    assert graph is mock_graph
