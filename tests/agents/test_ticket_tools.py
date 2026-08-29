import json
from pathlib import Path

import pytest

from agents import ticket_tools
from business import queries
from scripts import create_business_db, seed_business_db


@pytest.fixture
def ticket_tool_database(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Path:
    """为 Ticket Tool 创建独立的临时业务数据库。"""
    database_path = tmp_path / "business.db"

    monkeypatch.setattr(
        create_business_db,
        "DATABASE_PATH",
        database_path,
    )
    monkeypatch.setattr(
        seed_business_db,
        "DATABASE_PATH",
        database_path,
    )
    monkeypatch.setattr(
        queries,
        "BUSINESS_DATABASE_PATH",
        database_path,
    )

    create_business_db.create_database()
    seed_business_db.seed_database()

    return database_path


def test_customer_tickets_tool_schema() -> None:
    """验证客户工单工具的名称和参数结构。"""
    schema = ticket_tools.customer_tickets.args_schema.model_json_schema()

    assert ticket_tools.customer_tickets.name == "Customer_Tickets"
    assert schema["properties"]["customer_id"]["type"] == "integer"
    assert schema["required"] == ["customer_id"]


def test_customer_tickets_returns_json(
    ticket_tool_database: Path,
) -> None:
    """验证客户工单工具返回带字段名的 JSON。"""
    result = ticket_tools.customer_tickets.invoke({"customer_id": 1})
    data = json.loads(result)

    assert data["customer_id"] == 1
    assert data["ticket_count"] == 3
    assert data["tickets"][0]["ticket_id"] == 1001
    assert data["tickets"][2]["repair_count"] == 0


def test_customer_tickets_rejects_invalid_id(
    ticket_tool_database: Path,
) -> None:
    """验证客户 ID 必须是正整数。"""
    with pytest.raises(
        ValueError,
        match="customer_id 必须是正整数",
    ):
        ticket_tools.customer_tickets.invoke({"customer_id": 0})


def test_device_repair_history_returns_counts(
    ticket_tool_database: Path,
) -> None:
    """验证设备维修历史工具可以跨工单统计记录。"""
    result = ticket_tools.device_repair_history.invoke({"serial_number": "SN-ACME-1001"})
    data = json.loads(result)

    assert data["found"] is True
    assert data["ticket_count"] == 2
    assert data["repair_record_count"] == 2
    assert data["history"][0]["diagnosis"] == ("The internal display cable was loose.")


def test_device_repair_history_handles_missing_device(
    ticket_tool_database: Path,
) -> None:
    """验证不存在的设备返回明确的空结果。"""
    result = ticket_tools.device_repair_history.invoke({"serial_number": "UNKNOWN-DEVICE"})
    data = json.loads(result)

    assert data == {
        "serial_number": "UNKNOWN-DEVICE",
        "found": False,
        "ticket_count": 0,
        "repair_record_count": 0,
        "history": [],
    }


def test_device_repair_history_rejects_blank_serial(
    ticket_tool_database: Path,
) -> None:
    """验证设备序列号不能为空。"""
    with pytest.raises(
        ValueError,
        match="serial_number 不能为空",
    ):
        ticket_tools.device_repair_history.invoke({"serial_number": "   "})
