"""
JARVIS OS — Phase 64: Autonomous Architecture Evolution & Design Governance
Module: impact.py
Calculates blast radius, affected symbols, downstream consumers, and test surfaces
for prospective architectural alternatives.

Rule:
    Distinguish DIRECT, INDIRECT, DOWNSTREAM, UNCERTAIN.
    Never confuse estimated change with executed change.
"""

from __future__ import annotations

from typing import Dict, List, Set

from .models import (
    ArchitectureAlternative,
    ArchitectureSnapshot,
    ImpactAnalysisResult,
    ImpactScope,
)


class ArchitectureImpactAnalyzer:
    """Computes multidimensional impact across files, symbols, consumers, and tests."""

    def analyze_impact(
        self,
        alternative: ArchitectureAlternative,
        snapshot: ArchitectureSnapshot,
    ) -> ImpactAnalysisResult:
        affected_components = set(alternative.affected_components)
        if not affected_components:
            # e.g. keep_current
            return ImpactAnalysisResult(
                alternative_id=alternative.alternative_id,
                affected_files=[],
                affected_symbols=[],
                affected_consumers=[],
                affected_contracts=[],
                affected_behaviors=[],
                affected_tests=[],
                browser_surfaces=[],
                persistence_surfaces=[],
                scc_changes={"scc_split_count": 0, "scc_merge_count": 0},
                blast_radius=0,
                scope=ImpactScope.DIRECT,
            )

        # 1. Direct affected files
        direct_files = [f for f in snapshot.files if any(c in f for c in affected_components)]

        # 2. Direct and indirect affected symbols
        direct_symbols = [s for s in snapshot.symbols if any(c in s for c in affected_components)]

        # 3. Downstream Consumers
        downstream_consumers: Set[str] = set()
        affected_contracts: Set[str] = set()
        for contract, consumers in snapshot.consumers.items():
            if any(c in contract for c in affected_components):
                affected_contracts.add(contract)
                downstream_consumers.update(consumers)

        # 4. SCC modifications
        scc_impact_count = 0
        for scc in snapshot.sccs:
            if any(c in scc for c in affected_components):
                scc_impact_count += 1

        # 5. Affected tests
        affected_tests = [
            t for t in snapshot.test_surfaces
            if any(c in t for c in affected_components) or any(c in t for c in downstream_consumers)
        ]

        # 6. Browser & Persistence surfaces
        affected_browser = [
            b for b in snapshot.browser_surfaces
            if any(c in b for c in affected_components)
        ]
        affected_persistence = [
            p.get("table", str(p)) for p in snapshot.persistence_edges
            if any(c in str(p) for c in affected_components)
        ]

        # Blast radius score calculation
        blast_radius = (
            len(direct_files) * 2
            + len(direct_symbols)
            + len(downstream_consumers) * 3
            + len(affected_contracts) * 4
            + len(affected_tests)
        )

        # Scope assignment
        if len(downstream_consumers) > 5 or scc_impact_count > 1:
            scope = ImpactScope.DOWNSTREAM
        elif len(downstream_consumers) > 0:
            scope = ImpactScope.INDIRECT
        elif len(direct_files) > 0:
            scope = ImpactScope.DIRECT
        else:
            scope = ImpactScope.UNCERTAIN

        return ImpactAnalysisResult(
            alternative_id=alternative.alternative_id,
            affected_files=sorted(direct_files),
            affected_symbols=sorted(direct_symbols),
            affected_consumers=sorted(list(downstream_consumers)),
            affected_contracts=sorted(list(affected_contracts)),
            affected_behaviors=[f"behavior_of_{c}" for c in affected_components],
            affected_tests=sorted(affected_tests),
            browser_surfaces=sorted(affected_browser),
            persistence_surfaces=sorted(list(set(affected_persistence))),
            scc_changes={"scc_affected": scc_impact_count, "breaks_cycle": scc_impact_count > 0},
            blast_radius=blast_radius,
            scope=scope,
        )
