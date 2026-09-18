"""
JARVIS OS — Phase 64: Autonomous Architecture Evolution & Design Governance
Module: observation.py
Architectural observer identifying structural complexity, coupling patterns,
SCC bottlenecks, contract concentration, boundary violations, and change propagation.

Rule:
    Never classify an architectural smell as a bug automatically.
    Use OBSERVED, SUSPECTED, CONFIRMED_WITHIN_SCOPE, UNKNOWN.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Set, Tuple

from .models import (
    ArchitectureSnapshot,
    ObservationStatus,
    ProblemCategory,
    ProblemSeverity,
)


class ArchitectureObserver:
    """Observes and analyzes structural properties of an ArchitectureSnapshot."""

    def __init__(self, coupling_fanout_threshold: int = 8, scc_size_threshold: int = 3):
        self.coupling_fanout_threshold = coupling_fanout_threshold
        self.scc_size_threshold = scc_size_threshold

    def observe(self, snapshot: ArchitectureSnapshot) -> List[Dict[str, Any]]:
        """Run all observation passes on the snapshot and return detected smell candidates."""
        observations: List[Dict[str, Any]] = []

        # 1. High Coupling & Excessive Fan-Out
        observations.extend(self._observe_coupling(snapshot))

        # 2. Large Strongly Connected Components (SCCs) & Cycles
        observations.extend(self._observe_sccs(snapshot))

        # 3. Contract Concentration & Monolithic Hubs
        observations.extend(self._observe_contract_concentration(snapshot))

        # 4. Layer Violations & Boundary Leaks
        observations.extend(self._observe_boundary_violations(snapshot))

        # 5. Dynamic Boundaries & Hidden Consumers
        observations.extend(self._observe_dynamic_boundaries(snapshot))

        # 6. Low Testability Surfaces
        observations.extend(self._observe_testability(snapshot))

        # 7. Persistence & Database Coupling
        observations.extend(self._observe_persistence_coupling(snapshot))

        # 8. UI / Backend Direct Coupling
        observations.extend(self._observe_ui_backend_coupling(snapshot))

        return observations

    def _observe_coupling(self, snapshot: ArchitectureSnapshot) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        fan_out_map: Dict[str, Set[str]] = {}
        fan_in_map: Dict[str, Set[str]] = {}

        for src, dst in snapshot.dependencies:
            fan_out_map.setdefault(src, set()).add(dst)
            fan_in_map.setdefault(dst, set()).add(src)

        for node, targets in fan_out_map.items():
            if len(targets) >= self.coupling_fanout_threshold:
                results.append({
                    "smell_type": "excessive_fan_out",
                    "category": ProblemCategory.COUPLING,
                    "target_node": node,
                    "affected_nodes": [node] + sorted(list(targets)),
                    "evidence": {
                        "fan_out_count": len(targets),
                        "threshold": self.coupling_fanout_threshold,
                        "targets_sample": sorted(list(targets))[:5],
                    },
                    "status": ObservationStatus.CONFIRMED_WITHIN_SCOPE,
                    "severity": ProblemSeverity.HIGH if len(targets) > 15 else ProblemSeverity.MEDIUM,
                    "confidence": 0.95,
                    "description": f"Node '{node}' has high fan-out coupling ({len(targets)} dependencies).",
                })

        for node, callers in fan_in_map.items():
            if len(callers) >= 12:
                results.append({
                    "smell_type": "high_fan_in_hub",
                    "category": ProblemCategory.MAINTAINABILITY,
                    "target_node": node,
                    "affected_nodes": [node] + sorted(list(callers))[:8],
                    "evidence": {
                        "fan_in_count": len(callers),
                        "callers_sample": sorted(list(callers))[:5],
                    },
                    "status": ObservationStatus.OBSERVED,
                    "severity": ProblemSeverity.MEDIUM,
                    "confidence": 0.90,
                    "description": f"Node '{node}' is a central fan-in hub with {len(callers)} incoming dependants.",
                })

        return results

    def _observe_sccs(self, snapshot: ArchitectureSnapshot) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        for scc in snapshot.sccs:
            if len(scc) >= self.scc_size_threshold:
                results.append({
                    "smell_type": "large_scc_cycle",
                    "category": ProblemCategory.SCC,
                    "target_node": scc[0],
                    "affected_nodes": sorted(scc),
                    "evidence": {
                        "scc_size": len(scc),
                        "members": sorted(scc),
                    },
                    "status": ObservationStatus.CONFIRMED_WITHIN_SCOPE,
                    "severity": ProblemSeverity.HIGH if len(scc) >= 5 else ProblemSeverity.MEDIUM,
                    "confidence": 0.98,
                    "description": f"Strongly Connected Component of size {len(scc)} creates a cyclic coupling loop.",
                })
        return results

    def _observe_contract_concentration(self, snapshot: ArchitectureSnapshot) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        for contract, consumers in snapshot.consumers.items():
            if len(consumers) >= 6:
                results.append({
                    "smell_type": "contract_concentration",
                    "category": ProblemCategory.CONTRACT,
                    "target_node": contract,
                    "affected_nodes": [contract] + sorted(consumers),
                    "evidence": {
                        "consumer_count": len(consumers),
                        "consumers": sorted(consumers),
                    },
                    "status": ObservationStatus.CONFIRMED_WITHIN_SCOPE,
                    "severity": ProblemSeverity.MEDIUM,
                    "confidence": 0.92,
                    "description": f"Contract '{contract}' is concentrated across {len(consumers)} consumers, risking cascading breaks.",
                })
        return results

    def _observe_boundary_violations(self, snapshot: ArchitectureSnapshot) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        for src, dst in snapshot.dependencies:
            # Check for layer violation: e.g. backend depending on frontend or presentation
            src_lower = src.lower()
            dst_lower = dst.lower()
            if "backend" in src_lower and "frontend" in dst_lower:
                results.append({
                    "smell_type": "layer_inversion_violation",
                    "category": ProblemCategory.BOUNDARY,
                    "target_node": src,
                    "affected_nodes": [src, dst],
                    "evidence": {"src": src, "dst": dst},
                    "status": ObservationStatus.CONFIRMED_WITHIN_SCOPE,
                    "severity": ProblemSeverity.CRITICAL,
                    "confidence": 0.99,
                    "description": f"Layer inversion: backend component '{src}' directly imports frontend '{dst}'.",
                })
        return results

    def _observe_dynamic_boundaries(self, snapshot: ArchitectureSnapshot) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        for boundary in snapshot.external_boundaries:
            if any(term in boundary.lower() for term in ["eval", "getattr", "dynamic", "reflection"]):
                results.append({
                    "smell_type": "dynamic_reflection_boundary",
                    "category": ProblemCategory.SECURITY,
                    "target_node": boundary,
                    "affected_nodes": [boundary],
                    "evidence": {"boundary": boundary},
                    "status": ObservationStatus.SUSPECTED,
                    "severity": ProblemSeverity.HIGH,
                    "confidence": 0.85,
                    "description": f"Dynamic reflection boundary detected at '{boundary}', hindering static verification.",
                })
        return results

    def _observe_testability(self, snapshot: ArchitectureSnapshot) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        if len(snapshot.symbols) > 20 and len(snapshot.test_surfaces) == 0:
            results.append({
                "smell_type": "low_testability_coverage",
                "category": ProblemCategory.TESTABILITY,
                "target_node": snapshot.snapshot_id,
                "affected_nodes": snapshot.symbols[:10],
                "evidence": {
                    "symbol_count": len(snapshot.symbols),
                    "test_surface_count": len(snapshot.test_surfaces),
                },
                "status": ObservationStatus.OBSERVED,
                "severity": ProblemSeverity.HIGH,
                "confidence": 0.90,
                "description": "Module contains substantial symbol declarations without declared test surfaces.",
            })
        return results

    def _observe_persistence_coupling(self, snapshot: ArchitectureSnapshot) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        table_accessors: Dict[str, Set[str]] = {}
        for edge in snapshot.persistence_edges:
            table = edge.get("table") or edge.get("target") or "default_store"
            src = edge.get("source") or "unknown_service"
            table_accessors.setdefault(table, set()).add(src)

        for table, services in table_accessors.items():
            if len(services) >= 2:
                results.append({
                    "smell_type": "shared_database_coupling",
                    "category": ProblemCategory.COUPLING,
                    "target_node": table,
                    "affected_nodes": sorted(list(services)) + [table],
                    "evidence": {
                        "table": table,
                        "services": sorted(list(services)),
                    },
                    "status": ObservationStatus.CONFIRMED_WITHIN_SCOPE,
                    "severity": ProblemSeverity.MEDIUM,
                    "confidence": 0.94,
                    "description": f"Shared persistence table '{table}' is directly accessed by multiple services: {sorted(list(services))}.",
                })
        return results

    def _observe_ui_backend_coupling(self, snapshot: ArchitectureSnapshot) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        for edge in snapshot.communication_edges:
            if edge.get("type") == "tight_sync_rpc" and "ui" in str(edge.get("source", "")).lower():
                results.append({
                    "smell_type": "tight_ui_backend_coupling",
                    "category": ProblemCategory.RELIABILITY,
                    "target_node": edge.get("source", "ui"),
                    "affected_nodes": [edge.get("source", "ui"), edge.get("target", "backend")],
                    "evidence": edge,
                    "status": ObservationStatus.OBSERVED,
                    "severity": ProblemSeverity.MEDIUM,
                    "confidence": 0.88,
                    "description": f"UI component directly bound via synchronous tight coupling to backend.",
                })
        return results
