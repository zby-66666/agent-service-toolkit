import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BUSINESS_DATABASE_PATH = PROJECT_ROOT / "data" / "business.db"


def connect_business_db() -> sqlite3.Connection:
    """连接本地业务数据库。"""
    if not BUSINESS_DATABASE_PATH.is_file():
        raise FileNotFoundError(f"业务数据库不存在：{BUSINESS_DATABASE_PATH}")

    connection = sqlite3.connect(BUSINESS_DATABASE_PATH)
    connection.execute("PRAGMA foreign_keys = ON")
    connection.row_factory = sqlite3.Row

    return connection


def get_customer_tickets(
    customer_id: int,
) -> list[dict[str, object]]:
    """查询一个客户的全部工单及每张工单的维修记录数量。"""
    if customer_id <= 0:
        raise ValueError("customer_id 必须是正整数")

    connection = connect_business_db()

    try:
        rows = connection.execute(
            """
            SELECT
                c.id AS customer_id,
                c.name AS customer_name,
                d.id AS device_id,
                d.serial_number,
                d.model AS device_model,
                t.id AS ticket_id,
                t.title,
                t.description,
                t.status,
                t.priority,
                t.created_at,
                t.resolved_at,
                COUNT(r.id) AS repair_count
            FROM customer AS c
            JOIN device AS d
                ON d.customer_id = c.id
            JOIN ticket AS t
                ON t.device_id = d.id
            LEFT JOIN repair_record AS r
                ON r.ticket_id = t.id
            WHERE c.id = ?
            GROUP BY
                c.id,
                c.name,
                d.id,
                d.serial_number,
                d.model,
                t.id,
                t.title,
                t.description,
                t.status,
                t.priority,
                t.created_at,
                t.resolved_at
            ORDER BY t.created_at
            """,
            (customer_id,),
        ).fetchall()

        return [dict(row) for row in rows]
    finally:
        connection.close()


def get_device_repair_history(
    serial_number: str,
) -> list[dict[str, object]]:
    """查询一台设备的工单和维修历史。"""
    serial_number = serial_number.strip()

    if not serial_number:
        raise ValueError("serial_number 不能为空")

    connection = connect_business_db()

    try:
        rows = connection.execute(
            """
            SELECT
                d.id AS device_id,
                d.serial_number,
                d.model AS device_model,
                c.id AS customer_id,
                c.name AS customer_name,
                t.id AS ticket_id,
                t.title,
                t.description,
                t.status,
                t.priority,
                t.created_at,
                t.resolved_at,
                r.id AS repair_record_id,
                r.diagnosis,
                r.action_taken,
                r.technician,
                r.repaired_at
            FROM device AS d
            JOIN customer AS c
                ON c.id = d.customer_id
            LEFT JOIN ticket AS t
                ON t.device_id = d.id
            LEFT JOIN repair_record AS r
                ON r.ticket_id = t.id
            WHERE d.serial_number = ?
            ORDER BY
                t.created_at,
                r.repaired_at
            """,
            (serial_number,),
        ).fetchall()

        return [dict(row) for row in rows]
    finally:
        connection.close()
