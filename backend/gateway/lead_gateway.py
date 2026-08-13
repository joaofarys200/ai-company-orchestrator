from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Any

DB_PATH = Path("config/leads.sqlite")


class LeadCaptureGateway:
    """Manages real lead acquisition, conversion tracking, and SQLite persistence for economic missions."""

    def __init__(self, db_path: Path | str = DB_PATH):
        self.db_path = Path(db_path)
        self._init_db()

    def _init_db(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS captured_leads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    mission_id TEXT NOT NULL,
                    email TEXT NOT NULL,
                    name TEXT,
                    source TEXT,
                    is_converted INTEGER DEFAULT 0,
                    created_at REAL NOT NULL
                )
                """
            )
            conn.commit()

    def capture_lead(self, mission_id: str, email: str, name: str = "", source: str = "landing_page") -> dict[str, Any]:
        """Records a real lead submission. Rejects invalid emails."""
        email_clean = str(email).strip().lower()
        if not email_clean or "@" not in email_clean or "." not in email_clean:
            raise ValueError(f"Email inválido: '{email}'")

        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO captured_leads (mission_id, email, name, source, is_converted, created_at)
                VALUES (?, ?, ?, ?, 0, ?)
                """,
                (mission_id, email_clean, name, source, time.time()),
            )
            conn.commit()
            lead_id = cur.lastrowid

        return {
            "lead_id": lead_id,
            "mission_id": mission_id,
            "email": email_clean,
            "status": "CAPTURED",
            "timestamp": time.time(),
        }

    def convert_lead(self, mission_id: str, email: str) -> bool:
        """Marks a captured lead as converted upon verified customer action."""
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute(
                "UPDATE captured_leads SET is_converted = 1 WHERE mission_id = ? AND email = ?",
                (mission_id, str(email).strip().lower()),
            )
            conn.commit()
            return cur.rowcount > 0

    def get_mission_stats(self, mission_id: str) -> dict[str, int]:
        """Returns verified total leads and conversions for a given mission."""
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*), SUM(is_converted) FROM captured_leads WHERE mission_id = ?", (mission_id,))
            row = cur.fetchone()
            total_leads = row[0] if row else 0
            conversions = row[1] if (row and row[1] is not None) else 0
            return {"leads_generated": total_leads, "conversions": conversions}


__all__ = ["LeadCaptureGateway"]
