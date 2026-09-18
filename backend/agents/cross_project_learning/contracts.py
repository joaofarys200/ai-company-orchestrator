"""
JARVIS OS — Phase 63: Cross-Project Engineering Learning & Verification Transfer
Module: contracts.py
Cross-project contract pattern adapter.
Translates OpenAPI, JSON Schema, WebSocket, and type contracts without transferring unvalidated invariants.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from .models import EngineeringKnowledgeItem, ProjectFingerprint


class CrossProjectContractAdapter:
    """Adapts external contract patterns into local contract verification hypotheses."""

    @classmethod
    def adapt_contract_pattern(
        cls,
        contract_item: EngineeringKnowledgeItem,
        target_fingerprint: ProjectFingerprint,
    ) -> Dict[str, Any]:
        """Convert external contract knowledge into local target schema expectations."""
        pattern = contract_item.pattern
        protocol = pattern.get("protocol", "http_rest").lower()
        schema_format = pattern.get("schema_format", "json_schema").lower()
        compatibility_rule = pattern.get("compatibility_rule", "backward_compatible")

        is_protocol_supported = protocol in [c.lower() for c in target_fingerprint.communication_mechanisms] or (
            protocol == "http_rest" and any("http" in c for c in target_fingerprint.communication_mechanisms)
        )

        return {
            "source_knowledge_id": contract_item.knowledge_id,
            "target_project_id": target_fingerprint.project_id,
            "protocol": protocol,
            "schema_format": schema_format,
            "is_protocol_supported": is_protocol_supported,
            "target_compatibility_rule": compatibility_rule,
            "drift_mitigation": pattern.get("drift_mitigation", "Strict schema validation gate"),
            "local_hypothesis": (
                f"Verify target endpoints using {protocol} conform to {compatibility_rule} invariants "
                f"via local contract discovery (Phase 45/46)"
            ),
        }
