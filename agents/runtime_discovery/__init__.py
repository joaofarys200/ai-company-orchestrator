"""
JARVIS OS — Phase 45: Runtime Contract Discovery & Safe Schema Inference
Public API exports.
"""

from agents.runtime_discovery.bridge import RuntimeDiscoveryBridge
from agents.runtime_discovery.diff import ContractDiffEngine
from agents.runtime_discovery.inference import SchemaInferenceEngine
from agents.runtime_discovery.models import (
    ConsistencyVerdict,
    ContractDiff,
    ContractProposal,
    DiffSeverity,
    DiscoveryPolicyAction,
    FieldDifference,
    FieldDiffType,
    InferredSchema,
    ObservationSourceType,
    ProposalStatus,
    RuntimeObservation,
)
from agents.runtime_discovery.observer import RuntimeContractObserver
from agents.runtime_discovery.security import RuntimeDiscoverySecurity
from agents.runtime_discovery.validator import ContractProposalValidator

__all__ = [
    "ObservationSourceType",
    "ProposalStatus",
    "FieldDiffType",
    "DiffSeverity",
    "ConsistencyVerdict",
    "DiscoveryPolicyAction",
    "RuntimeObservation",
    "FieldDifference",
    "ContractDiff",
    "InferredSchema",
    "ContractProposal",
    "RuntimeDiscoverySecurity",
    "RuntimeContractObserver",
    "SchemaInferenceEngine",
    "ContractDiffEngine",
    "ContractProposalValidator",
    "RuntimeDiscoveryBridge",
]
