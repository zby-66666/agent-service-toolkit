import json

from langchain_core.tools import BaseTool, tool

from business.queries import (
    get_customer_tickets,
    get_device_repair_history,
)


def customer_tickets_func(customer_id: int) -> str:
    """Look up all support tickets for a customer by numeric customer ID.

    Use this tool when the user asks about a customer's devices, tickets,
    ticket status, priority, or number of repair records.
    """
    tickets = get_customer_tickets(customer_id)

    result = {
        "customer_id": customer_id,
        "ticket_count": len(tickets),
        "tickets": tickets,
    }

    return json.dumps(result, ensure_ascii=False)


customer_tickets: BaseTool = tool(customer_tickets_func)
customer_tickets.name = "Customer_Tickets"


def device_repair_history_func(serial_number: str) -> str:
    """Look up ticket and repair history for a device by exact serial number.

    Use this tool when the user asks about a device's previous problems,
    diagnoses, repair actions, technicians, or total repair count.
    """
    history = get_device_repair_history(serial_number)

    if not history:
        result = {
            "serial_number": serial_number.strip(),
            "found": False,
            "ticket_count": 0,
            "repair_record_count": 0,
            "history": [],
        }
    else:
        ticket_ids = {row["ticket_id"] for row in history if row["ticket_id"] is not None}

        repair_record_count = sum(row["repair_record_id"] is not None for row in history)

        result = {
            "serial_number": history[0]["serial_number"],
            "device_model": history[0]["device_model"],
            "customer_id": history[0]["customer_id"],
            "customer_name": history[0]["customer_name"],
            "found": True,
            "ticket_count": len(ticket_ids),
            "repair_record_count": repair_record_count,
            "history": history,
        }

    return json.dumps(result, ensure_ascii=False)


device_repair_history: BaseTool = tool(device_repair_history_func)
device_repair_history.name = "Device_Repair_History"
