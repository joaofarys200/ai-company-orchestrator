"""
JARVIS OS — Phase 69: Autonomous Quality Debt Remediation
Debt ingestion, validation preprocessing, and sanitization.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class IngestedDebtItem:
    debt_id: str
    category: str
    severity: str
    affected_surface: str
    evidence: Dict[str, Any]
    confidence: float
    recurrence: int
    age_days: float
    origin: str
    dependencies: List[str] = field(default_factory=list)
    description: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    ingested_at: float = field(default_factory=time.time)

    def content_hash(self) -> str:
        payload = {
            "debt_id": self.debt_id,
            "category": self.category,
            "severity": self.severity,
            "affected_surface": self.affected_surface,
            "evidence": self.evidence,
        }
        raw = json.dumps(payload, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class DebtIngestionEngine:
    """
    Ingests TechnicalDebtItem instances from Phase 68 or raw dictionaries.
    Validates mandatory fields and rejects UNKNOWN or malformed items
    without passing them through debt validation.
    """

    MANDATORY_FIELDS = [
        "debt_id",
        "category",
        "severity",
        "affected_surface",
    ]

    def ingest(self, raw_item: Any) -> IngestedDebtItem:
        if hasattr(raw_item, "to_dict"):
            data = raw_item.to_dict()
        elif isinstance(raw_item, dict):
            data = dict(raw_item)
        else:
            raise ValueError(f"Unsupported debt item format: {type(raw_item)}")

        # Check mandatory fields
        for f in self.MANDATORY_FIELDS:
            if f not in data or data[f] is None:
                raise ValueError(f"Missing mandatory debt field: {f}")

        debt_id = str(data["debt_id"]).strip()
        category = str(data["category"]).strip().upper()
        severity = str(data["severity"]).strip().upper()
        affected_surface = str(data["affected_surface"]).strip()
        
        evidence = data.get("evidence", {})
        if not isinstance(evidence, dict):
            evidence = {"raw_evidence": evidence}

        confidence = float(data.get("confidence", 0.8))
        recurrence = int(data.get("recurrence", 1))
        age_days = float(data.get("age_days", data.get("age", 1.0)))
        origin = str(data.get("origin", "phase68_governance"))
        dependencies = list(data.get("dependencies", []))
        description = str(data.get("description", ""))
        metadata = dict(data.get("metadata", {}))

        return IngestedDebtItem(
            debt_id=debt_id,
            category=category,
            severity=severity,
            affected_surface=affected_surface,
            evidence=evidence,
            confidence=confidence,
            recurrence=recurrence,
            age_days=age_days,
            origin=origin,
            dependencies=dependencies,
            description=description,
            metadata=metadata,
        )

    def ingest_batch(self, raw_items: List[Any]) -> List[IngestedDebtItem]:
        return [self.ingest(item) for item in raw_items]
