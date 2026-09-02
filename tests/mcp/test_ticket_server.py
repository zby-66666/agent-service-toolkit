import os
import sys
from pathlib import Path

import pytest
from langchain_mcp_adapters.client import MultiServerMCPClient

from mcp_servers import ticket_server

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_PATH = PROJECT_ROOT / "src"


def test_get_customer_tickets_formats_query_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tickets = [
        {
            "customer_id": 7,
            "ticket_id": 1001,
            "status": "resolved",
        },
        {
            "customer_id": 7,
            "ticket_id": 1002,
            "status": "open",
        },
    ]

    def fake_query_customer_tickets(
        customer_id: int,
    ) -> list[dict[str, object]]:
        assert customer_id == 7
        return tickets

    monkeypatch.setattr(
        ticket_server,
        "query_customer_tickets",
        fake_query_customer_tickets,
    )

    result = ticket_server.get_customer_tickets(7)

    assert result["customer_id"] == 7
    assert result["ticket_count"] == 2
    assert result["tickets"] == tickets


def test_get_device_repair_history_counts_unique_tickets_and_repairs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    history = [
        {
            "serial_number": "SN-TEST-1",
            "device_model": "Test Device",
            "customer_id": 7,
            "customer_name": "Test Customer",
            "ticket_id": 1001,
            "repair_record_id": 5001,
        },
        {
            "serial_number": "SN-TEST-1",
            "device_model": "Test Device",
            "customer_id": 7,
            "customer_name": "Test Customer",
            "ticket_id": 1001,
            "repair_record_id": 5002,
        },
        {
            "serial_number": "SN-TEST-1",
            "device_model": "Test Device",
            "customer_id": 7,
            "customer_name": "Test Customer",
            "ticket_id": 1002,
            "repair_record_id": None,
        },
    ]

    monkeypatch.setattr(
        ticket_server,
        "query_device_repair_history",
        lambda serial_number: history,
    )

    result = ticket_server.get_device_repair_history("SN-TEST-1")

    assert result["found"] is True
    assert result["ticket_count"] == 2
    assert result["repair_record_count"] == 2
    assert result["history"] == history


def test_get_device_repair_history_handles_unknown_device(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        ticket_server,
        "query_device_repair_history",
        lambda serial_number: [],
    )

    result = ticket_server.get_device_repair_history(" UNKNOWN-DEVICE ")

    assert result == {
        "serial_number": "UNKNOWN-DEVICE",
        "found": False,
        "ticket_count": 0,
        "repair_record_count": 0,
        "history": [],
    }


@pytest.mark.asyncio
async def test_stdio_server_exposes_ticket_tools() -> None:
    child_env = os.environ.copy()
    existing_pythonpath = child_env.get("PYTHONPATH")

    child_env["PYTHONPATH"] = (
        f"{SRC_PATH}{os.pathsep}{existing_pythonpath}" if existing_pythonpath else str(SRC_PATH)
    )

    client = MultiServerMCPClient(
        {
            "ticket": {
                "transport": "stdio",
                "command": sys.executable,
                "args": ["-m", "mcp_servers.ticket_server"],
                "cwd": str(PROJECT_ROOT),
                "env": child_env,
            }
        }
    )

    tools = await client.get_tools()
    tools_by_name = {tool.name: tool for tool in tools}

    assert set(tools_by_name) == {
        "get_customer_tickets",
        "get_device_repair_history",
    }

    assert tools_by_name["get_customer_tickets"].args_schema["required"] == ["customer_id"]

    assert tools_by_name["get_device_repair_history"].args_schema["required"] == ["serial_number"]
