"""
JARVIS OS — Phase 64: Autonomous Architecture Evolution & Design Governance
Module: models.py
Domain models, enums, dataclasses, and immutable records for architectural
observation, problem detection, constraint extraction, alternative generation,
impact/contract/behavior/risk/cost analysis, DAG migration planning,
simulation, verification, and governance gating.

Core Invariant:
    ARCHITECTURE OBSERVATION -> ARCHITECTURE PROBLEM -> CONSTRAINT EXTRACTION
    -> ALTERNATIVE GENERATION -> IMPACT ANALYSIS -> CONTRACT ANALYSIS
    -> BEHAVIOR ANALYSIS -> RISK ANALYSIS -> COST ANALYSIS -> MIGRATION PLAN
    -> SIMULATION -> VERIFICATION -> GOVERNANCE GATE

    PROPOSAL != APPROVAL
    APPROVAL != IMPLEMENTATION
    KNOWLEDGE HYPOTHESIS (F63) != LOCAL ARCHITECTURE PROOF
"""

from __future__ import annotations

import enum
import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple


class ProblemCategory(str, enum.Enum):
    """Architectural problem categories."""
    COUPLING = "COUPLING"
    COHESION = "COHESION"
    SCC = "SCC"
    BOUNDARY = "BOUNDARY"
    CONTRACT = "CONTRACT"
    PERFORMANCE = "PERFORMANCE"
    RELIABILITY = "RELIABILITY"
    SECURITY = "SECURITY"
    TESTABILITY = "TESTABILITY"
    MAINTAINABILITY = "MAINTAINABILITY"
    SCALABILITY = "SCALABILITY"
    ARCHITECTURAL_DRIFT = "ARCHITECTURAL_DRIFT"


class ProblemSeverity(str, enum.Enum):
    """Problem severity levels."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ObservationStatus(str, enum.Enum):
    """Status of an architectural smell or observation."""
    OBSERVED = "OBSERVED"
    SUSPECTED = "SUSPECTED"
    CONFIRMED_WITHIN_SCOPE = "CONFIRMED_WITHIN_SCOPE"
    UNKNOWN = "UNKNOWN"


class AlternativeType(str, enum.Enum):
    """Types of architectural alternatives."""
    KEEP_CURRENT = "keep_current"
    MODULARIZATION = "modularization"
    SERVICE_SPLIT = "service_split"
    BOUNDARY_EXTRACTION = "boundary_extraction"
    DEPENDENCY_INVERSION = "dependency_inversion"
    EVENT_DRIVEN = "event_driven"
    SYNCHRONOUS_API = "synchronous_api"
    ADAPTER_LAYER = "adapter_layer"
    FACADE = "facade"
    STRANGLER_MIGRATION = "strangler_migration"
    DATA_BOUNDARY = "data_boundary"
    CACHE_BOUNDARY = "cache_boundary"
    QUEUE_BOUNDARY = "queue_boundary"


class ImpactScope(str, enum.Enum):
    """Granularity of estimated impact."""
    DIRECT = "DIRECT"
    INDIRECT = "INDIRECT"
    DOWNSTREAM = "DOWNSTREAM"
    UNCERTAIN = "UNCERTAIN"


class ContractBreakStatus(str, enum.Enum):
    """Contract compatibility status."""
    NON_BREAKING = "NON_BREAKING"
    POTENTIALLY_BREAKING = "POTENTIALLY_BREAKING"
    BREAKING = "BREAKING"
    UNKNOWN = "UNKNOWN"


class BehaviorPreservationStatus(str, enum.Enum):
    """Behavioral equivalence status."""
    PROVEN_WITHIN_SCOPE = "PROVEN_WITHIN_SCOPE"
    POTENTIAL_BEHAVIOR_DRIFT = "POTENTIAL_BEHAVIOR_DRIFT"
    INCOMPATIBLE = "INCOMPATIBLE"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class RiskCriticality(str, enum.Enum):
    """Overall risk classification."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class CostCategory(str, enum.Enum):
    """Dimension of estimated architectural cost."""
    IMPLEMENTATION = "implementation"
    MIGRATION = "migration"
    TESTING = "testing"
    RUNTIME = "runtime"
    OPERATIONAL = "operational"
    ROLLBACK = "rollback"
    MAINTENANCE = "maintenance"


