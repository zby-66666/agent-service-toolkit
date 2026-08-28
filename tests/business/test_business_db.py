import sqlite3
from pathlib import Path

import pytest

from scripts import create_business_db, query_business_db, seed_business_db


@pytest.fixture
def business_db(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Path:
    """为每个测试创建独立的临时业务数据库。"""
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
        query_business_db,
        "DATABASE_PATH",
        database_path,
    )

    create_business_db.create_database()
    seed_business_db.seed_database()

    return database_path


def test_schema_and_seed_counts(business_db: Path) -> None:
    """验证四张表及种子数据数量。"""
    connection = sqlite3.connect(business_db)

    try:
        counts = {
            table_name: connection.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
            for table_name in (
                "customer",
                "device",
                "ticket",
                "repair_record",
            )
        }
    finally:
        connection.close()

    assert counts == {
        "customer": 2,
        "device": 3,
        "ticket": 4,
        "repair_record": 2,
    }


def test_customer_tickets_include_unrepaired_ticket(
    business_db: Path,
) -> None:
    """验证查询结果会保留没有维修记录的工单。"""
    tickets = query_business_db.get_customer_tickets(customer_id=1)

    ticket_ids = [ticket[2] for ticket in tickets]
    repair_counts = [ticket[5] for ticket in tickets]

    assert ticket_ids == [1001, 1002, 1003]
    assert repair_counts == [1, 1, 0]


def test_device_repair_count(business_db: Path) -> None:
    """验证设备维修次数可以跨多张工单累计。"""
    repair_count = query_business_db.get_device_repair_count("SN-ACME-1001")

    assert repair_count == 2


def test_missing_device_raises_error(business_db: Path) -> None:
    """验证查询不存在的设备时给出明确错误。"""
    with pytest.raises(ValueError, match="没有找到设备"):
        query_business_db.get_device_repair_count("UNKNOWN-DEVICE")


def test_foreign_key_rejects_unknown_customer(
    business_db: Path,
) -> None:
    """验证外键会拒绝属于不存在客户的设备。"""
    connection = sqlite3.connect(business_db)

    try:
        connection.execute("PRAGMA foreign_keys = ON")

        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO device (
                    id,
                    customer_id,
                    serial_number,
                    model,
                    purchase_date
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    999,
                    999,
                    "INVALID-SERIAL",
                    "Invalid Model",
                    "2026-01-01",
                ),
            )
    finally:
        connection.close()


def test_seed_refuses_duplicate_data(business_db: Path) -> None:
    """验证种子脚本不会重复插入数据。"""
    with pytest.raises(RuntimeError, match="拒绝重复写入"):
        seed_business_db.seed_database()
