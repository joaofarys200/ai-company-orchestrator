"""
JARVIS OS — Phase 53: Universal Project Preflight & Runtime Failure Auto-Recovery
Public API and submodules.
"""

from agents.project_preflight.bridge import ProjectPreflightBridge
from agents.project_preflight.cache import DeterministicFailureCache
from agents.project_preflight.config import ConfigValidator
from agents.project_preflight.dependencies import DependencyValidator
from agents.project_preflight.detector import ProjectProfileDetector
from agents.project_preflight.diagnostics import RuntimeDiagnosticEngine
from agents.project_preflight.entrypoint import EntrypointValidator
from agents.project_preflight.healthcheck import HealthcheckEngine
from agents.project_preflight.index import ProjectPreflightIndex
from agents.project_preflight.javascript import JavaScriptPreflightAnalyzer
from agents.project_preflight.language import (
    BROWSER_LEGITIMATE_GLOBALS,
    NODE_LEGITIMATE_GLOBALS,
    PYTHON_LEGITIMATE_BUILTINS,
    LanguageType,
    RuntimeType,
)
from agents.project_preflight.metrics import PreflightTelemetry
from agents.project_preflight.models import (
    DiagnosticErrorClass,
    FailureFingerprint,
    FilePatch,
    IssueSeverity,
    PreflightGateDecision,
    PreflightIssue,
    PreflightPolicy,
    PreflightResult,
    ProjectRuntimeProfile,
    RecoveryRun,
    RepairCategory,
    RepairConfidence,
    RepairPlan,
    RuntimeDiagnostic,
    StartupHealthResult,
)
from agents.project_preflight.node import NodeRuntimeValidator
from agents.project_preflight.policy import PreflightPolicyEngine
from agents.project_preflight.python import PythonPreflightAnalyzer
from agents.project_preflight.repair import SafeRepairPlanner
from agents.project_preflight.security import PreflightSecuritySentinel, SecurityVetoError
from agents.project_preflight.typescript import TypeScriptPreflightAnalyzer
from agents.project_preflight.validator import PreflightProofValidator

__all__ = [
    "ProjectPreflightBridge",
    "ProjectProfileDetector",
    "JavaScriptPreflightAnalyzer",
    "TypeScriptPreflightAnalyzer",
    "PythonPreflightAnalyzer",
    "NodeRuntimeValidator",
    "DependencyValidator",
    "EntrypointValidator",
    "ConfigValidator",
    "HealthcheckEngine",
    "RuntimeDiagnosticEngine",
    "SafeRepairPlanner",
    "PreflightPolicyEngine",
    "PreflightSecuritySentinel",
    "SecurityVetoError",
    "PreflightTelemetry",
    "DeterministicFailureCache",
    "PreflightProofValidator",
    "ProjectPreflightIndex",
    "ProjectRuntimeProfile",
    "PreflightResult",
    "PreflightIssue",
    "IssueSeverity",
    "StartupHealthResult",
    "RuntimeDiagnostic",
    "DiagnosticErrorClass",
    "RepairPlan",
    "RepairCategory",
    "RepairConfidence",
    "FilePatch",
    "RecoveryRun",
    "FailureFingerprint",
    "PreflightPolicy",
    "PreflightGateDecision",
    "LanguageType",
    "RuntimeType",
    "NODE_LEGITIMATE_GLOBALS",
    "BROWSER_LEGITIMATE_GLOBALS",
    "PYTHON_LEGITIMATE_BUILTINS",
]
