from typing import Any

from mcp.server.fastmcp import FastMCP

from business.queries import (
    get_customer_tickets as query_customer_tickets,
)
from business.queries import (
    get_device_repair_history as query_device_repair_history,
)

mcp = FastMCP(
    "ticket-mcp-server",
    instructions="Provide read-only access to AcmeTech customer ticket data.",
)


@mcp.tool()
def get_customer_tickets(customer_id: int) -> dict[str, Any]:
    """Look up all support tickets for a customer by numeric customer ID.

    Use this tool when the user asks about a customer's devices, tickets,
    ticket statuses, priorities, or repair counts.
    """
    tickets = query_customer_tickets(customer_id)

    return {
        "customer_id": customer_id,
        "ticket_count": len(tickets),
        "tickets": tickets,
    }


@mcp.tool()
def get_device_repair_history(serial_number: str) -> dict[str, Any]:
    """Look up ticket and repair history for a device by exact serial number.

    Use this tool when the user asks about a device's previous problems,
    diagnoses, repair actions, technicians, or total repair count.
    """
    history = query_device_repair_history(serial_number)

    if not history:
        return {
            "serial_number": serial_number.strip(),
            "found": False,
            "ticket_count": 0,
            "repair_record_count": 0,
            "history": [],
        }

    ticket_ids = {row["ticket_id"] for row in history if row["ticket_id"] is not None}

    repair_record_count = sum(row["repair_record_id"] is not None for row in history)

    return {
        "serial_number": history[0]["serial_number"],
        "device_model": history[0]["device_model"],
        "customer_id": history[0]["customer_id"],
        "customer_name": history[0]["customer_name"],
        "found": True,
        "ticket_count": len(ticket_ids),
        "repair_record_count": repair_record_count,
        "history": history,
    }


if __name__ == "__main__":
    mcp.run(transport="stdio")
