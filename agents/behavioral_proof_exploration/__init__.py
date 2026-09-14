"""
JARVIS OS — Phase 51: Behavioral Proof Coverage & Scenario Exploration
Public Exports and Package Manifest.
"""

from agents.behavioral_proof_exploration.bridge import BehavioralProofExplorationBridge
from agents.behavioral_proof_exploration.budget import (
    BudgetExceededError,
    ExplorationBudgetController,
)
from agents.behavioral_proof_exploration.cache import ExplorationReplayCache
from agents.behavioral_proof_exploration.comparator import ExplorationComparator
from agents.behavioral_proof_exploration.counterexample import (
    ExplorationCounterexampleManager,
)
from agents.behavioral_proof_exploration.coverage import BehavioralCoverageEngine
from agents.behavioral_proof_exploration.executor import ScenarioExecutor
from agents.behavioral_proof_exploration.generator import ScenarioGenerator
from agents.behavioral_proof_exploration.index import ExplorationIndex
from agents.behavioral_proof_exploration.invariants import (
    EconomicBehaviorMismatchError,
    ExplorationInvariantEngine,
)
from agents.behavioral_proof_exploration.metrics import ExplorationTelemetry
from agents.behavioral_proof_exploration.models import (
    BehavioralCoverage,
    BehavioralScenario,
    BoundedExplorationProof,
    CoverageDimension,
    CoverageDimensionReport,
    CoverageThresholdPolicy,
    ExplorationBudget,
    ExplorationStrategy,
    MutationCategory,
    ProofResult,
    ProofScope,
    ScenarioExecutionResult,
    ShrunkCounterexample,
    compute_deterministic_id,
)
from agents.behavioral_proof_exploration.mutator import (
    ScenarioMutator,
    UnsafeEconomicMutationError,
)
from agents.behavioral_proof_exploration.scenario import (
    ScenarioIntegrityError,
    ScenarioManager,
)
from agents.behavioral_proof_exploration.scheduler import ScenarioScheduler
from agents.behavioral_proof_exploration.search import ExplorationSearchStrategy
from agents.behavioral_proof_exploration.security import (
    ExplorationSecuritySentinel,
    SecurityCoverageSpoofingError,
    SecurityExplorationTamperedError,
)
from agents.behavioral_proof_exploration.shrinker import CounterexampleShrinker
from agents.behavioral_proof_exploration.trace import ExplorationTraceAdapter
from agents.behavioral_proof_exploration.validator import ExplorationValidator

__all__ = [
    "BehavioralScenario",
    "ExplorationBudget",
    "ProofScope",
    "ExplorationStrategy",
    "MutationCategory",
    "CoverageDimension",
    "CoverageDimensionReport",
    "CoverageThresholdPolicy",
    "BehavioralCoverage",
    "ScenarioExecutionResult",
    "ShrunkCounterexample",
    "BoundedExplorationProof",
    "ProofResult",
    "compute_deterministic_id",
    "ScenarioManager",
    "ScenarioIntegrityError",
    "ScenarioGenerator",
    "ScenarioMutator",
    "UnsafeEconomicMutationError",
    "BehavioralCoverageEngine",
    "ScenarioExecutor",
    "ScenarioScheduler",
    "ExplorationTraceAdapter",
    "ExplorationComparator",
    "ExplorationInvariantEngine",
    "EconomicBehaviorMismatchError",
    "ExplorationCounterexampleManager",
    "CounterexampleShrinker",
    "ExplorationSearchStrategy",
    "ExplorationBudgetController",
    "BudgetExceededError",
    "ExplorationSecuritySentinel",
    "SecurityExplorationTamperedError",
    "SecurityCoverageSpoofingError",
    "ExplorationTelemetry",
    "ExplorationReplayCache",
    "ExplorationValidator",
    "ExplorationIndex",
    "BehavioralProofExplorationBridge",
]
