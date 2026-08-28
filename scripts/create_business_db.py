import sqlite3
from pathlib import Path

DATABASE_PATH = Path("./data/business.db")


SCHEMA_SQL = """
CREATE TABLE customer (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    phone TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE device (
    id INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL,
    serial_number TEXT NOT NULL UNIQUE,
    model TEXT NOT NULL,
    purchase_date TEXT,
    FOREIGN KEY (customer_id)
        REFERENCES customer(id)
        ON DELETE RESTRICT
);

CREATE TABLE ticket (
    id INTEGER PRIMARY KEY,
    device_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    status TEXT NOT NULL
        CHECK (status IN ('open', 'in_progress', 'resolved', 'closed')),
    priority TEXT NOT NULL
        CHECK (priority IN ('low', 'medium', 'high', 'urgent')),
    created_at TEXT NOT NULL,
    resolved_at TEXT,
    FOREIGN KEY (device_id)
        REFERENCES device(id)
        ON DELETE RESTRICT
);

CREATE TABLE repair_record (
    id INTEGER PRIMARY KEY,
    ticket_id INTEGER NOT NULL,
    diagnosis TEXT NOT NULL,
    action_taken TEXT NOT NULL,
    technician TEXT NOT NULL,
    repaired_at TEXT NOT NULL,
    FOREIGN KEY (ticket_id)
        REFERENCES ticket(id)
        ON DELETE RESTRICT
);

CREATE INDEX idx_device_customer_id
    ON device(customer_id);

CREATE INDEX idx_ticket_device_id
    ON ticket(device_id);

CREATE INDEX idx_repair_record_ticket_id
    ON repair_record(ticket_id);
"""


def create_database() -> None:
    """创建新的业务数据库和业务表。"""
    if DATABASE_PATH.exists():
        raise FileExistsError(f"数据库已经存在，拒绝覆盖：{DATABASE_PATH.resolve()}")

    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(DATABASE_PATH)

    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executescript(SCHEMA_SQL)
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

    print(f"Business database created: {DATABASE_PATH.resolve()}")


if __name__ == "__main__":
    create_database()
