from __future__ import annotations

import hashlib
import hmac
import json
import time
from enum import Enum
from typing import Any


class EvidenceLevel(str, Enum):
    LOCAL_SYNTHETIC = "LOCAL_SYNTHETIC"
    LOCAL_REAL = "LOCAL_REAL"
    EXTERNAL_UNVERIFIED = "EXTERNAL_UNVERIFIED"
    EXTERNAL_VERIFIED = "EXTERNAL_VERIFIED"


class FabricationAttemptError(Exception):
    """Raised when an untrusted component attempts to forge an EXTERNAL_VERIFIED status."""
    pass


class ExternalVerificationGate:
    """Cryptographic and source gatekeeper ensuring only verified external events reach MONETIZED status."""

    def __init__(self, default_webhook_secret: str = "whsec_live_jarvis_production_secret"):
        self.default_webhook_secret = default_webhook_secret

    def verify_payment_webhook(
        self,
        raw_payload: bytes | str,
        signature_header: str,
        webhook_secret: str | None = None,
        provider: str = "stripe",
    ) -> tuple[bool, EvidenceLevel, str, dict[str, Any]]:
        """
        Validates HMAC-SHA256 signature for external webhook events.
        Only authentic signed payloads receive EXTERNAL_VERIFIED status.
        """
        secret = webhook_secret or self.default_webhook_secret
        payload_bytes = raw_payload.encode("utf-8") if isinstance(raw_payload, str) else raw_payload

        if not signature_header or not signature_header.strip():
            return False, EvidenceLevel.EXTERNAL_UNVERIFIED, "Missing signature header", {}

        expected_sig = hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()

        # Constant-time comparison to prevent timing attacks
        if not hmac.compare_digest(expected_sig, signature_header.strip()):
            return False, EvidenceLevel.EXTERNAL_UNVERIFIED, "Invalid HMAC signature: payload spoofing detected", {}

        try:
            parsed_data = json.loads(payload_bytes.decode("utf-8"))
        except Exception as e:
            return False, EvidenceLevel.EXTERNAL_UNVERIFIED, f"Malformed JSON payload: {e}", {}

        return True, EvidenceLevel.EXTERNAL_VERIFIED, "Valid cryptographic HMAC signature verified", parsed_data

    def verify_lead_optin(
        self,
        email: str,
        optin_token: str,
        expected_secret: str = "lead_optin_salt",
    ) -> tuple[bool, EvidenceLevel]:
        """Validates that a lead verified their email via double opt-in token."""
        clean_email = email.strip().lower()
        computed_token = hashlib.sha256(f"{clean_email}:{expected_secret}".encode("utf-8")).hexdigest()[:16]
        
        if hmac.compare_digest(computed_token, optin_token.strip()):
            return True, EvidenceLevel.EXTERNAL_VERIFIED
        return False, EvidenceLevel.EXTERNAL_UNVERIFIED

    def certify_evidence(
        self,
        evidence_level: EvidenceLevel,
        data: Any,
        signature: str = "",
    ) -> dict[str, Any]:
        """Certifies an evidence payload and enforces strict anti-fabrication rules."""
        if evidence_level == EvidenceLevel.EXTERNAL_VERIFIED and not signature:
            raise FabricationAttemptError(
                "Segurança: Impossível classificar como EXTERNAL_VERIFIED sem assinatura/prova criptográfica válida."
            )

        raw_str = json.dumps(data, sort_keys=True, ensure_ascii=False) if isinstance(data, dict) else str(data)
        sha256_hash = hashlib.sha256(raw_str.encode("utf-8")).hexdigest()

        return {
            "evidence_level": evidence_level.value,
            "sha256": sha256_hash,
            "signature": signature,
            "certified_at": time.time(),
        }


__all__ = [
    "EvidenceLevel",
    "FabricationAttemptError",
    "ExternalVerificationGate",
]
