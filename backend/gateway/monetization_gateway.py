from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Any

from backend.gateway.verification_gate import EvidenceLevel, ExternalVerificationGate

DB_PATH = Path("config/payments.sqlite")


class MonetizationGateway:
    """Processes revenue events, verifies webhook signatures, and segregates verified from synthetic revenue."""

    def __init__(
        self,
        db_path: Path | str = DB_PATH,
        webhook_secret: str = "whsec_live_jarvis_production_secret",
        verification_gate: ExternalVerificationGate | None = None,
    ):
        self.db_path = Path(db_path)
        self.webhook_secret = webhook_secret
        self.verification_gate = verification_gate or ExternalVerificationGate(self.webhook_secret)
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
                    evidence_level TEXT DEFAULT 'LOCAL_SYNTHETIC',
                    signature TEXT,
                    created_at REAL NOT NULL
                )
                """
            )
            # Add column if table existed previously without it
            cur = conn.cursor()
            cur.execute("PRAGMA table_info(payment_events)")
            columns = [col[1] for col in cur.fetchall()]
            if "evidence_level" not in columns:
                cur.execute("ALTER TABLE payment_events ADD COLUMN evidence_level TEXT DEFAULT 'LOCAL_SYNTHETIC'")
            conn.commit()

    def process_webhook_payment(
        self,
        mission_id: str,
        transaction_id: str,
        amount_usd: float,
        raw_payload: bytes | str,
        signature_header: str,
        customer_email: str = "",
        provider: str = "stripe_checkout",
    ) -> dict[str, Any]:
        """Verifies HMAC signature and records external verified payment."""
        is_valid, level, reason, _ = self.verification_gate.verify_payment_webhook(
            raw_payload=raw_payload,
            signature_header=signature_header,
            webhook_secret=self.webhook_secret,
            provider=provider,
        )

        if not is_valid or level != EvidenceLevel.EXTERNAL_VERIFIED:
            raise ValueError(f"Webhook de pagamento rejeitado: {reason}")

        return self._insert_payment_record(
            mission_id=mission_id,
            transaction_id=transaction_id,
            amount_usd=amount_usd,
            customer_email=customer_email,
            provider=provider,
            evidence_level=EvidenceLevel.EXTERNAL_VERIFIED,
            signature=signature_header,
        )

    def record_synthetic_payment(
        self,
        mission_id: str,
        transaction_id: str,
        amount_usd: float,
        customer_email: str = "synthetic@test.local",
        provider: str = "synthetic_fixture",
    ) -> dict[str, Any]:
        """Records a synthetic/benchmark payment fixture strictly tagged as LOCAL_SYNTHETIC."""
        return self._insert_payment_record(
            mission_id=mission_id,
            transaction_id=transaction_id,
            amount_usd=amount_usd,
            customer_email=customer_email,
            provider=provider,
            evidence_level=EvidenceLevel.LOCAL_SYNTHETIC,
            signature="LOCAL_SYNTHETIC_FIXTURE",
        )

    def _insert_payment_record(
        self,
        mission_id: str,
        transaction_id: str,
        amount_usd: float,
        customer_email: str,
        provider: str,
        evidence_level: EvidenceLevel,
        signature: str,
    ) -> dict[str, Any]:
        if amount_usd <= 0:
            raise ValueError(f"Montante inválido: {amount_usd}. Deve ser superior a $0.00.")

        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO payment_events (mission_id, transaction_id, amount_usd, currency, customer_email, provider, evidence_level, signature, created_at)
                VALUES (?, ?, ?, 'USD', ?, ?, ?, ?, ?)
                """,
                (mission_id, transaction_id, round(amount_usd, 2), customer_email, provider, evidence_level.value, signature, time.time()),
            )
            conn.commit()
            event_id = cur.lastrowid

        return {
            "event_id": event_id,
            "mission_id": mission_id,
            "transaction_id": transaction_id,
            "amount_usd": round(amount_usd, 2),
            "evidence_level": evidence_level.value,
            "status": "RECORDED",
            "timestamp": time.time(),
        }

    def get_verified_revenue(self, mission_id: str) -> float:
        """Returns verified revenue ONLY from EXTERNAL_VERIFIED transactions."""
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT SUM(amount_usd) FROM payment_events WHERE mission_id = ? AND evidence_level = 'EXTERNAL_VERIFIED'",
                (mission_id,),
            )
            row = cur.fetchone()
            return round(row[0], 2) if (row and row[0] is not None) else 0.0

    def get_total_recorded_revenue(self, mission_id: str) -> float:
        """Returns total recorded revenue (including synthetic fixtures) for simulation tests."""
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute("SELECT SUM(amount_usd) FROM payment_events WHERE mission_id = ?", (mission_id,))
            row = cur.fetchone()
            return round(row[0], 2) if (row and row[0] is not None) else 0.0


__all__ = ["MonetizationGateway"]
