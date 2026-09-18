"""
JARVIS OS — Phase 66: Multi-Agent Engineering Coordination & Conflict Arbitration
Package: backend.agents.multi_agent_coordination
Exports core bridges, managers, engines, and domain models.
"""

from .bridge import MultiAgentCoordinationBridge
from .priority import AgentPriorityModel
from .models import (
    AgentChangeSet,
    AgentConflict,
    AgentEngineeringIntent,
    ArbitrationDecision,
    ArbitrationResolution,
    ClaimType,
    ConflictType,
    ConvergenceState,
    DeadlockState,
    IntentState,
    MergeResult,
    ProvenanceRecord,
    RebaseResult,
    ResourceClaim,
    ResourceGranularity,
    SchedulingDecision,
    StarvationPolicy,
)

__all__ = [
    "MultiAgentCoordinationBridge",
    "AgentPriorityModel",
    "AgentEngineeringIntent",
    "ResourceClaim",
    "AgentConflict",
    "ArbitrationDecision",
    "AgentChangeSet",
    "MergeResult",
    "RebaseResult",
    "ProvenanceRecord",
    "IntentState",
    "ResourceGranularity",
    "ClaimType",
    "ConflictType",
    "ArbitrationResolution",
    "SchedulingDecision",
    "DeadlockState",
    "StarvationPolicy",
    "ConvergenceState",
]
