"""
JARVIS OS — Phase 63: Cross-Project Engineering Learning & Verification Transfer
Module: risk.py
Cross-project risk pattern analyzer.
Maps external vulnerability and failure modes to local project surfaces as risk hypotheses.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from .models import EngineeringKnowledgeItem, ProjectFingerprint


class CrossProjectRiskAnalyzer:
    """Analyzes risk patterns transferred across projects and projects them onto local surfaces."""

    KNOWN_RISK_SURFACES = {
        "network_timeout": ["http_client", "websocket", "streaming", "external_api"],
        "concurrency": ["shared_memory", "async_tasks", "threading", "background_workers"],
        "data_drift": ["schema_evolution", "database_migration", "serialization"],
        "security_exfiltration": ["untrusted_input", "env_variables", "file_access"],
        "dynamic_dispatch": ["reflection", "getattr", "eval", "dynamic_import"],
    }

    @classmethod
    def map_risk_to_local_surface(
        cls,
        risk_item: EngineeringKnowledgeItem,
        target_fingerprint: ProjectFingerprint,
    ) -> Dict[str, Any]:
        """Project external risk pattern onto target project's communication and architectural surfaces."""
        pattern = risk_item.pattern
        risk_class = pattern.get("risk_class", "unknown_risk").lower()
        severity = pattern.get("impact_severity", "MEDIUM")

        affected_surfaces: List[str] = []
        target_comms = [c.lower() for c in target_fingerprint.communication_mechanisms]

        # Check surface correlation
        surfaces = cls.KNOWN_RISK_SURFACES.get(risk_class, [])
        for surf in surfaces:
            if any(c in surf for c in target_comms):
                affected_surfaces.append(surf)

        # Check language-specific risks
        if risk_class == "dynamic_dispatch" and "python" in target_fingerprint.languages:
            affected_surfaces.append("python_reflection_boundaries")

        recommended_probes: List[str] = [
            f"probe_boundary_{risk_class}",
            f"stress_test_{risk_class}_resilience",
        ]

        return {
            "source_knowledge_id": risk_item.knowledge_id,
            "risk_class": risk_class,
            "severity": severity,
            "local_surfaces_exposed": affected_surfaces,
            "is_applicable_to_target": len(affected_surfaces) > 0 or risk_class in [r.lower() for r in target_fingerprint.risk_classes],
            "recommended_probes": recommended_probes,
            "mitigation_hint": pattern.get("mitigation_strategy", "Apply defensive retry and validation"),
        }
