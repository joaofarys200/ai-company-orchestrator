from __future__ import annotations

import hashlib
import json
import time
from typing import Any


class EvidenceGateway:
    """Collects and certifies evidence artifacts for economic mission transitions."""

    @staticmethod
    def create_evidence_package(
        stage: str,
        title: str,
        payload: dict[str, Any] | str,
        source: str = "gateway",
    ) -> dict[str, Any]:
        """Generates a certified evidence dictionary with SHA-256 fingerprint."""
        raw_str = json.dumps(payload, sort_keys=True, ensure_ascii=False) if isinstance(payload, dict) else str(payload)
        sha256 = hashlib.sha256(raw_str.encode("utf-8")).hexdigest()
        
        return {
            "stage": stage,
            "title": title,
            "source": source,
            "sha256": sha256,
            "bytes_count": len(raw_str.encode("utf-8")),
            "timestamp": time.time(),
        }


__all__ = ["EvidenceGateway"]
