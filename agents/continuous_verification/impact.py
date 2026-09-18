"""
JARVIS OS — Phase 62: Continuous Verification & Autonomous Regression Governance
Module: impact.py
Impact-to-Verification Planning integrating F60 Symbol-Fine-Grained Graph & SCC Condensation.
Transforms ChangeSets into comprehensive VerificationSurfaces.
"""

from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional, Set

from .models import ChangeItem, ChangeSet, ChangeType, VerificationSurface

try:
    from backend.agents.symbol_fine_grained_graph.bridge import SymbolFineGrainedGraphBridge
except ImportError:
    try:
        from agents.symbol_fine_grained_graph.bridge import SymbolFineGrainedGraphBridge
    except ImportError:
        SymbolFineGrainedGraphBridge = None  # type: ignore


class ImpactToVerificationPlanner:
    """
    Transforms a ChangeSet into a VerificationSurface:
    CHANGE -> FILE IMPACT -> SYMBOL IMPACT -> SCC IMPACT -> CONSUMER IMPACT
           -> CONTRACT IMPACT -> BEHAVIOR IMPACT -> RISK IMPACT

    Rule: Never assume empty impact just because static parser didn't find static dependencies.
    """

    CRITICAL_PATH_PATTERNS = [
        r"auth",
        r"security",
        r"payment",
        r"billing",
        r"sentinel",
        r"token",
        r"core",
        r"persistence",
        r"database",
    ]

    DYNAMIC_PATTERNS = [
        r"getattr\(",
        r"setattr\(",
        r"importlib",
        r"__import__",
        r"eval\(",
        r"exec\(",
        r"globals\(",
        r"locals\(",
    ]

    def __init__(self, workspace_root: Optional[str] = None) -> None:
        self.workspace_root = workspace_root or os.getcwd()
        self.symbol_bridge: Optional[SymbolFineGrainedGraphBridge] = None
        if SymbolFineGrainedGraphBridge is not None:
            try:
                self.symbol_bridge = SymbolFineGrainedGraphBridge.get_instance(self.workspace_root)
            except Exception:
                self.symbol_bridge = None

    def analyze(self, change_set: ChangeSet, workspace_files: Optional[Dict[str, str]] = None) -> VerificationSurface:
        """Analyze ChangeSet and construct the complete VerificationSurface."""
        if not change_set.changes:
            # NO_CHANGE invariant
            return VerificationSurface(
                affected_files=[],
                affected_symbols=[],
                affected_tests=[],
                affected_contracts=[],
                affected_behaviors=[],
                affected_consumers=[],
                browser_surfaces=[],
                risk_level="LOW",
                uncertainty=0.0,
                dynamic_boundaries=[],
                scc_clusters=[],
            )

        affected_files: Set[str] = set()
        affected_symbols: Set[str] = set()
        affected_contracts: Set[str] = set()
        affected_behaviors: Set[str] = set()
        affected_consumers: Set[str] = set()
        browser_surfaces: Set[str] = set()
        dynamic_boundaries: Set[str] = set()
        scc_clusters: Set[str] = set()
        affected_tests: Set[str] = set()

        has_contract_change = False
        has_dynamic_reflection = False
        total_lines_changed = 0

        # Step 1: Direct File & Symbol Ingestion
        for change in change_set.changes:
            affected_files.add(change.file_path)
            if change.symbol_id:
                affected_symbols.add(change.symbol_id)

            if change.change_type in (ChangeType.CONTRACT_CHANGED,):
                has_contract_change = True
                affected_contracts.add(change.symbol_id or change.file_path)

            if "test" in change.file_path.lower():
                affected_tests.add(change.file_path)

            if any(ext in change.file_path for ext in [".tsx", ".jsx", ".html", ".css", "frontend", "components"]):
                browser_surfaces.add(change.file_path)

            if "contract" in change.file_path.lower() or "schema" in change.file_path.lower() or "models" in change.file_path.lower():
                affected_contracts.add(change.file_path)

            lines_add = change.diff_metadata.get("lines_added", 0)
            lines_rem = change.diff_metadata.get("lines_removed", 0)
            total_lines_changed += (lines_add + lines_rem)

        # Step 2: Symbol Graph & SCC Analysis via F60 if available
        if self.symbol_bridge and self.symbol_bridge.graph:
            for sym in list(affected_symbols):
                try:
                    impact_res = self.symbol_bridge.compute_symbol_impact(sym, max_depth=3)
                    if impact_res:
                        for dep_sym in impact_res.impacted_symbols:
                            affected_symbols.add(dep_sym)
                            node = self.symbol_bridge.graph.nodes.get(dep_sym)
                            if node:
                                affected_files.add(node.file_path)
                                affected_consumers.add(f"consumer:{node.file_path}::{node.name}")
                        for scc_id in impact_res.affected_scc_ids:
                            scc_clusters.add(scc_id)
                except Exception:
                    pass

        # Step 3: Check for Dynamic Boundaries and Reflection
        if workspace_files:
            for f_path in affected_files:
                content = workspace_files.get(f_path, "")
                for dyn_pattern in self.DYNAMIC_PATTERNS:
                    if re.search(dyn_pattern, content):
                        dynamic_boundaries.add(f_path)
                        has_dynamic_reflection = True
                        break

        # Step 4: Map Associated Tests
        for f_path in list(affected_files):
            base_name = os.path.splitext(os.path.basename(f_path))[0]
            test_candidate_1 = f"tests/test_{base_name}.py"
            test_candidate_2 = f"test_{base_name}.py"
            affected_tests.add(test_candidate_1)
            affected_tests.add(test_candidate_2)

        # Invariant: Never assume empty impact just because static parser didn't find static dependency
        uncertainty = 0.0
        if dynamic_boundaries:
            uncertainty += min(0.5, 0.15 * len(dynamic_boundaries))
        if has_dynamic_reflection:
            uncertainty = max(uncertainty, 0.4)
        if not affected_symbols and len(affected_files) > 0:
            # File changed but no symbols resolved statically -> mark dynamic uncertainty!
            uncertainty = max(uncertainty, 0.35)
            dynamic_boundaries.update(affected_files)

        # Step 5: Determine Behavioral and Contract Impact
        for f in affected_files:
            if "policy" in f:
                affected_behaviors.add(f"behavior:policy_enforcement:{f}")
            if "workflow" in f or "loop" in f or "engine" in f or "orchestrat" in f:
                affected_behaviors.add(f"behavior:orchestration:{f}")
            if "agent" in f:
                affected_behaviors.add(f"behavior:agent_decision:{f}")

        # Step 6: Risk Assessment
        is_critical = False
        for f in affected_files:
            for cp_pat in self.CRITICAL_PATH_PATTERNS:
                if re.search(cp_pat, f, re.IGNORECASE):
                    is_critical = True
                    break

        if is_critical or len(scc_clusters) >= 2 or has_contract_change and len(affected_consumers) > 10:
            risk_level = "CRITICAL"
        elif len(affected_files) > 5 or len(affected_symbols) > 15 or len(affected_consumers) > 5:
            risk_level = "HIGH"
        elif len(affected_files) > 1 or len(affected_symbols) > 3 or browser_surfaces:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"

        return VerificationSurface(
            affected_files=sorted(list(affected_files)),
            affected_symbols=sorted(list(affected_symbols)),
            affected_tests=sorted(list(affected_tests)),
            affected_contracts=sorted(list(affected_contracts)),
            affected_behaviors=sorted(list(affected_behaviors)),
            affected_consumers=sorted(list(affected_consumers)),
            browser_surfaces=sorted(list(browser_surfaces)),
            risk_level=risk_level,
            uncertainty=round(min(uncertainty, 1.0), 3),
            dynamic_boundaries=sorted(list(dynamic_boundaries)),
            scc_clusters=sorted(list(scc_clusters)),
        )