class CostObservationStatus(str, enum.Enum):
    """Epistemic status of a cost figure."""
    OBSERVED = "OBSERVED"
    ESTIMATED = "ESTIMATED"
    INFERRED = "INFERRED"


class ReversibilityStatus(str, enum.Enum):
    """Reversibility classification of an architectural alternative."""
    EASILY_REVERSIBLE = "EASILY_REVERSIBLE"
    REVERSIBLE_WITH_MIGRATION = "REVERSIBLE_WITH_MIGRATION"
    DIFFICULT_TO_REVERSE = "DIFFICULT_TO_REVERSE"
    IRREVERSIBLE = "IRREVERSIBLE"
    UNKNOWN = "UNKNOWN"


class SimulationStatus(str, enum.Enum):
    """Result of pre-execution architectural simulation."""
    SIMULATION_SAFE = "SIMULATION_SAFE"
    SIMULATION_RISK = "SIMULATION_RISK"
    SIMULATION_INCOMPLETE = "SIMULATION_INCOMPLETE"


class GovernanceDecisionState(str, enum.Enum):
    """States emitted by the Architecture Governance Gate."""
    OBSERVATION_ONLY = "OBSERVATION_ONLY"
    PROPOSAL_READY = "PROPOSAL_READY"
    VALIDATION_REQUIRED = "VALIDATION_REQUIRED"
    HUMAN_REVIEW = "HUMAN_REVIEW"
    BLOCKED = "BLOCKED"
    APPROVED_FOR_IMPLEMENTATION = "APPROVED_FOR_IMPLEMENTATION"
    REJECTED = "REJECTED"


class MigrationStepType(str, enum.Enum):
    """Stages in the staged migration DAG."""
    PREPARATION = "PREPARATION"
    COMPATIBILITY_LAYER = "COMPATIBILITY_LAYER"
    DUAL_PATH = "DUAL_PATH"
    VALIDATION = "VALIDATION"
    CUTOVER = "CUTOVER"
    OBSERVATION = "OBSERVATION"
    CLEANUP = "CLEANUP"


@dataclass
class ArchitectureSnapshot:
    """Deterministic structural snapshot of a repository architecture."""
    snapshot_id: str
    files: List[str] = field(default_factory=list)
    symbols: List[str] = field(default_factory=list)
    modules: List[str] = field(default_factory=list)
    packages: List[str] = field(default_factory=list)
    services: List[str] = field(default_factory=list)
    interfaces: List[str] = field(default_factory=list)
    contracts: List[str] = field(default_factory=list)
    dependencies: List[Tuple[str, str]] = field(default_factory=list)
    consumers: Dict[str, List[str]] = field(default_factory=dict)
    sccs: List[List[str]] = field(default_factory=list)
    communication_edges: List[Dict[str, Any]] = field(default_factory=list)
    persistence_edges: List[Dict[str, Any]] = field(default_factory=list)
    external_boundaries: List[str] = field(default_factory=list)
    browser_surfaces: List[str] = field(default_factory=list)
    test_surfaces: List[str] = field(default_factory=list)
    risk_zones: List[str] = field(default_factory=list)
    snapshot_hash: str = ""
    timestamp: float = field(default_factory=time.time)
    source: str = "workspace"
    provenance: Dict[str, Any] = field(default_factory=dict)

    def compute_hash(self) -> str:
        payload = {
            "files": sorted(self.files),
            "symbols": sorted(self.symbols),
            "modules": sorted(self.modules),
            "packages": sorted(self.packages),
            "services": sorted(self.services),
            "interfaces": sorted(self.interfaces),
            "contracts": sorted(self.contracts),
            "dependencies": sorted([list(d) for d in self.dependencies]),
            "sccs": sorted([sorted(c) for c in self.sccs]),
            "external_boundaries": sorted(self.external_boundaries),
            "browser_surfaces": sorted(self.browser_surfaces),
            "test_surfaces": sorted(self.test_surfaces),
            "risk_zones": sorted(self.risk_zones),
        }
        can = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(can.encode("utf-8")).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ArchitectureProblem:
    """Structured architectural defect, bottleneck, or smell."""
    problem_id: str
    category: ProblemCategory
    affected_nodes: List[str]
    affected_symbols: List[str]
    evidence: Dict[str, Any]
    severity: ProblemSeverity
    confidence: float
    constraints: List[str] = field(default_factory=list)
    provenance: Dict[str, Any] = field(default_factory=dict)
    status: ObservationStatus = ObservationStatus.OBSERVED

    def to_dict(self) -> Dict[str, Any]:
        res = asdict(self)
        res["category"] = self.category.value
        res["severity"] = self.severity.value
        res["status"] = self.status.value
        return res


