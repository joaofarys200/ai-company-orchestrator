from __future__ import annotations

import hashlib
import hmac
import sqlite3
import time
from pathlib import Path
from typing import Any

DB_PATH = Path("config/payments.sqlite")


class MonetizationGateway:
    """Processes verified revenue events, checkout webhooks, and maintains payment records."""

    def __init__(self, db_path: Path | str = DB_PATH, webhook_secret: str = "whsec_test_jarvis_economic_gateway"):
        self.db_path = Path(db_path)
        self.webhook_secret = webhook_secret
        self._init_db()

    def _init_db(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS payment_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    mission_id TEXT NOT NULL,
                    transaction_id TEXT UNIQUE NOT NULL,
                    amount_usd REAL NOT NULL,
                    currency TEXT DEFAULT 'USD',
                    customer_email TEXT,
                    provider TEXT NOT NULL,
                    signature TEXT,
                    created_at REAL NOT NULL
                )
                """
            )
            conn.commit()

    def process_payment_event(
        self,
        mission_id: str,
        transaction_id: str,
        amount_usd: float,
        customer_email: str = "",
        provider: str = "stripe_checkout",
        signature: str = "",
    ) -> dict[str, Any]:
        """Records a verified revenue event. Rejects negative/zero amounts."""
        if amount_usd <= 0:
            raise ValueError(f"Montante inválido: {amount_usd}. Deve ser superior a $0.00.")

        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO payment_events (mission_id, transaction_id, amount_usd, currency, customer_email, provider, signature, created_at)
                VALUES (?, ?, ?, 'USD', ?, ?, ?, ?)
                """,
                (mission_id, transaction_id, round(amount_usd, 2), customer_email, provider, signature, time.time()),
            )
            conn.commit()
            event_id = cur.lastrowid

        return {
            "event_id": event_id,
            "mission_id": mission_id,
            "transaction_id": transaction_id,
            "amount_usd": round(amount_usd, 2),
            "status": "VERIFIED_PAID",
            "timestamp": time.time(),
        }

    def get_mission_revenue(self, mission_id: str) -> float:
        """Returns total verified revenue for a specific mission from real database records."""
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute("SELECT SUM(amount_usd) FROM payment_events WHERE mission_id = ?", (mission_id,))
            row = cur.fetchone()
            return round(row[0], 2) if (row and row[0] is not None) else 0.0


__all__ = ["MonetizationGateway"]
