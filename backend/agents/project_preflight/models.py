"""
JARVIS OS — Phase 53: Universal Project Preflight & Runtime Failure Auto-Recovery
Canonical Data Models for Project Runtime Profiles, Preflight Results, Diagnostics,
Safe Repair Plans, Healthchecks, and Recovery Ledgers.
"""

from __future__ import annotations

import copy
import hashlib
import json
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class LanguageType(str, Enum):
    JAVASCRIPT = "JAVASCRIPT"
    TYPESCRIPT = "TYPESCRIPT"
    PYTHON = "PYTHON"
    HTML_JS = "HTML/JAVASCRIPT"
    UNKNOWN = "UNKNOWN"


class RuntimeType(str, Enum):
    NODE_CJS = "NODE_CJS"
    NODE_ESM = "NODE_ESM"
    PYTHON_3 = "PYTHON_3"
    STATIC_BROWSER = "STATIC_BROWSER"
    UNKNOWN = "UNKNOWN"


class IssueSeverity(str, Enum):
    BLOCKER = "BLOCKER"
    WARNING = "WARNING"
    ADVISORY = "ADVISORY"


class DiagnosticErrorClass(str, Enum):
    REFERENCE_ERROR = "REFERENCE_ERROR"
    MODULE_NOT_FOUND = "MODULE_NOT_FOUND"
    IMPORT_ERROR = "IMPORT_ERROR"
    NAME_ERROR = "NAME_ERROR"
    TYPE_ERROR = "TYPE_ERROR"
    SYNTAX_ERROR = "SYNTAX_ERROR"
    PORT_CONFLICT = "PORT_CONFLICT"
    CONNECTION_ERROR = "CONNECTION_ERROR"
    STARTUP_TIMEOUT = "STARTUP_TIMEOUT"
    HEALTHCHECK_FAILURE = "HEALTHCHECK_FAILURE"
    CONFIGURATION_ERROR = "CONFIGURATION_ERROR"
    UNKNOWN_RUNTIME_FAILURE = "UNKNOWN_RUNTIME_FAILURE"


class RepairCategory(str, Enum):
    IMPORT_MISSING = "IMPORT_MISSING"
    DEPENDENCY_MISSING = "DEPENDENCY_MISSING"
    ENTRYPOINT_MISSING = "ENTRYPOINT_MISSING"
    CONFIG_MISSING = "CONFIG_MISSING"
    MIDDLEWARE_MISSING = "MIDDLEWARE_MISSING"
    START_SCRIPT_MISSING = "START_SCRIPT_MISSING"
    HEALTHCHECK_MISSING = "HEALTHCHECK_MISSING"


class RepairConfidence(str, Enum):
    HIGH_CONFIDENCE = "HIGH_CONFIDENCE"
    MEDIUM_CONFIDENCE = "MEDIUM_CONFIDENCE"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"


class PreflightPolicy(str, Enum):
    STANDARD = "STANDARD"
    STRICT = "STRICT"
    CRITICAL = "CRITICAL"
    ECONOMIC_CRITICAL = "ECONOMIC_CRITICAL"
    SECURITY_CRITICAL = "SECURITY_CRITICAL"


class PreflightGateDecision(str, Enum):
    GATE_CLEARED = "GATE_CLEARED"
    HUMAN_REVIEW_REQUIRED = "HUMAN_REVIEW_REQUIRED"
    EXECUTION_BLOCKED = "EXECUTION_BLOCKED"


def compute_deterministic_hash(data: Any, prefix: str = "") -> str:
    serialized = json.dumps(data, sort_keys=True, default=str)
    digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}{digest}"


@dataclass
class ProjectRuntimeProfile:
    """
    Structured profile of a user project directory.
    Inferred only through explicit evidence; defaults to UNKNOWN on ambiguity.
    """
    project_id: str
    workspace_root: str
    language: LanguageType = LanguageType.UNKNOWN
    runtime: RuntimeType = RuntimeType.UNKNOWN
    package_manager: Optional[str] = None
    entrypoint: Optional[str] = None
    build_command: Optional[str] = None
    start_command: Optional[str] = None
    test_command: Optional[str] = None
    healthcheck_path: str = "/"
    default_port: int = 3000
    dependency_manifest: Optional[str] = None
    config_files: List[str] = field(default_factory=list)
    has_node_modules: bool = False
    has_venv: bool = False
    inferred_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "project_id": self.project_id,
            "workspace_root": self.workspace_root,
            "language": self.language.value,
            "runtime": self.runtime.value,
            "package_manager": self.package_manager,
            "entrypoint": self.entrypoint,
            "build_command": self.build_command,
            "start_command": self.start_command,
            "test_command": self.test_command,
            "healthcheck_path": self.healthcheck_path,
            "default_port": self.default_port,
            "dependency_manifest": self.dependency_manifest,
            "config_files": list(self.config_files),
            "has_node_modules": self.has_node_modules,
            "has_venv": self.has_venv,
            "inferred_at": self.inferred_at,
        }


@dataclass
class PreflightIssue:
    """An issue detected during read-only preflight analysis."""
    issue_id: str
    severity: IssueSeverity
    category: str
    message: str
    file_path: Optional[str] = None
    line: Optional[int] = None
    symbol: Optional[str] = None
    suggested_action: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "issue_id": self.issue_id,
            "severity": self.severity.value,
            "category": self.category,
            "message": self.message,
            "file_path": self.file_path,
            "line": self.line,
            "symbol": self.symbol,
            "suggested_action": self.suggested_action,
        }