@dataclass
class ArchitectureConstraint:
    """Extracted constraint governing any valid architectural transformation."""
    constraint_id: str
    name: str
    category: str  # functional, non_functional, security, economic, etc.
    description: str
    source: str
    confidence: float
    evidence: Dict[str, Any]
    scope: str = "project"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ArchitectureAlternative:
    """Generated architectural candidate for resolving or observing a problem."""
    alternative_id: str
    problem_id: str
    alternative_type: AlternativeType
    title: str
    description: str
    benefits: List[str] = field(default_factory=list)
    costs: List[str] = field(default_factory=list)
    risks: List[str] = field(default_factory=list)
    affected_components: List[str] = field(default_factory=list)
    migration_complexity: str = "MEDIUM"  # LOW, MEDIUM, HIGH, EXTREME
    compatibility_impact: str = "MINIMAL"  # MINIMAL, MODERATE, HIGH, BREAKING
    verification_requirements: List[str] = field(default_factory=list)
    reversibility: ReversibilityStatus = ReversibilityStatus.REVERSIBLE_WITH_MIGRATION
    is_hypothesis_from_f63: bool = False
    source_project: Optional[str] = None
    knowledge_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        res = asdict(self)
        res["alternative_type"] = self.alternative_type.value
        res["reversibility"] = self.reversibility.value
        return res


@dataclass
class ImpactAnalysisResult:
    """Calculated blast radius across code, symbols, contracts, and tests."""
    alternative_id: str
    affected_files: List[str] = field(default_factory=list)
    affected_symbols: List[str] = field(default_factory=list)
    affected_consumers: List[str] = field(default_factory=list)
    affected_contracts: List[str] = field(default_factory=list)
    affected_behaviors: List[str] = field(default_factory=list)
    affected_tests: List[str] = field(default_factory=list)
    browser_surfaces: List[str] = field(default_factory=list)
    persistence_surfaces: List[str] = field(default_factory=list)
    scc_changes: Dict[str, Any] = field(default_factory=dict)
    blast_radius: int = 0
    scope: ImpactScope = ImpactScope.DIRECT

    def to_dict(self) -> Dict[str, Any]:
        res = asdict(self)
        res["scope"] = self.scope.value
        return res


@dataclass
class ContractAnalysisResult:
    """Contract change and breaking risk assessment (integrates F44–F49)."""
    alternative_id: str
    breaking_contracts: List[str] = field(default_factory=list)
    potentially_breaking_contracts: List[str] = field(default_factory=list)
    affected_consumers: List[str] = field(default_factory=list)
    required_migrations: List[str] = field(default_factory=list)
    polymorphic_risks: List[str] = field(default_factory=list)
    schema_changes: List[Dict[str, Any]] = field(default_factory=list)
    versioning_needs: List[str] = field(default_factory=list)
    status: ContractBreakStatus = ContractBreakStatus.NON_BREAKING

    def to_dict(self) -> Dict[str, Any]:
        res = asdict(self)
        res["status"] = self.status.value
        return res


@dataclass
class BehaviorAnalysisResult:
    """Behavior preservation assessment (integrates F50–F52)."""
    alternative_id: str
    behavior_preservation: str = "PRESERVED"
    ordering_preservation: str = "PRESERVED"
    retry_impact: str = "UNCHANGED"
    timeout_impact: str = "UNCHANGED"
    concurrency_impact: str = "UNCHANGED"
    idempotency_impact: str = "UNCHANGED"
    state_transition_impact: str = "UNCHANGED"
    failure_behavior_impact: str = "UNCHANGED"
    status: BehaviorPreservationStatus = BehaviorPreservationStatus.PROVEN_WITHIN_SCOPE
    evidence: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        res = asdict(self)
        res["status"] = self.status.value
        return res


@dataclass
class RiskAnalysisResult:
    """Multi-axis risk vector evaluation."""
    alternative_id: str
    security_risk: float = 0.0
    reliability_risk: float = 0.0
    migration_risk: float = 0.0
    rollback_risk: float = 0.0
    economic_risk: float = 0.0
    operational_risk: float = 0.0
    data_loss_risk: float = 0.0
    contract_risk: float = 0.0
    risk_vector: Dict[str, float] = field(default_factory=dict)
    uncertainty_vector: Dict[str, float] = field(default_factory=dict)
    criticality: RiskCriticality = RiskCriticality.LOW

    def to_dict(self) -> Dict[str, Any]:
        res = asdict(self)
        res["criticality"] = self.criticality.value
        return res


