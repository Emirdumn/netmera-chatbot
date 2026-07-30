"""Rotate all staff login hashes to the current STAFF_DEMO_PASSWORD.

Usage:
    STAFF_DEMO_PASSWORD='new-strong-password' python scripts/rotate_staff_passwords.py

This intentionally does not print the password or any hash.
"""
import sys
from pathlib import Path

if __name__ == "__main__" and not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import STAFF_DEMO_PASSWORD
from storage import repository as repo
from storage.db import get_connection


def main():
    repo.init_db()
    conn = get_connection()
    rows = conn.execute("SELECT id FROM staff").fetchall()
    for row in rows:
        conn.execute(
            "UPDATE staff SET password_hash = ? WHERE id = ?",
            (repo.hash_staff_password(row["id"], STAFF_DEMO_PASSWORD), row["id"]),
        )
    conn.commit()
    print(f"Rotated password hashes for {len(rows)} staff users.")


if __name__ == "__main__":
    main()
