import sys
from pathlib import Path

# Ensure project backend root is on sys.path
BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.database import engine
from app.config import settings
from sqlmodel import text


def column_exists_sqlite(conn, table: str, column: str) -> bool:
    result = conn.exec_driver_sql(f"PRAGMA table_info('{table}')")
    for _cid, name, _type, _notnull, _dflt, _pk in result.fetchall():
        if name == column:
            return True
    return False


def main():
    url = settings.database_url or ""
    print(f"Database URL: {url}")
    with engine.connect() as conn:
        if url.startswith("sqlite"):
            if column_exists_sqlite(conn, "expenses", "receipt_path"):
                print("Column 'receipt_path' already exists on 'expenses'. Nothing to do.")
                return
            print("Adding column 'receipt_path' to 'expenses' (SQLite)...")
            conn.exec_driver_sql("ALTER TABLE expenses ADD COLUMN receipt_path TEXT;")
            print("Done.")
        else:
            # Generic SQL for Postgres-like engines
            print("Adding column 'receipt_path' to 'expenses' (non-SQLite)...")
            conn.execute(text("""
                ALTER TABLE IF EXISTS expenses
                ADD COLUMN IF NOT EXISTS receipt_path TEXT
            """))
            print("Done.")


if __name__ == "__main__":
    main()
