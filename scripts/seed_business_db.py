import sqlite3
from pathlib import Path

DATABASE_PATH = Path("./data/business.db")

CUSTOMERS = [
    (
        1,
        "Zhang Wei",
        "zhang.wei@example.com",
        "13800000001",
        "2026-01-10T09:00:00",
    ),
    (
        2,
        "Li Na",
        "li.na@example.com",
        "13800000002",
        "2026-01-15T10:30:00",
    ),
]

DEVICES = [
    (
        101,
        1,
        "SN-ACME-1001",
        "EdgeBox X1",
        "2025-06-01",
    ),
    (
        102,
        1,
        "SN-ACME-1002",
        "SensorHub S2",
        "2025-09-15",
    ),
    (
        201,
        2,
        "SN-ACME-2001",
        "EdgeBox X1",
        "2025-11-20",
    ),
]

TICKETS = [
    (
        1001,
        101,
        "Power on but no display",
        "The power indicator is on, but the monitor remains black.",
        "resolved",
        "high",
        "2026-03-01T09:00:00",
        "2026-03-02T16:00:00",
    ),
    (
        1002,
        101,
        "Intermittent boot failure",
        "The device sometimes fails to start and requires several attempts.",
        "resolved",
        "medium",
        "2026-04-10T11:00:00",
        "2026-04-11T15:30:00",
    ),
    (
        1003,
        102,
        "Unstable temperature readings",
        "Temperature readings fluctuate significantly during normal operation.",
        "open",
        "medium",
        "2026-08-20T14:00:00",
        None,
    ),
    (
        2001,
        201,
        "No display after firmware update",
        "The device stopped displaying output after a firmware update.",
        "in_progress",
        "urgent",
        "2026-08-25T08:30:00",
        None,
    ),
]

REPAIR_RECORDS = [
    (
        5001,
        1001,
        "The internal display cable was loose.",
        "Reseated and secured the display cable.",
        "Alice Chen",
        "2026-03-02T15:30:00",
    ),
    (
        5002,
        1002,
        "The power adapter supplied unstable voltage.",
        "Replaced the faulty power adapter.",
        "Bob Liu",
        "2026-04-11T15:00:00",
    ),
]


def ensure_tables_exist(connection: sqlite3.Connection) -> None:
    """确认建库脚本已经创建了所需的四张表。"""
    required_tables = {
        "customer",
        "device",
        "ticket",
        "repair_record",
    }

    rows = connection.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
        """
    ).fetchall()

    existing_tables = {row[0] for row in rows}
    missing_tables = required_tables - existing_tables

    if missing_tables:
        missing_names = ", ".join(sorted(missing_tables))
        raise RuntimeError(f"缺少数据表：{missing_names}")


def ensure_tables_are_empty(connection: sqlite3.Connection) -> None:
    """拒绝向已有业务数据的数据库重复写入种子数据。"""
    table_names = (
        "customer",
        "device",
        "ticket",
        "repair_record",
    )

    for table_name in table_names:
        row_count = connection.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]

        if row_count != 0:
            raise RuntimeError(f"数据表 {table_name} 已有 {row_count} 条数据，拒绝重复写入")


def seed_database() -> None:
    """向空的业务数据库写入演示数据。"""
    if not DATABASE_PATH.is_file():
        raise FileNotFoundError(f"业务数据库不存在，请先运行建库脚本：{DATABASE_PATH.resolve()}")

    connection = sqlite3.connect(DATABASE_PATH)

    try:
        connection.execute("PRAGMA foreign_keys = ON")

        ensure_tables_exist(connection)
        ensure_tables_are_empty(connection)

        connection.execute("BEGIN")

        connection.executemany(
            """
            INSERT INTO customer (
                id,
                name,
                email,
                phone,
                created_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            CUSTOMERS,
        )

        connection.executemany(
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
            DEVICES,
        )

        connection.executemany(
            """
            INSERT INTO ticket (
                id,
                device_id,
                title,
                description,
                status,
                priority,
                created_at,
                resolved_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            TICKETS,
        )

        connection.executemany(
            """
            INSERT INTO repair_record (
                id,
                ticket_id,
                diagnosis,
                action_taken,
                technician,
                repaired_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            REPAIR_RECORDS,
        )

        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

    print(f"Seeded customers: {len(CUSTOMERS)}")
    print(f"Seeded devices: {len(DEVICES)}")
    print(f"Seeded tickets: {len(TICKETS)}")
    print(f"Seeded repair records: {len(REPAIR_RECORDS)}")


if __name__ == "__main__":
    seed_database()
