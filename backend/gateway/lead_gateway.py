from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Any

from backend.gateway.verification_gate import EvidenceLevel, ExternalVerificationGate

DB_PATH = Path("config/leads.sqlite")


class LeadCaptureGateway:
    """Manages lead acquisition, verification levels, and SQLite persistence for economic missions."""

    def __init__(
        self,
        db_path: Path | str = DB_PATH,
        verification_gate: ExternalVerificationGate | None = None,
    ):
        self.db_path = Path(db_path)
        self.verification_gate = verification_gate or ExternalVerificationGate()
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
                    evidence_level TEXT DEFAULT 'LOCAL_SYNTHETIC',
                    is_converted INTEGER DEFAULT 0,
                    created_at REAL NOT NULL
                )
                """
            )
            # Add column if table existed previously without it
            cur = conn.cursor()
            cur.execute("PRAGMA table_info(captured_leads)")
            columns = [col[1] for col in cur.fetchall()]
            if "evidence_level" not in columns:
                cur.execute("ALTER TABLE captured_leads ADD COLUMN evidence_level TEXT DEFAULT 'LOCAL_SYNTHETIC'")
            conn.commit()

    def capture_lead(
        self,
        mission_id: str,
        email: str,
        name: str = "",
        source: str = "landing_page",
        evidence_level: EvidenceLevel = EvidenceLevel.EXTERNAL_UNVERIFIED,
    ) -> dict[str, Any]:
        """Records a lead submission tagged with its appropriate reality evidence level."""
        email_clean = str(email).strip().lower()
        if not email_clean or "@" not in email_clean or "." not in email_clean:
            raise ValueError(f"Email inválido: '{email}'")

        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO captured_leads (mission_id, email, name, source, evidence_level, is_converted, created_at)
                VALUES (?, ?, ?, ?, ?, 0, ?)
                """,
                (mission_id, email_clean, name, source, evidence_level.value, time.time()),
            )
            conn.commit()
            lead_id = cur.lastrowid

        return {
            "lead_id": lead_id,
            "mission_id": mission_id,
            "email": email_clean,
            "evidence_level": evidence_level.value,
            "status": "CAPTURED",
            "timestamp": time.time(),
        }

    def verify_lead_double_optin(self, mission_id: str, email: str, optin_token: str) -> bool:
        """Verifies lead double opt-in token and elevates level to EXTERNAL_VERIFIED."""
        is_valid, level = self.verification_gate.verify_lead_optin(email, optin_token)
        if not is_valid:
            return False

        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute(
                "UPDATE captured_leads SET evidence_level = ?, is_converted = 1 WHERE mission_id = ? AND email = ?",
                (level.value, mission_id, str(email).strip().lower()),
            )
            conn.commit()
            return cur.rowcount > 0

    def get_mission_stats(self, mission_id: str) -> dict[str, Any]:
        """Returns total leads, verified leads, and conversions."""
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT 
                    COUNT(*),
                    SUM(CASE WHEN evidence_level = 'EXTERNAL_VERIFIED' THEN 1 ELSE 0 END),
                    SUM(is_converted)
                FROM captured_leads 
                WHERE mission_id = ?
                """,
                (mission_id,),
            )
            row = cur.fetchone()
            total_leads = row[0] if row else 0
            verified_leads = row[1] if (row and row[1] is not None) else 0
            conversions = row[2] if (row and row[2] is not None) else 0
            return {
                "leads_generated": total_leads,
                "verified_leads": verified_leads,
                "conversions": conversions,
            }


__all__ = ["LeadCaptureGateway"]