@dataclass
class CostEstimationResult:
    """Multi-dimensional cost estimation with epistemic grounding."""
    alternative_id: str
    costs: Dict[str, float] = field(default_factory=dict)
    observation_status: CostObservationStatus = CostObservationStatus.ESTIMATED
    total_estimated_effort_hours: float = 0.0
    currency_budget: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        res = asdict(self)
        res["observation_status"] = self.observation_status.value
        return res


@dataclass
class MigrationStep:
    """A node in the phased DAG migration plan."""
    step_id: str
    step_type: MigrationStepType
    title: str
    description: str
    dependencies: List[str] = field(default_factory=list)
    rollback_action: str = ""
    is_reversibility_supported: bool = True
    verification_gates: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        res = asdict(self)
        res["step_type"] = self.step_type.value
        return res


@dataclass
class ArchitectureMigrationPlan:
    """Staged DAG migration plan with rollback checkpoints."""
    plan_id: str
    alternative_id: str
    steps: List[MigrationStep] = field(default_factory=list)
    total_steps: int = 0
    reversibility_status: ReversibilityStatus = ReversibilityStatus.REVERSIBLE_WITH_MIGRATION
    rollback_strategy: str = "Staged compensation and blue-green rollback"
    rollback_complexity: str = "LOW"
    rollback_evidence: str = "Rollback actions simulated and verified in sandbox"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "alternative_id": self.alternative_id,
            "steps": [s.to_dict() for s in self.steps],
            "total_steps": self.total_steps,
            "reversibility_status": self.reversibility_status.value,
            "rollback_strategy": self.rollback_strategy,
            "rollback_complexity": self.rollback_complexity,
            "rollback_evidence": self.rollback_evidence,
        }


@dataclass
class SimulationResult:
    """Dry-run simulation of architectural mutations."""
    alternative_id: str
    graph_mutation_valid: bool = True
    contract_changes_safe: bool = True
    behavior_preserved: bool = True
    test_impact_acceptable: bool = True
    rollback_path_verified: bool = True
    failure_scenarios_tested: int = 0
    migration_ordering_valid: bool = True
    status: SimulationStatus = SimulationStatus.SIMULATION_SAFE
    logs: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        res = asdict(self)
        res["status"] = self.status.value
        return res


@dataclass
class VerificationPlan:
    """Comprehensive multi-tier verification requirements (integrates F61/F62)."""
    plan_id: str
    alternative_id: str
    required_tests: List[str] = field(default_factory=list)
    required_contract_checks: List[str] = field(default_factory=list)
    required_behavior_checks: List[str] = field(default_factory=list)
    required_browser_checks: List[str] = field(default_factory=list)
    required_migration_checks: List[str] = field(default_factory=list)
    required_rollback_checks: List[str] = field(default_factory=list)
    required_security_checks: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ArchitectureComparisonResult:
    """Comparative trade-off matrix across alternative candidates."""
    problem_id: str
    alternatives: List[Dict[str, Any]] = field(default_factory=list)
    tradeoffs: List[Dict[str, Any]] = field(default_factory=list)
    radar_metrics: Dict[str, Dict[str, float]] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ArchitectureGovernanceDecision:
    """Immutable governance gate verdict."""
    decision_id: str
    problem_id: str
    alternative_id: Optional[str]
    state: GovernanceDecisionState
    reason: str
    conditions: List[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)
    sentinel_passed: bool = True
    provenance_hash: str = ""

    def to_dict(self) -> Dict[str, Any]:
        res = asdict(self)
        res["state"] = self.state.value
        return res


@dataclass
class ArchitectureProvenanceRecord:
    """Cryptographic audit chain record."""
    record_id: str
    target_id: str
    source_type: str
    action: str
    actor: str
    timestamp: float = field(default_factory=time.time)
    hash_signature: str = ""
    parent_hashes: List[str] = field(default_factory=list)

    def compute_signature(self) -> str:
        payload = f"{self.record_id}:{self.target_id}:{self.source_type}:{self.action}:{self.actor}:{self.timestamp}:{':'.join(self.parent_hashes)}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