@dataclass
class PreflightResult:
    """Result of read-only preflight verification."""
    preflight_id: str
    project_id: str
    policy: PreflightPolicy
    can_proceed: bool
    issues: List[PreflightIssue] = field(default_factory=list)
    state_hash_before: str = ""
    state_hash_after: str = ""
    duration_ms: float = 0.0
    timestamp: float = field(default_factory=time.time)

    @property
    def blockers(self) -> List[PreflightIssue]:
        return [i for i in self.issues if i.severity == IssueSeverity.BLOCKER]

    @property
    def warnings(self) -> List[PreflightIssue]:
        return [i for i in self.issues if i.severity == IssueSeverity.WARNING]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "preflight_id": self.preflight_id,
            "project_id": self.project_id,
            "policy": self.policy.value,
            "can_proceed": self.can_proceed,
            "issues": [i.to_dict() for i in self.issues],
            "blockers_count": len(self.blockers),
            "warnings_count": len(self.warnings),
            "state_hash_before": self.state_hash_before,
            "state_hash_after": self.state_hash_after,
            "duration_ms": self.duration_ms,
            "timestamp": self.timestamp,
        }


@dataclass
class StartupHealthResult:
    """Result of real post-startup health probing."""
    started: bool
    ready: bool
    port: Optional[int] = None
    status_code: Optional[int] = None
    latency_ms: float = 0.0
    failure_reason: Optional[str] = None
    preview_url: Optional[str] = None
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "started": self.started,
            "ready": self.ready,
            "port": self.port,
            "status_code": self.status_code,
            "latency_ms": round(self.latency_ms, 2),
            "failure_reason": self.failure_reason,
            "preview_url": self.preview_url,
            "timestamp": self.timestamp,
        }


@dataclass
class RuntimeDiagnostic:
    """Structured diagnostic produced from crash output or stderr."""
    diagnostic_id: str
    error_class: DiagnosticErrorClass
    message: str
    file_path: Optional[str] = None
    line: Optional[int] = None
    column: Optional[int] = None
    symbol: Optional[str] = None
    probable_cause: str = ""
    evidence: List[str] = field(default_factory=list)
    confidence: float = 0.0
    suggested_fix: str = ""
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "diagnostic_id": self.diagnostic_id,
            "error_class": self.error_class.value,
            "message": self.message,
            "file_path": self.file_path,
            "line": self.line,
            "column": self.column,
            "symbol": self.symbol,
            "probable_cause": self.probable_cause,
            "evidence": list(self.evidence),
            "confidence": round(self.confidence, 4),
            "suggested_fix": self.suggested_fix,
            "timestamp": self.timestamp,
        }


@dataclass
class FilePatch:
    """A non-destructive file patch with prior snapshot and replacement."""
    relative_path: str
    original_content: str
    patched_content: str
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "relative_path": self.relative_path,
            "original_content_length": len(self.original_content),
            "patched_content_length": len(self.patched_content),
            "reason": self.reason,
        }


@dataclass
class RepairPlan:
    """Deterministic, reversible repair plan."""
    repair_id: str
    diagnostic_id: str
    category: RepairCategory
    confidence: RepairConfidence
    reason: str
    file_patches: List[FilePatch] = field(default_factory=list)
    risk_score: float = 0.1
    rollback_plan: Dict[str, Any] = field(default_factory=dict)
    expected_effect: str = ""
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "repair_id": self.repair_id,
            "diagnostic_id": self.diagnostic_id,
            "category": self.category.value if hasattr(self.category, "value") else str(self.category),
            "confidence": self.confidence.value if hasattr(self.confidence, "value") else str(self.confidence),
            "reason": self.reason,
            "file_patches": [p.to_dict() for p in self.file_patches],
            "risk_score": round(self.risk_score, 4),
            "rollback_plan": self.rollback_plan,
            "expected_effect": self.expected_effect,
            "created_at": self.created_at,
        }


@dataclass
class RecoveryRun:
    """Audit record of a recovery attempt."""
    recovery_id: str
    project_id: str
    attempt_number: int
    diagnostic: RuntimeDiagnostic
    repair_plan: RepairPlan
    gate_decision: PreflightGateDecision
    was_applied: bool = False
    was_successful: bool = False
    rolled_back: bool = False
    rollback_reason: Optional[str] = None
    duration_ms: float = 0.0
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "recovery_id": self.recovery_id,
            "project_id": self.project_id,
            "attempt_number": self.attempt_number,
            "diagnostic": self.diagnostic.to_dict(),
            "repair_plan": self.repair_plan.to_dict(),
            "gate_decision": self.gate_decision.value,
            "was_applied": self.was_applied,
            "was_successful": self.was_successful,
            "rolled_back": self.rolled_back,
            "rollback_reason": self.rollback_reason,
            "duration_ms": round(self.duration_ms, 2),
            "timestamp": self.timestamp,
        }


@dataclass
class FailureFingerprint:
    """Deterministic hash fingerprint for deduplication and memory retrieval."""
    runtime: str
    error_class: str
    file_name: str
    line: Optional[int]
    symbol: Optional[str]
    normalized_message: str

    def compute_fingerprint(self) -> str:
        data = {
            "rt": self.runtime,
            "err": self.error_class,
            "f": self.file_name,
            "l": self.line,
            "sym": self.symbol,
            "msg": self.normalized_message.strip().lower(),
        }
        return compute_deterministic_hash(data, prefix="fp_")
