"""
JARVIS OS — Phase 64: Autonomous Architecture Evolution & Design Governance
Module: contracts.py
Evaluates contract compatibility, schema mutations, polymorphic risks, and breaking changes.

Rule:
    An alternative that introduces BREAKING contracts cannot be marked as safe.
    States: NON_BREAKING, POTENTIALLY_BREAKING, BREAKING, UNKNOWN.
"""

from __future__ import annotations

from typing import List

from .models import (
    ArchitectureAlternative,
    ArchitectureSnapshot,
    ContractAnalysisResult,
    ContractBreakStatus,
)


class ArchitectureContractAnalyzer:
    """Analyzes contract breaks, consumer compatibility, and schema migrations."""

    def analyze_contracts(
        self,
        alternative: ArchitectureAlternative,
        snapshot: ArchitectureSnapshot,
    ) -> ContractAnalysisResult:
        affected_comps = set(alternative.affected_components)
        if not affected_comps:
            return ContractAnalysisResult(
                alternative_id=alternative.alternative_id,
                breaking_contracts=[],
                potentially_breaking_contracts=[],
                affected_consumers=[],
                required_migrations=[],
                polymorphic_risks=[],
                schema_changes=[],
                versioning_needs=[],
                status=ContractBreakStatus.NON_BREAKING,
            )

        breaking: List[str] = []
        potentially_breaking: List[str] = []
        consumers_affected: List[str] = []
        migrations: List[str] = []
        poly_risks: List[str] = []
        schema_changes: List[dict] = []
        versioning: List[str] = []

        for contract, consumers in snapshot.consumers.items():
            if any(c in contract for c in affected_comps):
                consumers_affected.extend(consumers)
                # Check alternative compatibility impact
                if alternative.compatibility_impact == "BREAKING":
                    breaking.append(contract)
                    migrations.append(f"Migrate consumers of {contract} to v2 schema")
                    versioning.append(f"{contract}@v2.0.0")
                elif alternative.compatibility_impact in ["HIGH", "MODERATE"]:
                    potentially_breaking.append(contract)
                    poly_risks.append(f"Union variant shift on {contract}")
                    schema_changes.append({"contract": contract, "field_drift": "optional_to_required"})
                    versioning.append(f"{contract}@v1.1.0")

        # Determine overall contract break status
        if breaking:
            status = ContractBreakStatus.BREAKING
        elif potentially_breaking:
            status = ContractBreakStatus.POTENTIALLY_BREAKING
        elif consumers_affected:
            status = ContractBreakStatus.NON_BREAKING
        else:
            status = ContractBreakStatus.NON_BREAKING

        return ContractAnalysisResult(
            alternative_id=alternative.alternative_id,
            breaking_contracts=sorted(list(set(breaking))),
            potentially_breaking_contracts=sorted(list(set(potentially_breaking))),
            affected_consumers=sorted(list(set(consumers_affected))),
            required_migrations=sorted(list(set(migrations))),
            polymorphic_risks=sorted(list(set(poly_risks))),
            schema_changes=schema_changes,
            versioning_needs=sorted(list(set(versioning))),
            status=status,
        )
