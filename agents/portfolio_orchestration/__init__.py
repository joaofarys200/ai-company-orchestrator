"""
JARVIS OS — Phase 75: Autonomous Engineering Strategy & Portfolio Orchestration
Package initialization and public exports.
"""

from .backlog import PortfolioBacklog
from .bridge import PortfolioOrchestrationBridge
from .dependency_graph import DependencyGraphEngine
from .evaluator import PortfolioEvaluator
from .metrics import PortfolioMetricsTracker
from .models import (
    ConflictDiagnostic,
    ConflictType,
    ConstraintViolationError,
    DependencyCycleError,
    DependencyRelation,
    DependencyType,
    EngineeringInitiative,
    EvidenceProvenance,
    ExecutionSchedule,
    ExecutionScheduleItem,
    InfeasiblePortfolioError,
    InitiativeState,
    InitiativeType,
    MilestoneCheckpoint,
    PortfolioError,
    PortfolioEvaluationResult,
    PortfolioMetrics,
    PortfolioRoadmap,
    RedundancyDefinition,
    ReplanningEvent,
    ReplanningLoopError,
    ReplanningTriggerType,
    ResourceRequirement,
    SynergyDefinition,
    UnauthorizedInitiativeError,
)
from .persistence import PortfolioStore
from .replanning import PortfolioReplanningEngine
from .roadmap import RoadmapGenerator
from .scheduler import CapacityScheduler

__all__ = [
    "PortfolioOrchestrationBridge",
    "PortfolioBacklog",
    "DependencyGraphEngine",
    "PortfolioEvaluator",
    "CapacityScheduler",
    "RoadmapGenerator",
    "PortfolioReplanningEngine",
    "PortfolioMetricsTracker",
    "PortfolioStore",
    "EngineeringInitiative",
    "InitiativeState",
    "InitiativeType",
    "DependencyType",
    "ConflictType",
    "ReplanningTriggerType",
    "ResourceRequirement",
    "EvidenceProvenance",
    "DependencyRelation",
    "ConflictDiagnostic",
    "SynergyDefinition",
    "RedundancyDefinition",
    "PortfolioEvaluationResult",
    "ExecutionScheduleItem",
    "ExecutionSchedule",
    "MilestoneCheckpoint",
    "PortfolioRoadmap",
    "ReplanningEvent",
    "PortfolioMetrics",
    "PortfolioError",
    "DependencyCycleError",
    "InfeasiblePortfolioError",
    "ConstraintViolationError",
    "UnauthorizedInitiativeError",
    "ReplanningLoopError",
]
