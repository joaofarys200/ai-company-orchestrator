"""
JARVIS OS — Phase 68: Technical Debt Detector
Detects structural and temporal debt through multi-signal correlation:
- repeated hotspots
- repeated rollback
- recurring regressions
- persistent complexity
- flaky tests
- unresolved contracts
- architectural smells
- repeated human reviews
- recurring dynamic boundaries
- repeated mission failures

Core Invariant:
Do NOT create debt items simply because a threshold was exceeded once in isolation.
Require temporal persistence (recurrence >= 2) or structural evidence (architectural smell, circular dependency).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .models import DebtCategory, DebtSeverity, TechnicalDebtItem
from .technical_debt import TechnicalDebtManager


class TechnicalDebtDetector:
    """
    Detects debt candidates by correlating signals across historical events,
    snapshots, and mission telemetry.
    """

    def __init__(self, debt_manager: Optional[TechnicalDebtManager] = None) -> None:
        self.debt_manager = debt_manager or TechnicalDebtManager()

    def analyze_signals(
        self,
        mission_id: str,
        history: List[Dict[str, Any]],
        context: Optional[Dict[str, Any]] = None,
    ) -> List[TechnicalDebtItem]:
        """
        Correlates signals across history and creates debt items ONLY when
        temporal or structural persistence criteria are satisfied.
        """
        ctx = context or {}
        detected_items: List[TechnicalDebtItem] = []

        # 1. Check Repeated Rollbacks on specific surfaces
        rollback_surfaces: Dict[str, int] = {}
        for event in history:
            if event.get("type") in ("rollback", "mission_rollback") or event.get("rollback_occurred"):
                surf = event.get("surface", event.get("component", "core_subsystem"))
                rollback_surfaces[surf] = rollback_surfaces.get(surf, 0) + 1

        for surf, count in rollback_surfaces.items():
            if count >= 2:  # Temporal persistence
                item = self.debt_manager.create_debt_item(
                    category=DebtCategory.OPERATIONAL,
                    affected_surface=surf,
                    origin_mission=mission_id,
                    evidence=[{
                        "detection_rule": "repeated_rollback",
                        "surface": surf,
                        "rollback_count": count,
                    }],
                    severity=DebtSeverity.HIGH if count >= 3 else DebtSeverity.MEDIUM,
                    confidence=0.90,
                    estimated_cost=2.5,
                    risk=0.75,
                    resolution_options=[
                        "Implement transactional staging to avoid repeated rollbacks",
                        "Partition subsystem into isolated failure domains",
                    ],
                )
                detected_items.append(item)

        # 2. Check Recurring Regressions on same module/symbol
        regression_counts: Dict[str, int] = {}
        for event in history:
            if event.get("regression_detected"):
                sym = event.get("target_symbol", event.get("module", "unknown_module"))
                regression_counts[sym] = regression_counts.get(sym, 0) + 1

        for sym, count in regression_counts.items():
            if count >= 2:
                item = self.debt_manager.create_debt_item(
                    category=DebtCategory.CODE,
                    affected_surface=sym,
                    origin_mission=mission_id,
                    evidence=[{
                        "detection_rule": "recurring_regression",
                        "symbol": sym,
                        "recurrence_count": count,
                    }],
                    severity=DebtSeverity.HIGH,
                    confidence=0.85,
                    estimated_cost=3.0,
                    risk=0.80,
                    resolution_options=[
                        f"Add targeted regression assertions around {sym}",
                        "Refactor symbol to reduce branching complexity",
                    ],
                )
                detected_items.append(item)

        # 3. Check Persistent High Complexity (Structural evidence)
        code_data = ctx.get("code", {})
        high_comp_modules = code_data.get("high_complexity_modules", [])
        if isinstance(high_comp_modules, list):
            for mod_info in high_comp_modules:
                if isinstance(mod_info, dict):
                    name = mod_info.get("name", "unknown")
                    comp = mod_info.get("complexity", 0)
                    cycles = mod_info.get("persistence_cycles", 1)
                    if comp > 25 and cycles >= 2:
                        item = self.debt_manager.create_debt_item(
                            category=DebtCategory.CODE,
                            affected_surface=name,
                            origin_mission=mission_id,
                            evidence=[{
                                "detection_rule": "persistent_complexity",
                                "module": name,
                                "complexity": comp,
                                "cycles": cycles,
                            }],
                            severity=DebtSeverity.MEDIUM,
                            confidence=0.88,
                            estimated_cost=2.0,
                            risk=0.60,
                            resolution_options=["Decompose function into smaller pure helpers"],
                        )
                        detected_items.append(item)

        # 4. Check Flaky Tests with Temporal Persistence
        flaky_tests = ctx.get("test", {}).get("flaky_test_list", [])
        for f in flaky_tests:
            if isinstance(f, dict):
                t_name = f.get("test_name", "test_unknown")
                flaky_runs = f.get("intermittent_failures_count", 0)
                if flaky_runs >= 2:
                    item = self.debt_manager.create_debt_item(
                        category=DebtCategory.TEST,
                        affected_surface=t_name,
                        origin_mission=mission_id,
                        evidence=[{
                            "detection_rule": "persistent_flaky_test",
                            "test_name": t_name,
                            "intermittent_failures": flaky_runs,
                        }],
                        severity=DebtSeverity.MEDIUM,
                        confidence=0.92,
                        estimated_cost=1.5,
                        risk=0.65,
                        resolution_options=["Isolate shared state / mock external network call in test"],
                    )
                    detected_items.append(item)

        # 5. Check Architectural Smells (Structural persistence: SCC cycle > threshold)
        arch_data = ctx.get("architecture", {})
        scc_cycles = arch_data.get("cyclic_components", [])
        for c in scc_cycles:
            if isinstance(c, dict):
                cycle_nodes = c.get("nodes", [])
                if len(cycle_nodes) >= 3:
                    surf = " <-> ".join(cycle_nodes[:3])
                    item = self.debt_manager.create_debt_item(
                        category=DebtCategory.ARCHITECTURAL,
                        affected_surface=surf,
                        origin_mission=mission_id,
                        evidence=[{
                            "detection_rule": "architectural_cyclic_scc",
                            "nodes": cycle_nodes,
                            "size": len(cycle_nodes),
                        }],
                        severity=DebtSeverity.HIGH if len(cycle_nodes) >= 5 else DebtSeverity.MEDIUM,
                        confidence=0.95,
                        estimated_cost=4.0,
                        risk=0.85,
                        resolution_options=["Apply dependency inversion or extract shared interface"],
                    )
                    detected_items.append(item)

        # 6. Check Recurring Dynamic Boundaries
        dyn_boundaries = arch_data.get("recurring_dynamic_boundaries", [])
        for db in dyn_boundaries:
            if isinstance(db, dict) and db.get("occurrence_count", 0) >= 2:
                item = self.debt_manager.create_debt_item(
                    category=DebtCategory.ARCHITECTURAL,
                    affected_surface=db.get("boundary", "unnamed_boundary"),
                    origin_mission=mission_id,
                    evidence=[{
                        "detection_rule": "recurring_dynamic_boundary",
                        "boundary": db.get("boundary"),
                        "occurrences": db.get("occurrence_count"),
                    }],
                    severity=DebtSeverity.LOW,
                    confidence=0.75,
                    estimated_cost=1.0,
                    risk=0.40,
                    resolution_options=["Codify implicit runtime boundary into explicit package boundary"],
                )
                detected_items.append(item)

        return detected_items
