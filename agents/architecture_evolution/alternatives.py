"""
JARVIS OS — Phase 64: Autonomous Architecture Evolution & Design Governance
Module: alternatives.py
Generates viable architectural evolution candidates for a given problem.

Rules:
    - Never assume microservices are universally superior.
    - Never assume splitting a package automatically improves architecture.
    - Always include 'keep_current' as an empirical baseline.
    - Attach explicit trade-offs, reversibility classifications, and verification needs.
"""

from __future__ import annotations

import hashlib
from typing import Any, Dict, List, Optional

from .models import (
    AlternativeType,
    ArchitectureAlternative,
    ArchitectureConstraint,
    ArchitectureProblem,
    ProblemCategory,
    ReversibilityStatus,
)


class ArchitectureAlternativeGenerator:
    """Generates alternative architectural solutions tailored to observed problems."""

    def generate_alternatives(
        self,
        problem: ArchitectureProblem,
        constraints: List[ArchitectureConstraint],
        external_pattern_hint: Optional[Dict[str, Any]] = None,
        external_hint: Optional[Dict[str, Any]] = None,
    ) -> List[ArchitectureAlternative]:
        alternatives: List[ArchitectureAlternative] = []
        hint = external_pattern_hint or external_hint

        # 1. Baseline: Keep Current Architecture (Observational stance)
        alternatives.append(self._create_keep_current(problem))

        # 2. Category-Specific Architectural Refactoring Alternatives
        if problem.category == ProblemCategory.COUPLING:
            alternatives.append(self._create_modularization(problem))
            alternatives.append(self._create_facade_adapter(problem))
            alternatives.append(self._create_dependency_inversion(problem))

        elif problem.category == ProblemCategory.SCC:
            alternatives.append(self._create_boundary_extraction(problem))
            alternatives.append(self._create_dependency_inversion(problem))
            alternatives.append(self._create_event_driven(problem))

        elif problem.category == ProblemCategory.CONTRACT:
            alternatives.append(self._create_adapter_layer(problem))
            alternatives.append(self._create_facade_adapter(problem))

        elif problem.category == ProblemCategory.SECURITY:
            alternatives.append(self._create_boundary_extraction(problem))
            alternatives.append(self._create_adapter_layer(problem))

        else:
            alternatives.append(self._create_modularization(problem))
            alternatives.append(self._create_strangler_migration(problem))

        # 3. Integrate External Pattern from Phase 63 (Hypothesis Only)
        if hint:
            alt_f63 = self._create_f63_hypothesis(problem, hint)
            alternatives.append(alt_f63)

        return alternatives

    def _create_keep_current(self, problem: ArchitectureProblem) -> ArchitectureAlternative:
        return ArchitectureAlternative(
            alternative_id=f"alt_keep_{hashlib.sha256(problem.problem_id.encode()).hexdigest()[:6]}",
            problem_id=problem.problem_id,
            alternative_type=AlternativeType.KEEP_CURRENT,
            title="Maintain Current Topology (Accept Technical Debt as Documented Smell)",
            description="Preserves existing component boundaries, avoids refactoring churn, and establishes monitoring thresholds.",
            benefits=["Zero migration risk", "Zero deployment downtime", "Zero engineering cost immediately"],
            costs=["Ongoing maintainability friction", "Gradual coupling accumulation"],
            risks=["Potential cascade in future feature modifications"],
            affected_components=[],
            migration_complexity="LOW",
            compatibility_impact="MINIMAL",
            verification_requirements=["Maintain existing regression tests"],
            reversibility=ReversibilityStatus.EASILY_REVERSIBLE,
            is_hypothesis_from_f63=False,
        )

    def _create_modularization(self, problem: ArchitectureProblem) -> ArchitectureAlternative:
        return ArchitectureAlternative(
            alternative_id=f"alt_mod_{hashlib.sha256(problem.problem_id.encode()).hexdigest()[:6]}",
            problem_id=problem.problem_id,
            alternative_type=AlternativeType.MODULARIZATION,
            title="Internal Modularization & Responsibility Decomposition",
            description="Decomposes tightly coupled internal routines into cohesive sub-packages with distinct single responsibilities.",
            benefits=["Decoupled concern spaces", "Improved unit test isolation", "Lower cognitive burden"],
            costs=["Code reorganization effort", "Internal import re-pathing"],
            risks=["Internal symbol relocation bugs"],
            affected_components=problem.affected_nodes[:4],
            migration_complexity="MEDIUM",
            compatibility_impact="MINIMAL",
            verification_requirements=["Symbol graph invariant check", "Module import tests", "Full regression suite"],
            reversibility=ReversibilityStatus.REVERSIBLE_WITH_MIGRATION,
            is_hypothesis_from_f63=False,
        )

    def _create_boundary_extraction(self, problem: ArchitectureProblem) -> ArchitectureAlternative:
        return ArchitectureAlternative(
            alternative_id=f"alt_bound_{hashlib.sha256(problem.problem_id.encode()).hexdigest()[:6]}",
            problem_id=problem.problem_id,
            alternative_type=AlternativeType.BOUNDARY_EXTRACTION,
            title="Formal Boundary Extraction & Pure Interface Segregation",
            description="Extracts a shared domain interface or independent intermediate layer to break cyclic or dynamic dependencies.",
            benefits=["Breaks cyclic SCC loops", "Enforces static type contracts", "Isolates dynamic reflection"],
            costs=["Additional abstraction layer", "Interface maintenance overhead"],
            risks=["Over-engineering if component is rarely modified"],
            affected_components=problem.affected_nodes[:3],
            migration_complexity="MEDIUM",
            compatibility_impact="MINIMAL",
            verification_requirements=["Contract compatibility suite", "Interface compliance verification"],
            reversibility=ReversibilityStatus.EASILY_REVERSIBLE,
            is_hypothesis_from_f63=False,
        )

    def _create_dependency_inversion(self, problem: ArchitectureProblem) -> ArchitectureAlternative:
        return ArchitectureAlternative(
            alternative_id=f"alt_dip_{hashlib.sha256(problem.problem_id.encode()).hexdigest()[:6]}",
            problem_id=problem.problem_id,
            alternative_type=AlternativeType.DEPENDENCY_INVERSION,
            title="Dependency Inversion Principle (DIP) Injection",
            description="Inverts the direction of coupling by introducing high-level abstractions injected at runtime.",
            benefits=["Eliminates direct layer violations", "Enables clean mock injection in tests"],
            costs=["Requires dependency injection container or factory wiring"],
            risks=["Runtime configuration drift if factory fails"],
            affected_components=problem.affected_nodes[:3],
            migration_complexity="MEDIUM",
            compatibility_impact="MINIMAL",
            verification_requirements=["Dependency injection wiring tests", "Behavioral proof under mocks"],
            reversibility=ReversibilityStatus.REVERSIBLE_WITH_MIGRATION,
            is_hypothesis_from_f63=False,
        )

    def _create_facade_adapter(self, problem: ArchitectureProblem) -> ArchitectureAlternative:
        return ArchitectureAlternative(
            alternative_id=f"alt_fac_{hashlib.sha256(problem.problem_id.encode()).hexdigest()[:6]}",
            problem_id=problem.problem_id,
            alternative_type=AlternativeType.FACADE,
            title="Consolidated Gateway Facade & Rate-Limited Boundary",
            description="Presents a simplified, unified entry point wrapping concentrated contracts or high fan-in hubs.",
            benefits=["Reduces client coupling", "Centralizes validation and rate-limiting", "Hides internal complexity"],
            costs=["Single facade choke-point if under high throughput"],
            risks=["Potential god-object evolution if not bounded"],
            affected_components=problem.affected_nodes[:2],
            migration_complexity="LOW",
            compatibility_impact="MINIMAL",
            verification_requirements=["Contract consumer regression tests", "Load and latency benchmarks"],
            reversibility=ReversibilityStatus.EASILY_REVERSIBLE,
            is_hypothesis_from_f63=False,
        )

    def _create_adapter_layer(self, problem: ArchitectureProblem) -> ArchitectureAlternative:
        return ArchitectureAlternative(
            alternative_id=f"alt_adp_{hashlib.sha256(problem.problem_id.encode()).hexdigest()[:6]}",
            problem_id=problem.problem_id,
            alternative_type=AlternativeType.ADAPTER_LAYER,
            title="Two-Way Semantic Adapter Layer",
            description="Translates legacy contract schemas and dynamic payloads into strongly validated canonical structures.",
            benefits=["Guarantees backward compatibility", "Safely absorbs polymorphic contract drift"],
            costs=["Translation compute overhead per request"],
            risks=["Mapping errors during schema evolution"],
            affected_components=problem.affected_nodes[:2],
            migration_complexity="MEDIUM",
            compatibility_impact="MINIMAL",
            verification_requirements=["Round-trip contract serialization tests", "Fuzzing across schema variants"],
            reversibility=ReversibilityStatus.EASILY_REVERSIBLE,
            is_hypothesis_from_f63=False,
        )

    def _create_event_driven(self, problem: ArchitectureProblem) -> ArchitectureAlternative:
        return ArchitectureAlternative(
            alternative_id=f"alt_evt_{hashlib.sha256(problem.problem_id.encode()).hexdigest()[:6]}",
            problem_id=problem.problem_id,
            alternative_type=AlternativeType.EVENT_DRIVEN,
            title="Asynchronous Event-Driven Decoupling",
            description="Replaces direct synchronous invocation with asynchronous event emission and decoupled subscribers.",
            benefits=["Completely decouples callers and callees", "High temporal resilience"],
            costs=["Event bus infrastructure", "Eventual consistency complexity"],
            risks=["Ordering anomalies", "Debugging distributed async traces"],
            affected_components=problem.affected_nodes[:3],
            migration_complexity="HIGH",
            compatibility_impact="MODERATE",
            verification_requirements=["Message ordering invariants", "Consumer idempotency tests", "End-to-end integration"],
            reversibility=ReversibilityStatus.DIFFICULT_TO_REVERSE,
            is_hypothesis_from_f63=False,
        )

    def _create_strangler_migration(self, problem: ArchitectureProblem) -> ArchitectureAlternative:
        return ArchitectureAlternative(
            alternative_id=f"alt_strang_{hashlib.sha256(problem.problem_id.encode()).hexdigest()[:6]}",
            problem_id=problem.problem_id,
            alternative_type=AlternativeType.STRANGLER_MIGRATION,
            title="Strangler Fig Migration Pattern",
            description="Gradually routes invocations to a modern implementation alongside the legacy component until cutover.",
            benefits=["Incremental de-risking", "Safe dual-run verification", "Zero instant cutover risk"],
            costs=["Temporary dual code path maintenance"],
            risks=["Synchronization drift between dual implementations"],
            affected_components=problem.affected_nodes[:3],
            migration_complexity="HIGH",
            compatibility_impact="MINIMAL",
            verification_requirements=["Shadow verification comparison", "Differential testing suite"],
            reversibility=ReversibilityStatus.REVERSIBLE_WITH_MIGRATION,
            is_hypothesis_from_f63=False,
        )

    def _create_f63_hypothesis(
        self,
        problem: ArchitectureProblem,
        hint: Dict[str, Any],
    ) -> ArchitectureAlternative:
        alt_id = f"alt_f63_{hashlib.sha256((problem.problem_id + str(hint)).encode()).hexdigest()[:6]}"
        return ArchitectureAlternative(
            alternative_id=alt_id,
            problem_id=problem.problem_id,
            alternative_type=AlternativeType.ADAPTER_LAYER,
            title=f"Cross-Project Transferred Pattern: {hint.get('title', 'External Architecture Pattern')}",
            description=f"Hypothesis derived from external project '{hint.get('source_project')}': {hint.get('description', '')}. Note: Requires full local verification.",
            benefits=hint.get("benefits", ["Observed effectiveness in external repository"]),
            costs=hint.get("costs", ["Adaptation to local framework and contracts"]),
            risks=hint.get("risks", ["Potential context drift between external and local paradigms"]),
            affected_components=problem.affected_nodes[:2],
            migration_complexity="MEDIUM",
            compatibility_impact="MINIMAL",
            verification_requirements=["New local test synthesis", "Behavioral proof under target runtime"],
            reversibility=ReversibilityStatus.REVERSIBLE_WITH_MIGRATION,
            is_hypothesis_from_f63=True,
            source_project=hint.get("source_project"),
            knowledge_id=hint.get("knowledge_id"),
        )
