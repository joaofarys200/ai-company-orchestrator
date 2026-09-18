"""
JARVIS OS — Phase 61: Autonomous Test Synthesis & Coverage-Guided Validation
Package Initialization
"""

from .bridge import AutonomousTestSynthesisBridge
from .models import (
    CoverageGapType,
    CoverageMetrics,
    MutationResult,
    MutationType,
    TestCandidate,
    TestCandidateStatus,
    TestEvidenceItem,
    TestExecutionResult,
    TestFramework,
    TestRequirement,
    TestRequirementSource,
    TestStrategy,
)

__all__ = [
    "AutonomousTestSynthesisBridge",
    "TestRequirement",
    "TestRequirementSource",
    "CoverageGapType",
    "TestStrategy",
    "TestFramework",
    "TestCandidate",
    "TestCandidateStatus",
    "TestExecutionResult",
    "TestEvidenceItem",
    "CoverageMetrics",
    "MutationResult",
    "MutationType",
]
