import sqlite3
from pathlib import Path

DATABASE_PATH = Path("./data/business.db")


def get_customer_tickets(customer_id: int) -> list[tuple]:
    """查询一个客户的全部工单及每张工单的维修记录数量。"""
    connection = sqlite3.connect(DATABASE_PATH)

    try:
        rows = connection.execute(
            """
            SELECT
                c.name,
                d.serial_number,
                t.id,
                t.title,
                t.status,
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
                c.name,
                d.serial_number,
                t.id,
                t.title,
                t.status
            ORDER BY t.id
            """,
            (customer_id,),
        ).fetchall()

        return rows
    finally:
        connection.close()


def get_device_repair_count(serial_number: str) -> int:
    """根据设备序列号统计设备的维修记录总数。"""
    connection = sqlite3.connect(DATABASE_PATH)

    try:
        row = connection.execute(
            """
            SELECT
                d.id,
                COUNT(r.id) AS repair_count
            FROM device AS d
            LEFT JOIN ticket AS t
                ON t.device_id = d.id
            LEFT JOIN repair_record AS r
                ON r.ticket_id = t.id
            WHERE d.serial_number = ?
            GROUP BY d.id
            """,
            (serial_number,),
        ).fetchone()

        if row is None:
            raise ValueError(f"没有找到设备：{serial_number}")

        return row[1]
    finally:
        connection.close()


if __name__ == "__main__":
    tickets = get_customer_tickets(customer_id=1)

    print(f"ticket_count: {len(tickets)}")

    for ticket in tickets:
        (
            customer_name,
            serial_number,
            ticket_id,
            title,
            status,
            repair_count,
        ) = ticket

        print(
            f"customer={customer_name}, "
            f"device={serial_number}, "
            f"ticket_id={ticket_id}, "
            f"title={title}, "
            f"status={status}, "
            f"repair_count={repair_count}"
        )

    repair_count = get_device_repair_count("SN-ACME-1001")
    print(f"device_repair_count: {repair_count}")
