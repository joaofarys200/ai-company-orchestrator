from __future__ import annotations

import asyncio
import hashlib
import importlib.util
import json
import logging
import os
import re
import signal
import socket
import subprocess
import sys
import threading
import time
import unicodedata
import urllib.error
import urllib.request
import uuid
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Awaitable, Callable

from dotenv import dotenv_values

try:
    import tree_sitter_javascript as tsjavascript
    from tree_sitter import Language as TreeSitterLanguage, Parser as TreeSitterParser
except ImportError:  # pragma: no cover - exercised by the conservative fallback path
    tsjavascript = None
    TreeSitterLanguage = None
    TreeSitterParser = None

from agents import tools as ag_tools
from agents.orchestrator.flight_recorder import (
    NoOpFlightRecorder,
    ProjectBuilderFlightRecorder,
    recorder_directory,
)
from backend.model_harness import (
    ContextBuildRequest,
    ContextBuilder,
    ContextCandidate,
    ExecutionConstraints,
    ExpectedOutput,
    ModelHarness,
    ModelPreferences,
    ModelRequest,
    ModelResponseStatus,
    OllamaChatProvider,
    OllamaExecutionOptions,
    OllamaIncompleteResponseError,
    OllamaModelNotFoundError,
    OllamaOutputLimitError,
    OllamaProviderResponseError,
    OllamaStructuredOutputUnsupportedError,
    OutputFormat,
    create_runtime_model_harness,
    get_model_harness,
)
from intelligence.project_context import ProjectContextService


PlanRequester = Callable[[str, str | None], Awaitable[str] | str | dict[str, Any]]
FileCallback = Callable[[str, str], None]
LogCallback = Callable[[str], None]
logger = logging.getLogger(__name__)

PROJECT_ROOT_REL = "workspace/projects"
MAX_FILES = 40
MAX_FILE_BYTES = 250_000
PROJECT_COMMAND_DENYLIST = [
    r"\bnpm\s+install\b",
    r"\bpnpm\s+install\b",
    r"\byarn\s+install\b",
    r"\bpython\s+-m\s+http\.server\b",
    r"\bhttp-server\b",
    r"\bnpm\s+run\s+dev\b",
    r"\bvite\b",
    r"\bflask\s+run\b",
    r"\buvicorn\b",
]
NODE_BUILTINS = {
    "assert", "buffer", "child_process", "crypto", "events", "fs", "http", "https",
    "net", "os", "path", "querystring", "stream", "string_decoder", "timers", "url",
    "util", "worker_threads", "zlib",
}
PLAN_PROVIDER = "ollama"
PLAN_MAX_ATTEMPTS = 2
PLAN_RETRYABLE_CATEGORIES = {
    "OLLAMA_UNAVAILABLE", "MODEL_LOAD_TIMEOUT", "PLAN_READ_TIMEOUT", "PLAN_HTTP_ERROR",
}
COMMAND_TIMEOUT_DEFAULTS = {
    "SETUP": 120.0,
    "TEST": 60.0,
    "BUILD": 120.0,
    "SYNTAX": 60.0,
    "ENTRYPOINT": 15.0,
    "PREVIEW_START": 15.0,
    "HEALTHCHECK": 10.0,
    "PREVIEW": 15.0,
}
PROJECT_BUILD_PHASES = {
    "PLANNING",
    "PLAN_VALIDATED",
    "MATERIALIZING",
    "ARTIFACTS_CREATED",
    "PRE_VALIDATION",
    "SETTING_UP",
    "VALIDATING",
    "STARTING_PREVIEW",
    "WAITING_HEALTHCHECK",
    "TECHNICALLY_VALIDATED",
    "VALIDATION_FAILED",
    "INTERRUPTED",
}
PROJECT_PLAN_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additional_properties": False,
    "properties": {
        "project_name": {"type": "string", "required": True, "non_empty": True},
        "stack": {"type": "string", "required": True, "non_empty": True},
        "components": {
            "type": "array[string]",
            "required": False,
            "default": [],
            "allowed_items": ["frontend", "backend", "persistence", "tests", "preview"],
        },
        "files": {
            "type": "array[object]",
            "required": True,
            "min_items": 1,
            "max_items": MAX_FILES,
            "item_schema": {
                "type": "object",
                "additional_properties": False,
                "properties": {
                    "path": {"type": "string", "required": True, "non_empty": True},
                    "content": {"type": "string", "required": True},
                },
            },
        },
        "dependencies": {"type": "array[string]", "required": False, "default": []},
        "setup_commands": {"type": "array[string]", "required": False, "default": []},
        "validation_commands": {"type": "array[string]", "required": False, "default": []},
        "entrypoints": {"type": "array[string]", "required": False, "default": []},
        "preview_strategy": {
            "type": "object",
            "required": False,
            "default": {},
            "additional_properties": True,
        },
        "preview_command": {"type": "string", "required": False, "default": ""},
        "constraints": {"type": "array[string]", "required": False, "default": []},
        "component_files": {
            "type": "object[array[string]]",
            "required": False,
            "default": {},
        },
        "rationale": {"type": "string", "required": False, "default": ""},
    },
}
FOCAL_CORRECTION_PROTOCOL = "project_builder_focal_correction_v2"
FOCAL_CORRECTION_SCHEMA_VERSION = "project_builder_focal_correction_schema_v2"
FOCAL_CORRECTION_RESPONSE_KEYS = {"plan_updates", "replacements"}
FOCAL_PLAN_UPDATE_FIELDS_BY_ERROR: dict[str, set[str]] = {
    "MISSING_REQUESTED_COMPONENTS": {"components"},
    "MISSING_COMPONENT_MAPPING": {"component_files"},
    "MAPPED_FILE_NOT_FOUND": {"component_files"},
    "DECLARED_COMPONENT_WITHOUT_ARTIFACTS": {"component_files"},
    "PERSISTENCE_NOT_IMPLEMENTED": {"component_files"},
    "MISSING_ENTRYPOINTS": {"entrypoints"},
    "MISSING_VALIDATION_COMMANDS": {"validation_commands"},
    "MISSING_PREVIEW_IMPLEMENTATION": {"preview_command", "preview_strategy"},
    "MISSING_DECLARED_DEPENDENCY": {"dependencies"},
}

_preview_processes: list[subprocess.Popen] = []
_owned_process_registry: dict[int, dict[str, Any]] = {}


class ProjectBuilderError(Exception):
    pass


class ProjectBuilderValidationPlanError(ProjectBuilderError):
    def __init__(self, errors: list[dict[str, Any]], journal_path: str):
        self.errors = errors
        self.journal_path = journal_path
        summary = {
            "category": "VALIDATION_PLAN_INVALID",
            "errors": errors,
            "journal_path": journal_path,
        }
        super().__init__(f"ProjectBuilder validation plan failed: {json.dumps(summary, ensure_ascii=True)}")


class ProjectBuilderInternalError(ProjectBuilderError):
    category = "INTERNAL_ERROR"

    def __init__(self, message: str, cause: Exception | None = None):
        self.primary_error = {
            "type": type(cause).__name__ if cause is not None else type(self).__name__,
            "message": _sanitize_persisted_output(str(cause or message)),
        }
        super().__init__(message)


class ProjectBuilderInterruptedError(ProjectBuilderError):
    pass


@dataclass(frozen=True)
class PlanValidationIssue:
    code: str
    field_path: str
    message: str
    expected_type: str = ""
    received_type: str = ""
    offending_value: str = ""
    repairable: bool = False
    suggestion: str = ""
    phase: str = "PLAN_SEMANTIC_VALIDATION"
    file: str = ""
    line: int | None = None
    symbol: str = ""
    target: str = ""
    expected: str = ""
    actual: str = ""
    component: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ProjectPlanValidationError(ProjectBuilderError):
    def __init__(self, category: str, issues: list[PlanValidationIssue]):
        self.category = category
        self.issues = issues
        messages = "; ".join(issue.message for issue in issues[:5])
        super().__init__(messages or "O plano e invalido.")


class ProjectBuilderPlanningError(ProjectBuilderError):
    def __init__(self, category: str, sanitized_message: str, diagnostics: dict[str, Any]):
        self.category = category
        self.sanitized_message = sanitized_message
        self.diagnostics = diagnostics
        summary = {
            "category": category,
            "provider": diagnostics.get("provider"),
            "model": diagnostics.get("model"),
            "attempt_count": diagnostics.get("attempt_count"),
            "durations": diagnostics.get("durations"),
            "timeout_config": diagnostics.get("timeout_config"),
            "prompt_length": diagnostics.get("prompt_length"),
            "attempts": diagnostics.get("attempts"),
            "readiness": diagnostics.get("readiness"),
            "first_error": diagnostics.get("first_error"),
            "final_error": diagnostics.get("final_error"),
            "final_validation": diagnostics.get("final_validation"),
            "correction_prompt_sha256": diagnostics.get("correction_prompt_sha256"),
            "base_prompt_length": diagnostics.get("base_prompt_length"),
            "correction_prompt_length": diagnostics.get("correction_prompt_length"),
            "effective_prompt_length": diagnostics.get("effective_prompt_length"),
            "correction_error_count": diagnostics.get("correction_error_count"),
            "correction_files_sent_count": diagnostics.get("correction_files_sent_count"),
            "correction_replacements_received": diagnostics.get("correction_replacements_received"),
            "correction_replacements_applied": diagnostics.get("correction_replacements_applied"),
            "correction_plan_update_fields": diagnostics.get("correction_plan_update_fields"),
            "correction_manifest_verified": diagnostics.get("correction_manifest_verified"),
            "correction_rejection_reason": diagnostics.get("correction_rejection_reason"),
            "sanitized_message": sanitized_message,
        }
        super().__init__(f"ProjectBuilder planning failed: {json.dumps(summary, ensure_ascii=True)}")


@dataclass(frozen=True)
class PlanTimeoutConfig:
    connect: float = 5.0
    read: float = 300.0
    write: float = 15.0
    pool: float = 5.0

    def to_dict(self) -> dict[str, float]:
        return asdict(self)


@dataclass
class PlanAttemptRecord:
    attempt: int
    phase: str
    duration: float
    prompt_length: int
    status: str
    error_type: str = ""
    error_category: str = ""
    retry_reason: str = ""
    response_length: int = 0
    partial_response: bool = False
    raw_response_length: int = 0
    parse_status: str = "NOT_PROCESSED"
    local_repairs: list[dict[str, Any]] = field(default_factory=list)
    schema_errors: list[dict[str, Any]] = field(default_factory=list)
    semantic_errors: list[dict[str, Any]] = field(default_factory=list)
    security_errors: list[dict[str, Any]] = field(default_factory=list)
    correction_errors: list[dict[str, Any]] = field(default_factory=list)
    corrected_by_model: bool = False
    final_plan_hash: str = ""
    base_prompt_length: int = 0
    correction_prompt_length: int = 0
    effective_prompt_length: int = 0
    structured_output_enabled: bool = False
    correction_schema_sha256: str = ""
    correction_schema_length: int = 0
    correction_schema_version: str = ""
    streaming_enabled: bool = True


@dataclass(frozen=True)
class _OllamaGenerationContract:
    response_format: str | dict[str, Any]
    structured_output_enabled: bool = False
    correction_schema_sha256: str = ""
    correction_schema_length: int = 0
    correction_schema_version: str = ""
    streaming_enabled: bool = True


class _PlanAttemptFailure(Exception):
    def __init__(
        self,
        category: str,
        message: str,
        *,
        retryable: bool,
        error_type: str = "",
        partial_response: bool = False,
    ):
        super().__init__(message)
        self.category = category
        self.message = message
        self.retryable = retryable
        self.error_type = error_type or category
        self.partial_response = partial_response


class _PlanValidationFailure(Exception):
    def __init__(
        self,
        category: str,
        cause: Exception,
        *,
        raw_response_length: int = 0,
        parse_status: str = "FAILED",
        local_repairs: list[dict[str, Any]] | None = None,
        errors: list[PlanValidationIssue] | None = None,
        parsed_plan: dict[str, Any] | None = None,
        virtual_files: list[dict[str, Any]] | None = None,
        static_analysis: dict[str, Any] | None = None,
        error_artifact_mappings: list[dict[str, Any]] | None = None,
        correction_manifest: list[dict[str, Any]] | None = None,
        correction_effectiveness: dict[str, Any] | None = None,
    ):
        super().__init__(str(cause))
        self.category = category
        self.cause = cause
        self.raw_response_length = raw_response_length
        self.parse_status = parse_status
        self.local_repairs = list(local_repairs or [])
        self.errors = list(errors or [])
        self.parsed_plan = parsed_plan
        self.virtual_files = list(virtual_files or [])
        self.static_analysis = deepcopy(static_analysis or {})
        self.error_artifact_mappings = deepcopy(error_artifact_mappings or [])
        self.correction_manifest = deepcopy(correction_manifest or [])
        self.correction_effectiveness = deepcopy(correction_effectiveness or {})


@dataclass
class _ProcessedProjectPlan:
    plan: "ProjectPlan"
    normalized_data: dict[str, Any]
    raw_response_length: int
    parse_status: str
    local_repairs: list[dict[str, Any]]
    final_plan_hash: str
    virtual_files: list[dict[str, Any]] = field(default_factory=list)
    static_analysis: dict[str, Any] = field(default_factory=dict)
    error_artifact_mappings: list[dict[str, Any]] = field(default_factory=list)
    correction_manifest: list[dict[str, Any]] = field(default_factory=list)
    correction_effectiveness: dict[str, Any] = field(default_factory=dict)


@dataclass
class ProjectCreationIntent:
    is_creation_request: bool
    confidence: float
    creation_signals: list[str] = field(default_factory=list)
    negative_constraints: list[str] = field(default_factory=list)
    excluded_targets: list[str] = field(default_factory=list)
    rejection_reason: str | None = None
    compound_intent: bool = False
    separate_work: list[str] = field(default_factory=list)


@dataclass
class ProjectFile:
    path: str
    content: str


@dataclass(frozen=True)
class PlannedFile:
    normalized_path: str
    content: str
    component: str
    language: str
    extension: str
    content_hash: str


@dataclass
class PlannedFileSystem:
    files: dict[str, PlannedFile]
    source_kind: str = "planned"
    warnings: list[PlanValidationIssue] = field(default_factory=list)

    @classmethod
    def from_plan_data(cls, data: dict[str, Any]) -> "PlannedFileSystem":
        component_by_path: dict[str, str] = {}
        for component, paths in (data.get("component_files") or {}).items():
            for path in paths:
                component_by_path[_normalize_relative_path_syntax(str(path))] = str(component)
        planned: dict[str, PlannedFile] = {}
        for item in data.get("files") or []:
            path = _normalize_relative_path_syntax(str(item.get("path") or ""))
            content = str(item.get("content") or "")
            extension = Path(path).suffix.lower()
            planned[path] = PlannedFile(
                normalized_path=path,
                content=content,
                component=component_by_path.get(path, ""),
                language=_language_for_extension(extension),
                extension=extension,
                content_hash=hashlib.sha256(content.encode("utf-8")).hexdigest(),
            )
        return cls(files=planned, source_kind="planned")

    @classmethod
    def from_materialized_project(
        cls,
        project_dir: str,
        plan: "ProjectPlan",
    ) -> "PlannedFileSystem":
        component_by_path = {
            _normalize_relative_path_syntax(path): component
            for component, paths in plan.component_files.items()
            for path in paths
        }
        files: dict[str, PlannedFile] = {}
        warnings: list[PlanValidationIssue] = []
        expected_paths = list(dict.fromkeys(item.path for item in plan.files))
        for relative in expected_paths:
            normalized = _normalize_relative_path_syntax(relative)
            path = Path(project_dir, *PurePosixPath(normalized).parts)
            if not path.is_file():
                continue
            try:
                content = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as exc:
                warnings.append(PlanValidationIssue(
                    code="ARTIFACT_READ_WARNING",
                    field_path=f"files[{normalized}]",
                    message=f"Nao foi possivel analisar {normalized}: {type(exc).__name__}.",
                    file=normalized,
                    phase="PRE_VALIDATION",
                    suggestion="Verifica se o ficheiro e texto UTF-8 legivel.",
                ))
                continue
            extension = path.suffix.lower()
            files[normalized] = PlannedFile(
                normalized_path=normalized,
                content=content,
                component=component_by_path.get(normalized, ""),
                language=_language_for_extension(extension),
                extension=extension,
                content_hash=hashlib.sha256(content.encode("utf-8")).hexdigest(),
            )
        return cls(files=files, source_kind="materialized", warnings=warnings)

    def exists(self, path: str) -> bool:
        return _normalize_relative_path_syntax(path) in self.files

    def get(self, path: str) -> PlannedFile | None:
        return self.files.get(_normalize_relative_path_syntax(path))

    def metadata(self) -> list[dict[str, Any]]:
        return [
            {
                "normalized_path": item.normalized_path,
                "component": item.component,
                "language": item.language,
                "extension": item.extension,
                "content_hash": item.content_hash,
                "size_bytes": len(item.content.encode("utf-8")),
            }
            for item in sorted(self.files.values(), key=lambda value: value.normalized_path)
        ]

    def hashes(self) -> dict[str, str]:
        return {
            item.normalized_path: item.content_hash
            for item in sorted(self.files.values(), key=lambda value: value.normalized_path)
        }


@dataclass(frozen=True)
class SemanticErrorArtifactMapping:
    code: str
    message: str
    affected_artifacts: list[str] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)
    required_postconditions: list[str] = field(default_factory=list)
    content_dependent: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CorrectionEffectivenessResult:
    valid: bool
    errors: list[PlanValidationIssue] = field(default_factory=list)
    error_artifact_mappings: list[dict[str, Any]] = field(default_factory=list)
    correction_manifest: list[dict[str, Any]] = field(default_factory=list)
    hashes_before: dict[str, str] = field(default_factory=dict)
    hashes_after: dict[str, str] = field(default_factory=dict)
    changed_artifacts: list[str] = field(default_factory=list)
    unchanged_affected_artifacts: list[str] = field(default_factory=list)
    protocol: str = "complete_plan_v1"
    plan_updates: dict[str, Any] = field(default_factory=dict)
    allowed_plan_updates: list[str] = field(default_factory=list)
    allowed_replacements: list[str] = field(default_factory=list)
    replacements_received: int = 0
    replacements_applied: int = 0
    manifest_verified: bool = False
    revalidation: dict[str, Any] = field(default_factory=dict)
    rejection_reason: str = ""
    model_manifest_accepted: bool = False
    derived_changed_plan_fields: list[str] = field(default_factory=list)
    derived_changed_files: list[str] = field(default_factory=list)
    unchanged_replacements: list[str] = field(default_factory=list)
    error_resolution_statuses: dict[str, str] = field(default_factory=dict)
    revalidation_executed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "errors": [item.to_dict() for item in self.errors],
            "error_artifact_mappings": deepcopy(self.error_artifact_mappings),
            "correction_manifest": deepcopy(self.correction_manifest),
            "hashes_before": dict(self.hashes_before),
            "hashes_after": dict(self.hashes_after),
            "changed_artifacts": list(self.changed_artifacts),
            "unchanged_affected_artifacts": list(self.unchanged_affected_artifacts),
            "protocol": self.protocol,
            "plan_updates": deepcopy(self.plan_updates),
            "plan_update_fields": sorted(self.plan_updates),
            "allowed_plan_updates": list(self.allowed_plan_updates),
            "allowed_replacements": list(self.allowed_replacements),
            "replacements_received": self.replacements_received,
            "replacements_applied": self.replacements_applied,
            "manifest_verified": self.manifest_verified,
            "revalidation": deepcopy(self.revalidation),
            "rejection_reason": self.rejection_reason,
            "focal_protocol_version": self.protocol,
            "model_manifest_accepted": self.model_manifest_accepted,
            "derived_changed_plan_fields": list(self.derived_changed_plan_fields),
            "derived_changed_files": list(self.derived_changed_files),
            "unchanged_replacements": list(self.unchanged_replacements),
            "error_resolution_statuses": dict(self.error_resolution_statuses),
            "revalidation_executed": self.revalidation_executed,
        }


@dataclass
class StaticAnalysisResult:
    errors: list[PlanValidationIssue] = field(default_factory=list)
    warnings: list[PlanValidationIssue] = field(default_factory=list)
    checked_components: list[str] = field(default_factory=list)
    checked_entrypoints: list[str] = field(default_factory=list)
    checked_scripts: list[str] = field(default_factory=list)
    checked_dependencies: list[str] = field(default_factory=list)
    virtual_files: list[dict[str, Any]] = field(default_factory=list)

    @property
    def valid(self) -> bool:
        return not self.errors

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "errors": [item.to_dict() for item in self.errors],
            "warnings": [item.to_dict() for item in self.warnings],
            "checked_components": list(self.checked_components),
            "checked_entrypoints": list(self.checked_entrypoints),
            "checked_scripts": list(self.checked_scripts),
            "checked_dependencies": list(self.checked_dependencies),
            "virtual_files": deepcopy(self.virtual_files),
        }


@dataclass
class ProjectPlan:
    project_name: str
    stack: str
    files: list[ProjectFile]
    validation_commands: list[str] = field(default_factory=list)
    preview_command: str = ""
    components: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    setup_commands: list[str] = field(default_factory=list)
    entrypoints: list[str] = field(default_factory=list)
    preview_strategy: dict[str, Any] = field(default_factory=dict)
    component_files: dict[str, list[str]] = field(default_factory=dict)
    constraints: list[str] = field(default_factory=list)
    rationale: str = ""
    planning_diagnostics: dict[str, Any] = field(default_factory=dict)
    normalized_data: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass
class ValidationCheck:
    check_id: str
    command: str
    working_directory: str
    category: str
    required: bool
    source: str
    timeout: float
    component: str = ""
    status: str = "PENDING"
    reason: str = ""
    result: dict[str, Any] | None = None
    evidence_eligible: bool = True


@dataclass
class ValidationPlan:
    setup_commands: list[ValidationCheck] = field(default_factory=list)
    validation_commands: list[ValidationCheck] = field(default_factory=list)
    entrypoint_checks: list[ValidationCheck] = field(default_factory=list)
    preview_checks: list[ValidationCheck] = field(default_factory=list)
    required_components: list[str] = field(default_factory=list)
    optional_checks: list[ValidationCheck] = field(default_factory=list)
    blocked_commands: list[dict[str, Any]] = field(default_factory=list)
    skipped_commands: list[dict[str, Any]] = field(default_factory=list)
    rationale: str = ""
    requested_components: list[str] = field(default_factory=list)
    promised_components: list[str] = field(default_factory=list)
    materialized_components: list[str] = field(default_factory=list)
    validated_components: list[str] = field(default_factory=list)
    missing_components: list[str] = field(default_factory=list)
    missing_dependencies: list[str] = field(default_factory=list)
    failed_checks: list[str] = field(default_factory=list)
    skipped_required_checks: list[str] = field(default_factory=list)
    technical_evidence: list[dict[str, Any]] = field(default_factory=list)
    suggested_fix: str = ""
    success: bool = False
    static_errors: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class PreValidationResult:
    valid: bool
    errors: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[dict[str, Any]] = field(default_factory=list)
    checked_components: list[str] = field(default_factory=list)
    checked_entrypoints: list[str] = field(default_factory=list)
    checked_scripts: list[str] = field(default_factory=list)
    checked_dependencies: list[str] = field(default_factory=list)
    blocked_commands: list[dict[str, Any]] = field(default_factory=list)
    suggested_fixes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CommandResult:
    command: str
    ok: bool
    output: str
    working_directory: str = ""
    exit_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    duration: float = 0.0
    timed_out: bool = False
    category: str = "SYNTAX"
    required: bool = True
    source: str = "ProjectBuilder"
    status: str = "PENDING"
    error_category: str = ""
    command_id: str = ""
    process_id: int | None = None
    termination_confirmed: bool | None = None
    process_started: bool = False
    termination_attempted: bool = False
    termination_succeeded: bool | None = None
    descendant_count: int = 0
    stdout_truncated: bool = False
    stderr_truncated: bool = False
    cleanup_completed: bool = False
    cleanup_errors: list[str] = field(default_factory=list)


@dataclass
class SkippedCommand:
    command: str
    reason: str


@dataclass
class ProjectBuildResult:
    project_name: str
    project_dir: str
    project_rel_dir: str
    files_created: list[str]
    commands_executed: list[CommandResult]
    commands_skipped: list[SkippedCommand]
    preview_url: str = ""
    preview_started: bool = False
    obsidian_used: bool = False
    validation_plan: dict[str, Any] = field(default_factory=dict)
    technical_success: bool = False
    missing_components: list[str] = field(default_factory=list)
    failed_checks: list[str] = field(default_factory=list)
    blocked_checks: list[str] = field(default_factory=list)
    skipped_required_checks: list[str] = field(default_factory=list)
    suggested_fix: str = ""
    creation_intent: dict[str, Any] = field(default_factory=dict)
    planning_diagnostics: dict[str, Any] = field(default_factory=dict)
    build_run_id: str = ""
    progress_path: str = ""
    progress_state: dict[str, Any] = field(default_factory=dict)
    status: str = ""
    error_category: str = ""
    validation_errors: list[dict[str, Any]] = field(default_factory=list)
    pre_validation: dict[str, Any] = field(default_factory=dict)
    completion_reason: str = ""
    flight_recorder_path: str = ""

    def report(self) -> str:
        files = "\n".join(f"- {path}" for path in self.files_created) or "- nenhum"
        executed = "\n".join(
            f"- {'OK' if item.ok else 'FALHOU'}: {item.command}" for item in self.commands_executed
        ) or "- nenhum"
        skipped = "\n".join(
            f"- {item.command}: {item.reason}" for item in self.commands_skipped
        ) or "- nenhum"
        preview = self.preview_url if self.preview_url else "nao iniciado"
        status = "[OK]" if self.technical_success else "[VALIDATION_FAILED]"
        return (
            f"{status} Projeto criado pelo Project Builder.\n"
            f"Pasta: {self.project_rel_dir}\n"
            f"Preview: {preview}\n"
            f"Obsidian usado: {'sim' if self.obsidian_used else 'nao'}\n\n"
            "Ficheiros criados:\n"
            f"{files}\n\n"
            "Comandos executados:\n"
            f"{executed}\n\n"
            "Comandos ignorados:\n"
            f"{skipped}"
        )


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sanitize_persisted_output(value: Any, limit: int = 4000) -> str:
    text = str(value or "")
    text = re.sub(
        r"(?i)(authorization\s*:\s*bearer\s+|api[_-]?key\s*[=:]\s*|token\s*[=:]\s*)\S+",
        r"\1[REDACTED]",
        text,
    )
    return text[:limit]


class ProjectBuildJournal:
    def __init__(self, run_id: str | None = None):
        self.run_id = run_id or uuid.uuid4().hex
        self.relative_path = f"workspace/.jarvis/project_builder/runs/{self.run_id}.json"
        self.path = Path(ag_tools.resolve_workspace_path(self.relative_path))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self.flight_recorder = None
        now = _utc_timestamp()
        self.state: dict[str, Any] = {
            "run_id": self.run_id,
            "status": "RUNNING",
            "current_phase": "PLANNING",
            "current_command_id": "",
            "last_heartbeat_at": now,
            "last_completed_step": "",
            "interruption_reason": "",
            "started_at": now,
            "updated_at": now,
            "project_name": "",
            "project_rel_dir": "",
            "plan_hash": "",
            "normalized_plan_hash": "",
            "normalized_plan": None,
            "local_repairs": [],
            "planning_diagnostics": {},
            "planning_validation_history": [],
            "virtual_files": [],
            "validation_plan": None,
            "requested_components": [],
            "promised_components": [],
            "expected_files": [],
            "materialized_files": [],
            "artifacts_created": [],
            "pre_validation": None,
            "static_analysis_results": None,
            "validation_errors": [],
            "commands_executed": [],
            "technical_success": None,
            "completion_reason": "",
            "commands": [],
            "processes": [],
            "errors": [],
        }
        self._persist()

    @classmethod
    def from_path(cls, path: str | os.PathLike[str]) -> "ProjectBuildJournal":
        instance = cls.__new__(cls)
        instance.path = Path(path).resolve()
        instance.relative_path = os.path.relpath(
            instance.path, Path(ag_tools.resolve_workspace_path("."))
        ).replace(os.sep, "/")
        instance._lock = threading.RLock()
        instance.flight_recorder = None
        instance.state = json.loads(instance.path.read_text(encoding="utf-8"))
        instance.run_id = str(instance.state["run_id"])
        return instance

    def _persist(self) -> None:
        with self._lock:
            self.state["updated_at"] = _utc_timestamp()
            recorder = self.flight_recorder
            if recorder is not None:
                recorder.event(
                    "journal_write_started",
                    phase="JOURNAL",
                    metadata={"path": self.relative_path},
                )
            temporary = self.path.with_name(f".{self.path.name}.{uuid.uuid4().hex}.tmp")
            payload = json.dumps(self.state, ensure_ascii=False, indent=2)
            try:
                with open(temporary, "w", encoding="utf-8", newline="\n") as handle:
                    handle.write(payload)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temporary, self.path)
            finally:
                if temporary.exists():
                    temporary.unlink()
                if recorder is not None:
                    recorder.event(
                        "journal_write_completed",
                        phase="JOURNAL",
                        status="COMPLETED" if self.path.is_file() else "FAILED",
                        metadata={"path": self.relative_path, "persisted": self.path.is_file()},
                    )

    def attach_flight_recorder(self, recorder: Any) -> None:
        with self._lock:
            self.flight_recorder = recorder

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return deepcopy(self.state)

    def heartbeat(self) -> None:
        with self._lock:
            self.state["last_heartbeat_at"] = _utc_timestamp()
            self._persist()

    def transition(self, phase: str, *, completed_step: str = "") -> None:
        if phase not in PROJECT_BUILD_PHASES:
            raise ProjectBuilderError(f"Fase ProjectBuilder desconhecida: {phase}")
        with self._lock:
            self.state["current_phase"] = phase
            self.state["last_heartbeat_at"] = _utc_timestamp()
            if completed_step:
                self.state["last_completed_step"] = completed_step
            if phase == "TECHNICALLY_VALIDATED":
                self.state["status"] = "SUCCEEDED"
                self.state["technical_success"] = True
                self.state["completion_reason"] = "TECHNICALLY_VALIDATED"
            elif phase == "VALIDATION_FAILED":
                self.state["status"] = "FAILED"
                self.state["technical_success"] = False
                self.state["completion_reason"] = "VALIDATION_FAILED"
            elif phase == "INTERRUPTED":
                self.state["status"] = "INTERRUPTED"
            self._persist()

    def record_plan(
        self,
        plan: ProjectPlan,
        validation_plan: ValidationPlan,
        project_rel_dir: str,
    ) -> None:
        with self._lock:
            diagnostics = deepcopy(plan.planning_diagnostics)
            normalized_plan_hash = diagnostics.get("final_plan_hash") or _plan_hash(plan.normalized_data)
            self.state.update({
                "project_name": plan.project_name,
                "project_rel_dir": project_rel_dir,
                "plan_hash": normalized_plan_hash,
                "normalized_plan_hash": normalized_plan_hash,
                "normalized_plan": deepcopy(plan.normalized_data),
                "local_repairs": deepcopy(diagnostics.get("local_repairs") or []),
                "planning_diagnostics": diagnostics,
                "validation_plan": asdict(validation_plan),
                "requested_components": list(validation_plan.requested_components),
                "promised_components": list(validation_plan.promised_components),
                "expected_files": [item.path for item in plan.files],
                "commands": [
                    {
                        "command_id": item.check_id,
                        "command": item.command,
                        "working_directory": item.working_directory,
                        "category": item.category,
                        "required": item.required,
                        "timeout": item.timeout,
                        "status": "PENDING",
                        "started_at": None,
                        "completed_at": None,
                    }
                    for item in (
                        validation_plan.setup_commands
                        + validation_plan.validation_commands
                        + validation_plan.entrypoint_checks
                        + validation_plan.preview_checks
                    )
                ],
            })
            self.transition("PLAN_VALIDATED", completed_step="plan_and_validation_plan_persisted")

    def record_planning_failure(self, error: ProjectBuilderPlanningError) -> None:
        with self._lock:
            diagnostics = deepcopy(error.diagnostics)
            final_validation = deepcopy(diagnostics.get("final_validation") or {})
            validation_errors = _planning_errors_from_diagnostics(diagnostics, error.category)
            analysis = deepcopy(final_validation.get("static_analysis") or {})
            if not analysis and error.category == "PLAN_CORRECTION_FAILED":
                analysis = next((
                    deepcopy(item.get("static_analysis") or {})
                    for item in diagnostics.get("validation_history") or []
                    if item.get("static_analysis")
                ), {})
            self.state.update({
                "status": "VALIDATION_FAILED",
                "current_phase": "PLANNING",
                "last_completed_step": "planning_validation_failed",
                "planning_diagnostics": diagnostics,
                "planning_validation_history": deepcopy(diagnostics.get("validation_history") or []),
                "virtual_files": deepcopy(final_validation.get("virtual_files") or []),
                "static_analysis_results": analysis,
                "validation_errors": validation_errors,
                "materialized_files": [],
                "artifacts_created": [],
                "commands_executed": [],
                "technical_success": False,
                "completion_reason": error.category,
            })
            self.state["errors"].extend(deepcopy(validation_errors or [{
                "category": error.category,
                "phase": "PLANNING",
                "message": error.sanitized_message,
                "suggested_fix": "Corrige o plano antes de o materializar.",
                "retryable": False,
            }]))
            self._persist()

    def record_artifacts(self, files: list[dict[str, Any]]) -> None:
        with self._lock:
            self.state["materialized_files"] = deepcopy(files)
            self.state["artifacts_created"] = deepcopy(files)
            self.transition("ARTIFACTS_CREATED", completed_step="artifacts_hashed")

    def record_prevalidation(
        self,
        result: PreValidationResult,
        validation_plan: ValidationPlan,
    ) -> None:
        with self._lock:
            result_data = result.to_dict()
            self.state["current_phase"] = "PRE_VALIDATION"
            self.state["last_completed_step"] = (
                "pre_validation_passed" if result.valid else "pre_validation_failed"
            )
            self.state["validation_plan"] = asdict(validation_plan)
            self.state["pre_validation"] = result_data
            self.state["static_analysis_results"] = result_data
            self.state["validation_errors"] = deepcopy(result.errors)
            self.state["commands_executed"] = []
            if not result.valid:
                self.state["status"] = "VALIDATION_FAILED"
                self.state["technical_success"] = False
                self.state["completion_reason"] = "PRE_VALIDATION_FAILED"
                self.state["errors"].extend(deepcopy(result.errors))
            self._persist()

    def record_validation_snapshot(self, validation_plan: ValidationPlan) -> None:
        with self._lock:
            self.state["validation_plan"] = asdict(validation_plan)
            self._persist()

    def _command(self, command_id: str) -> dict[str, Any]:
        for item in self.state["commands"]:
            if item["command_id"] == command_id:
                return item
        item = {"command_id": command_id, "status": "PENDING"}
        self.state["commands"].append(item)
        return item

    def command_started(self, check: ValidationCheck) -> None:
        with self._lock:
            item = self._command(check.check_id)
            item.update({
                "command": check.command,
                "working_directory": check.working_directory,
                "category": check.category,
                "required": check.required,
                "timeout": check.timeout,
                "status": "RUNNING",
                "started_at": _utc_timestamp(),
                "completed_at": None,
            })
            self.state["current_command_id"] = check.check_id
            self.state["last_heartbeat_at"] = _utc_timestamp()
            self._persist()

    def process_started(self, command_id: str, pid: int, purpose: str, process_group: str = "") -> None:
        with self._lock:
            self.state["processes"].append({
                "pid": pid,
                "process_group": process_group,
                "command_id": command_id,
                "started_at": _utc_timestamp(),
                "purpose": purpose,
                "status": "RUNNING",
                "termination_confirmed": None,
            })
            self._command(command_id)["pid"] = pid
            self._persist()

    def process_finished(self, command_id: str, pid: int, *, termination_confirmed: bool | None) -> None:
        with self._lock:
            for item in reversed(self.state["processes"]):
                if item["command_id"] == command_id and item["pid"] == pid:
                    item["status"] = "TERMINATED" if termination_confirmed else "EXITED"
                    item["termination_confirmed"] = termination_confirmed
                    item["completed_at"] = _utc_timestamp()
                    break
            self._persist()

    def command_completed(self, command_id: str, result: CommandResult) -> None:
        with self._lock:
            item = self._command(command_id)
            item.update({
                "status": result.status,
                "exit_code": result.exit_code,
                "stdout": _sanitize_persisted_output(result.stdout),
                "stderr": _sanitize_persisted_output(result.stderr),
                "duration": result.duration,
                "timed_out": result.timed_out,
                "error_category": result.error_category,
                "completed_at": _utc_timestamp(),
                "termination_confirmed": result.termination_confirmed,
            })
            self.state["current_command_id"] = ""
            self.state.setdefault("commands_executed", []).append({
                "command_id": command_id,
                "command": result.command,
                "status": result.status,
                "exit_code": result.exit_code,
                "error_category": result.error_category,
            })
            self.state["last_completed_step"] = command_id
            self.state["last_heartbeat_at"] = _utc_timestamp()
            self._persist()

    def record_errors(self, errors: list[dict[str, Any]], phase: str = "VALIDATION_FAILED") -> None:
        with self._lock:
            self.state["errors"].extend(deepcopy(errors))
            self.transition(phase, completed_step="errors_persisted")

    def interrupt(self, reason: str, error: dict[str, Any]) -> None:
        with self._lock:
            self.state["interruption_reason"] = reason
            self.state["errors"].append(deepcopy(error))
            self.state["current_command_id"] = ""
            self.transition("INTERRUPTED", completed_step="interruption_recovered")


class _JournalHeartbeat:
    def __init__(self, journal: ProjectBuildJournal | None, interval: float = 2.0):
        self.journal = journal
        self.interval = interval
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def __enter__(self):
        if self.journal is not None:
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()
        return self

    def _run(self):
        while not self._stop.wait(self.interval):
            try:
                self.journal.heartbeat()
            except OSError:
                return

    def __exit__(self, exc_type, exc, tb):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=self.interval + 1.0)


def recover_interrupted_project_build(
    journal_path: str,
    *,
    stale_after_seconds: float = 300.0,
    mission_executor_service: Any | None = None,
    project_id: str = "",
    mission_id: str = "",
    execution_id: str = "",
) -> dict[str, Any]:
    metadata_root = Path(
        ag_tools.resolve_workspace_path("workspace/.jarvis/project_builder/runs")
    ).resolve()
    candidate = Path(journal_path)
    if not candidate.is_absolute():
        candidate = Path(ag_tools.resolve_workspace_path(journal_path))
    candidate = candidate.resolve()
    try:
        if os.path.commonpath([str(metadata_root), str(candidate)]) != str(metadata_root):
            raise ProjectBuilderError("Journal fora da metadata permitida do ProjectBuilder.")
    except ValueError as exc:
        raise ProjectBuilderError("Journal fora da metadata permitida do ProjectBuilder.") from exc
    journal = ProjectBuildJournal.from_path(candidate)
    state = journal.snapshot()
    if state.get("status") != "RUNNING":
        return {"recovered": False, "reason": "build_not_running", "journal": state}
    heartbeat_text = str(state.get("last_heartbeat_at") or state.get("updated_at") or "")
    try:
        heartbeat = datetime.fromisoformat(heartbeat_text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ProjectBuilderError("Journal sem heartbeat valido.") from exc
    age = (datetime.now(timezone.utc) - heartbeat.astimezone(timezone.utc)).total_seconds()
    if age < max(0.0, stale_after_seconds):
        raise ProjectBuilderError(
            f"Build ainda tem heartbeat recente ({age:.1f}s < {stale_after_seconds:.1f}s)."
        )
    alive_owned = [
        int(item["pid"])
        for item in state.get("processes") or []
        if item.get("status") == "RUNNING" and _pid_exists(int(item.get("pid") or 0))
    ]
    if alive_owned:
        raise ProjectBuilderError(
            f"Build ainda tem processos proprios ativos: {alive_owned}."
        )
    error = _validation_static_error(
        "EXECUTION_INTERRUPTED",
        "O ProjectBuilder deixou de atualizar heartbeat e os seus processos ja nao existem.",
        phase="INTERRUPTED",
        command_id=str(state.get("current_command_id") or ""),
        suggested_fix="Rever plano, artefactos e resultados persistidos antes de iniciar nova execucao.",
        retryable=True,
    )
    journal.interrupt("stale_heartbeat_without_owned_process", error)
    snapshot = None
    if mission_executor_service is not None:
        if not all((project_id, mission_id, execution_id)):
            raise ProjectBuilderError("A recuperacao da MissionExecution exige os tres identificadores.")
        snapshot = mission_executor_service._fail_execution(
            project_id,
            mission_id,
            execution_id,
            ProjectBuilderInterruptedError(json.dumps(error, ensure_ascii=True)),
            validation_failed=False,
            output={
                "phase": "INTERRUPTED",
                "project_builder_progress": journal.snapshot(),
                "interruption_reason": "stale_heartbeat_without_owned_process",
            },
        )
    return {
        "recovered": True,
        "category": "STALE_EXECUTION_RECOVERED",
        "journal": journal.snapshot(),
        "mission_snapshot": snapshot,
    }


def normalize_prompt(text: str) -> str:
    replacements = str.maketrans({
        "á": "a", "à": "a", "â": "a", "ã": "a",
        "é": "e", "ê": "e",
        "í": "i",
        "ó": "o", "ô": "o", "õ": "o",
        "ú": "u",
        "ç": "c",
    })
    lowered = (text or "").lower().translate(replacements)
    return "".join(
        character
        for character in unicodedata.normalize("NFKD", lowered)
        if not unicodedata.combining(character)
    )


_CREATION_ACTION_RE = re.compile(
    r"\b(?:cria|criar|crie|cries|constroi|construir|desenvolve|desenvolver|gera|gerar|"
    r"implementa|implementar|inicia|iniciar|faz|fazer|build|create|generate|develop|implement|start)\b"
)
_PROJECT_TARGET_RE = re.compile(
    r"\b(?:full\s+stack|fullstack|ficheiro|arquivo|pagina|site|website|app|aplicacao|projeto|"
    r"frontend|backend|api|dashboard|tarefas|todo|stack)\b|workspace/projects|"
    r"\.(?:txt|html|css|js|ts|py)\b"
)
_STACK_SELECTION_RE = re.compile(r"\b(?:usa|use)\s+(?:uma?\s+)?outra\s+stack\b")
_NEGATION_MARKER_RE = re.compile(
    r"\b(?:nao|sem|evita|evitar|avoid|without|never)\b|\bdo\s+not\b|\bdon't\b"
)
_NEGATED_CREATION_RE = re.compile(
    r"\b(?:nao|never)\s+(?:\w+\s+){0,3}(?:cria|criar|crie|cries|constroi|construir|"
    r"desenvolve|desenvolver|gera|gerar|implementa|implementar|inicia|iniciar|faz|fazer)\b|"
    r"\bdo\s+not\s+(?:\w+\s+){0,2}(?:create|build|develop|generate|implement|start)\b|"
    r"\bdon't\s+(?:\w+\s+){0,2}(?:create|build|develop|generate|implement|start)\b|"
    r"\b(?:sem|without)\s+(?:\w+\s+){0,2}(?:criar|construir|desenvolver|gerar|create|build)\b"
)
_CONSTRAINED_TARGETS = {
    "Obsidian": ("obsidian", "vault", "cofre"),
    "Docker": ("docker",),
    "React": ("react",),
}


def _mention_is_negated(text: str, mention_start: int) -> bool:
    boundary = max(
        text.rfind(separator, 0, mention_start)
        for separator in (".", ";", "!", "?", "\n")
    )
    prefix = text[max(boundary + 1, mention_start - 80):mention_start]
    tail = " ".join(prefix.split()[-7:])
    return bool(re.search(
        r"(?:^|\s)(?:"
        r"nao(?:\s+\w+){0,4}|"
        r"sem(?:\s+\w+){0,3}|"
        r"evita(?:r)?(?:\s+\w+){0,2}|"
        r"do\s+not(?:\s+\w+){0,3}|"
        r"don't(?:\s+\w+){0,3}|"
        r"without(?:\s+\w+){0,3}|"
        r"avoid(?:\s+\w+){0,2}|"
        r"never(?:\s+\w+){0,3}|"
        r"fora\s+(?:de|do|da)(?:\s+\w+){0,1}"
        r")$",
        tail,
    ))


def _negative_constraints(prompt: str) -> list[str]:
    constraints: list[str] = []
    for clause in re.split(r"(?<=[.!?;])|[\r\n]+", str(prompt or "")):
        clean_clause = clause.strip(" \t\r\n.;!?")
        if not clean_clause:
            continue
        normalized_clause = normalize_prompt(clean_clause)
        marker = _NEGATION_MARKER_RE.search(normalized_clause)
        if marker:
            constraint = clean_clause[marker.start():].strip()
            if constraint and constraint not in constraints:
                constraints.append(constraint)
    return constraints


def detect_project_creation_intent(prompt: str) -> ProjectCreationIntent:
    text = normalize_prompt(prompt)
    if not text.strip():
        return ProjectCreationIntent(False, 0.0, rejection_reason="empty_prompt")

    signals: list[tuple[int, str]] = []
    positive_actions = []
    for match in _CREATION_ACTION_RE.finditer(text):
        if _mention_is_negated(text, match.start()):
            continue
        positive_actions.append(match.group(0))
        signals.append((match.start(), match.group(0)))

    target_matches = list(_PROJECT_TARGET_RE.finditer(text))
    for match in target_matches:
        signals.append((match.start(), re.sub(r"\s+", " ", match.group(0))))

    stack_selection = _STACK_SELECTION_RE.search(text)
    if stack_selection:
        positive_actions.append("usa")
        signals.append((stack_selection.start(), "usa"))
        signals.append((stack_selection.start() + len("usa "), "outra stack"))

    excluded_targets: list[str] = []
    positive_external_targets: list[str] = []
    for canonical, aliases in _CONSTRAINED_TARGETS.items():
        mentions = [
            match
            for alias in aliases
            for match in re.finditer(rf"\b{re.escape(alias)}\b", text)
        ]
        if any(_mention_is_negated(text, match.start()) for match in mentions):
            excluded_targets.append(canonical)
        if canonical == "Obsidian" and any(
            not _mention_is_negated(text, match.start()) for match in mentions
        ):
            positive_external_targets.append(canonical)

    constraints = _negative_constraints(prompt)
    ordered_signals: list[str] = []
    for _, signal in sorted(signals, key=lambda item: item[0]):
        if signal not in ordered_signals:
            ordered_signals.append(signal)

    explicit_creation_negation = bool(_NEGATED_CREATION_RE.search(text))
    has_project_target = bool(target_matches or stack_selection)
    if explicit_creation_negation and not positive_actions:
        return ProjectCreationIntent(
            False,
            0.99,
            creation_signals=ordered_signals,
            negative_constraints=constraints,
            excluded_targets=excluded_targets,
            rejection_reason="creation_explicitly_negated",
        )
    if positive_external_targets and not has_project_target:
        return ProjectCreationIntent(
            False,
            0.95,
            creation_signals=ordered_signals,
            negative_constraints=constraints,
            excluded_targets=excluded_targets,
            rejection_reason="external_workspace_is_primary_target",
            separate_work=positive_external_targets,
        )
    if not positive_actions:
        return ProjectCreationIntent(
            False,
            0.2,
            creation_signals=ordered_signals,
            negative_constraints=constraints,
            excluded_targets=excluded_targets,
            rejection_reason="no_creation_action",
            separate_work=positive_external_targets,
        )
    if not has_project_target:
        return ProjectCreationIntent(
            False,
            0.35,
            creation_signals=ordered_signals,
            negative_constraints=constraints,
            excluded_targets=excluded_targets,
            rejection_reason="no_project_target",
            separate_work=positive_external_targets,
        )

    compound = bool(positive_external_targets)
    return ProjectCreationIntent(
        True,
        0.98 if not compound else 0.9,
        creation_signals=ordered_signals,
        negative_constraints=constraints,
        excluded_targets=excluded_targets,
        rejection_reason=None,
        compound_intent=compound,
        separate_work=positive_external_targets,
    )


def is_project_creation_request(prompt: str) -> bool:
    return detect_project_creation_intent(prompt).is_creation_request


def slugify(value: str, fallback: str = "project") -> str:
    normalized = normalize_prompt(value)
    slug = re.sub(r"[^a-z0-9]+", "-", normalized).strip("-")
    return (slug or fallback)[:64].strip("-") or fallback


def unique_project_rel_dir(project_name: str, projects_root_rel: str = PROJECT_ROOT_REL) -> str:
    base_slug = slugify(project_name)
    root_abs = ag_tools.resolve_workspace_path(projects_root_rel)
    os.makedirs(root_abs, exist_ok=True)
    candidate = base_slug
    counter = 2
    while os.path.exists(os.path.join(root_abs, candidate)):
        candidate = f"{base_slug}-{counter}"
        counter += 1
    return f"{projects_root_rel.rstrip('/')}/{candidate}".replace("\\", "/")


def extract_json_object(text: str) -> dict[str, Any]:
    if isinstance(text, dict):
        return text
    raw = str(text or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?", "", raw, flags=re.IGNORECASE).strip()
        raw = re.sub(r"```$", "", raw).strip()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start < 0 or end <= start:
            raise ProjectBuilderError("O LLM nao devolveu um objeto JSON.")
        parsed = json.loads(raw[start:end + 1])
    if not isinstance(parsed, dict):
        raise ProjectBuilderError("O plano JSON tem de ser um objeto.")
    return parsed


def _safe_relative_file_path(path_value: str) -> str:
    path = str(path_value or "").replace("\\", "/").strip().lstrip("/")
    if not path:
        raise ProjectBuilderError("Ficheiro sem path.")
    if re.match(r"^[a-zA-Z]:", path) or path.startswith("../") or "/../" in path or path == "..":
        raise ProjectBuilderError(f"Path recusado fora do projeto: {path_value}")
    lowered = path.lower()
    if lowered.startswith("obsidian_vault/") or "/obsidian_vault/" in lowered:
        raise ProjectBuilderError(f"Path recusado dentro do Obsidian: {path_value}")
    return path


def project_plan_schema_document() -> dict[str, Any]:
    return deepcopy(PROJECT_PLAN_SCHEMA)


def project_plan_schema_prompt() -> str:
    return json.dumps(project_plan_schema_document(), ensure_ascii=False, separators=(",", ":"))


def _received_type(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    if isinstance(value, (int, float)):
        return "number"
    return type(value).__name__


def _summarize_offending(value: Any, *, sensitive: bool = False) -> str:
    if isinstance(value, str):
        if sensitive or len(value) > 120:
            return f"<string length={len(value)}>"
        return value
    if isinstance(value, (list, dict)):
        return f"<{_received_type(value)} items={len(value)}>"
    return repr(value)[:120]


def _validation_issue(
    code: str,
    field_path: str,
    message: str,
    *,
    expected_type: str = "",
    value: Any = None,
    repairable: bool = False,
    suggestion: str = "",
    sensitive: bool = False,
    phase: str = "PLAN_SEMANTIC_VALIDATION",
    file: str = "",
    line: int | None = None,
    symbol: str = "",
    target: str = "",
    actual: str = "",
    component: str = "",
) -> PlanValidationIssue:
    return PlanValidationIssue(
        code=code,
        field_path=field_path,
        message=message,
        expected_type=expected_type,
        received_type=_received_type(value) if expected_type else "",
        offending_value=_summarize_offending(value, sensitive=sensitive),
        repairable=repairable,
        suggestion=suggestion,
        phase=phase,
        file=file,
        line=line,
        symbol=symbol,
        target=target,
        expected=expected_type,
        actual=actual,
        component=component,
    )


def _language_for_extension(extension: str) -> str:
    return {
        ".js": "javascript",
        ".mjs": "javascript",
        ".cjs": "javascript",
        ".jsx": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".py": "python",
        ".html": "html",
        ".css": "css",
        ".json": "json",
    }.get(extension.lower(), "text")


def _record_repair(repairs: list[dict[str, Any]], code: str, field_path: str, action: str) -> None:
    repairs.append({"code": code, "field_path": field_path, "action": action})


def _normalize_relative_path_syntax(value: str) -> str:
    normalized = value.replace("\\", "/").strip()
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def _deduplicate_string_array(
    data: dict[str, Any], field_name: str, repairs: list[dict[str, Any]]
) -> None:
    value = data.get(field_name)
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        return
    normalized_items: list[str] = []
    seen: set[str] = set()
    for item in value:
        clean = item.strip()
        if field_name == "components":
            clean = clean.lower()
        if clean and clean not in seen:
            normalized_items.append(clean)
            seen.add(clean)
    if normalized_items != value:
        data[field_name] = normalized_items
        _record_repair(repairs, "DEDUPLICATE_ARRAY", field_name, "Trimmed and deduplicated strings preserving order.")


def repair_project_plan_mechanically(data: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    normalized = deepcopy(data)
    repairs: list[dict[str, Any]] = []

    for alias, canonical in {
        "name": "project_name",
        "component_to_file_mapping": "component_files",
    }.items():
        if alias in normalized and canonical not in normalized:
            normalized[canonical] = normalized.pop(alias)
            _record_repair(repairs, "NORMALIZE_FIELD_ALIAS", canonical, f"Renamed {alias} to {canonical}.")

    for field_name, spec in PROJECT_PLAN_SCHEMA["properties"].items():
        if field_name not in normalized and not spec.get("required") and "default" in spec:
            normalized[field_name] = deepcopy(spec["default"])
            _record_repair(repairs, "FILL_OPTIONAL_DEFAULT", field_name, "Filled the declared optional default.")

    for field_name, spec in PROJECT_PLAN_SCHEMA["properties"].items():
        if spec.get("type") != "array[string]" or field_name not in normalized:
            continue
        value = normalized[field_name]
        if isinstance(value, str):
            normalized[field_name] = [value]
            _record_repair(repairs, "SCALAR_TO_ARRAY", field_name, "Wrapped one string in an array.")
        elif field_name == "dependencies" and isinstance(value, dict):
            normalized[field_name] = list(value.keys())
            _record_repair(repairs, "DEPENDENCY_MAP_TO_ARRAY", field_name, "Used dependency names from the object keys.")
        _deduplicate_string_array(normalized, field_name, repairs)

    for field_name in ("project_name", "stack", "preview_command", "rationale"):
        value = normalized.get(field_name)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            normalized[field_name] = str(value)
            _record_repair(repairs, "SCALAR_TO_STRING", field_name, "Converted an unambiguous scalar to string.")

    files = normalized.get("files")
    if isinstance(files, list):
        repaired_files: list[Any] = []
        seen_files: dict[str, str] = {}
        for index, item in enumerate(files):
            if not isinstance(item, dict):
                repaired_files.append(item)
                continue
            repaired_item = deepcopy(item)
            if "filename" in repaired_item and "path" not in repaired_item:
                repaired_item["path"] = repaired_item.pop("filename")
                _record_repair(
                    repairs, "NORMALIZE_FIELD_ALIAS", f"files[{index}].path", "Renamed filename to path."
                )
            path_value = repaired_item.get("path")
            if isinstance(path_value, str):
                clean_path = _normalize_relative_path_syntax(path_value)
                if clean_path != path_value:
                    repaired_item["path"] = clean_path
                    _record_repair(
                        repairs, "NORMALIZE_PATH", f"files[{index}].path", "Normalized slashes and ./ prefix."
                    )
                content = repaired_item.get("content")
                if isinstance(content, str) and clean_path in seen_files and seen_files[clean_path] == content:
                    _record_repair(
                        repairs,
                        "REMOVE_IDENTICAL_DUPLICATE_FILE",
                        f"files[{index}].path",
                        f"Removed an identical duplicate for {clean_path}.",
                    )
                    continue
                if isinstance(content, str) and clean_path not in seen_files:
                    seen_files[clean_path] = content
            repaired_files.append(repaired_item)
        normalized["files"] = repaired_files

    entrypoints = normalized.get("entrypoints")
    if isinstance(entrypoints, list) and all(isinstance(item, str) for item in entrypoints):
        clean_entrypoints = [_normalize_relative_path_syntax(item) for item in entrypoints]
        clean_entrypoints = list(dict.fromkeys(item for item in clean_entrypoints if item))
        if clean_entrypoints != entrypoints:
            normalized["entrypoints"] = clean_entrypoints
            _record_repair(repairs, "NORMALIZE_PATH_ARRAY", "entrypoints", "Normalized and deduplicated paths.")

    component_files = normalized.get("component_files")
    if isinstance(component_files, dict):
        repaired_mapping: dict[str, Any] = {}
        for component, paths in component_files.items():
            key = str(component).strip().lower()
            if isinstance(paths, str):
                paths = [paths]
                _record_repair(
                    repairs, "SCALAR_TO_ARRAY", f"component_files.{key}", "Wrapped one path in an array."
                )
            if isinstance(paths, list) and all(isinstance(item, str) for item in paths):
                paths = list(dict.fromkeys(
                    clean for clean in (_normalize_relative_path_syntax(item) for item in paths) if clean
                ))
            repaired_mapping[key] = paths
        if repaired_mapping != component_files:
            normalized["component_files"] = repaired_mapping
            _record_repair(repairs, "NORMALIZE_COMPONENT_MAPPING", "component_files", "Normalized component names and paths.")

    preview_strategy = normalized.get("preview_strategy")
    if isinstance(preview_strategy, str):
        normalized["preview_strategy"] = {"kind": preview_strategy}
        _record_repair(repairs, "SCALAR_TO_OBJECT", "preview_strategy", "Converted the strategy name to an object.")

    return normalized, repairs


def _schema_errors(data: dict[str, Any]) -> list[PlanValidationIssue]:
    errors: list[PlanValidationIssue] = []
    properties = PROJECT_PLAN_SCHEMA["properties"]
    if PROJECT_PLAN_SCHEMA.get("additional_properties") is False:
        for field_name in data:
            if field_name not in properties:
                errors.append(_validation_issue(
                    "UNKNOWN_FIELD",
                    field_name,
                    f"O campo {field_name} nao pertence ao schema do plano.",
                    value=data[field_name],
                    repairable=False,
                    suggestion="Remove a propriedade desconhecida sem omitir campos obrigatorios.",
                ))

    for field_name, spec in properties.items():
        if field_name not in data:
            if spec.get("required"):
                errors.append(_validation_issue(
                    "MISSING_REQUIRED_FIELD",
                    field_name,
                    f"O campo obrigatorio {field_name} esta em falta.",
                    expected_type=spec["type"],
                    value=None,
                    repairable=False,
                    suggestion=f"Inclui {field_name} com o tipo exato {spec['type']}.",
                ))
            continue
        value = data[field_name]
        expected = spec["type"]
        type_ok = {
            "string": isinstance(value, str),
            "array[string]": isinstance(value, list) and all(isinstance(item, str) for item in value),
            "array[object]": isinstance(value, list) and all(isinstance(item, dict) for item in value),
            "object": isinstance(value, dict),
            "object[array[string]]": (
                isinstance(value, dict)
                and all(isinstance(item, list) and all(isinstance(path, str) for path in item) for item in value.values())
            ),
        }.get(expected, False)
        if not type_ok:
            errors.append(_validation_issue(
                "INVALID_FIELD_TYPE",
                field_name,
                f"{field_name} tem de ter o tipo {expected}.",
                expected_type=expected,
                value=value,
                repairable=True,
                suggestion=f"Converte {field_name} para {expected} sem alterar o significado.",
            ))
            continue
        if expected == "string" and spec.get("non_empty") and not value.strip():
            errors.append(_validation_issue(
                "EMPTY_REQUIRED_STRING",
                field_name,
                f"{field_name} nao pode ser vazio.",
                expected_type="non-empty string",
                value=value,
                repairable=False,
                suggestion=f"Fornece um valor nao vazio para {field_name}.",
            ))
        if expected.startswith("array"):
            if len(value) < spec.get("min_items", 0):
                errors.append(_validation_issue(
                    "TOO_FEW_ITEMS", field_name, f"{field_name} nao pode ser vazio.",
                    expected_type=expected, value=value, repairable=False,
                    suggestion=f"Inclui pelo menos {spec.get('min_items', 1)} item valido.",
                ))
            if "max_items" in spec and len(value) > spec["max_items"]:
                errors.append(_validation_issue(
                    "TOO_MANY_ITEMS", field_name,
                    f"{field_name} excede o maximo de {spec['max_items']} itens.",
                    expected_type=expected, value=value, repairable=False,
                    suggestion=f"Reduz a lista para no maximo {spec['max_items']} itens.",
                ))
            allowed = spec.get("allowed_items")
            if allowed:
                for index, item in enumerate(value):
                    if item not in allowed:
                        errors.append(_validation_issue(
                            "INVALID_ENUM_VALUE", f"{field_name}[{index}]",
                            f"O valor {item} nao e permitido em {field_name}.",
                            expected_type="one of: " + ", ".join(allowed), value=item, repairable=True,
                            suggestion="Usa apenas valores declarados no schema.",
                        ))

    files = data.get("files")
    if isinstance(files, list):
        item_schema = properties["files"]["item_schema"]
        seen_paths: dict[str, tuple[int, str]] = {}
        for index, item in enumerate(files):
            if not isinstance(item, dict):
                continue
            if item_schema.get("additional_properties") is False:
                for key in item:
                    if key not in item_schema["properties"]:
                        errors.append(_validation_issue(
                            "UNKNOWN_FIELD", f"files[{index}].{key}",
                            f"O campo files[{index}].{key} nao pertence ao schema.",
                            value=item[key], repairable=False,
                            suggestion="Remove a propriedade desconhecida.",
                        ))
            for key, item_spec in item_schema["properties"].items():
                field_path = f"files[{index}].{key}"
                if key not in item:
                    errors.append(_validation_issue(
                        "MISSING_REQUIRED_FIELD", field_path, f"O campo {field_path} esta em falta.",
                        expected_type=item_spec["type"], value=None, repairable=False,
                        suggestion=f"Inclui {key} em cada ficheiro.",
                    ))
                elif not isinstance(item[key], str):
                    errors.append(_validation_issue(
                        "INVALID_FIELD_TYPE", field_path, f"{field_path} tem de ser string.",
                        expected_type="string", value=item[key], repairable=True,
                        suggestion=f"Converte {field_path} para string sem inventar conteudo.",
                        sensitive=key == "content",
                    ))
                elif item_spec.get("non_empty") and not item[key].strip():
                    errors.append(_validation_issue(
                        "EMPTY_REQUIRED_STRING", field_path, f"{field_path} nao pode ser vazio.",
                        expected_type="non-empty string", value=item[key], repairable=False,
                        suggestion=f"Fornece um valor nao vazio para {field_path}.",
                    ))
            path = item.get("path")
            content = item.get("content")
            if isinstance(path, str) and isinstance(content, str):
                if path in seen_paths:
                    errors.append(_validation_issue(
                        "DUPLICATE_FILE_PATH_CONFLICT",
                        f"files[{index}].path",
                        f"O path {path} aparece mais de uma vez com conteudo diferente.",
                        expected_type="unique file path",
                        value=path,
                        repairable=False,
                        suggestion="Devolve paths distintos ou um unico ficheiro com o conteudo correto; nao omitas outros ficheiros.",
                    ))
                else:
                    seen_paths[path] = (index, content)
    return errors


def _requested_components(prompt: str) -> list[str]:
    text = normalize_prompt(prompt)
    required: list[str] = []
    if "full stack" in text or "fullstack" in text:
        required.extend(["frontend", "backend"])
    for component, terms in {
        "frontend": ["frontend", "pagina", "interface", "browser"],
        "backend": ["backend", "api", "endpoint", "servidor"],
        "persistence": ["persistencia", "persistente", "database", "base de dados", "sqlite"],
        "tests": ["teste", "testes", "validation", "validacao"],
        "preview": ["preview"],
    }.items():
        if any(term in text for term in terms):
            required.append(component)
    return list(dict.fromkeys(required))


def _infer_components(stack: str, files: list[ProjectFile]) -> list[str]:
    components: list[str] = []
    paths = [item.path.lower() for item in files]
    content = "\n".join(item.content.lower() for item in files)
    if any(path.endswith((".html", ".css", ".jsx", ".tsx")) for path in paths):
        components.extend(["frontend", "preview"])
    if any(term in content for term in ("createserver(", "express(", "fastapi(", "flask(")):
        components.append("backend")
    if any(term in content for term in ("sqlite", "notes.json", "writefile", "json.dump", "localstorage")):
        components.append("persistence")
    if any("test" in Path(path).stem for path in paths):
        components.append("tests")
    return list(dict.fromkeys(components))


@dataclass
class _JavaScriptFacts:
    bindings: set[str] = field(default_factory=set)
    imported_modules: set[str] = field(default_factory=set)
    root_member_uses: list[tuple[str, str, int]] = field(default_factory=list)
    direct_calls: set[str] = field(default_factory=set)
    string_literals: set[str] = field(default_factory=set)
    warnings: list[str] = field(default_factory=list)


FUNCTIONAL_COMPONENTS = {"frontend", "backend", "persistence", "tests"}
FS_READ_OPERATIONS = {"readFile", "readFileSync", "createReadStream"}
FS_WRITE_OPERATIONS = {
    "appendFile", "appendFileSync", "createWriteStream", "truncate", "truncateSync",
    "writeFile", "writeFileSync",
}


def _tree_sitter_javascript_parser():
    if TreeSitterParser is None or TreeSitterLanguage is None or tsjavascript is None:
        return None
    parser = TreeSitterParser()
    parser.language = TreeSitterLanguage(tsjavascript.language())
    return parser


def _javascript_facts(file: PlannedFile) -> _JavaScriptFacts:
    facts = _JavaScriptFacts()
    parser = _tree_sitter_javascript_parser()
    if parser is None:
        facts.warnings.append("tree-sitter-javascript indisponivel; imports nao inferidos por suspeita.")
        return facts
    source = file.content.encode("utf-8")
    tree = parser.parse(source)
    if tree.root_node.has_error:
        facts.warnings.append("Tree-sitter encontrou sintaxe JavaScript incompleta.")
        return facts

    def text(node) -> str:
        return source[node.start_byte:node.end_byte].decode("utf-8", errors="replace")

    def identifiers(node) -> set[str]:
        found: set[str] = set()
        if node.type in {
            "identifier", "shorthand_property_identifier_pattern",
        }:
            found.add(text(node))
        for child in node.children:
            found.update(identifiers(child))
        return found

    def module_name(node) -> str:
        value = text(node).strip()
        if len(value) >= 2 and value[0] in {'\"', "'", "`"} and value[-1] == value[0]:
            return value[1:-1]
        return ""

    def traverse(node) -> None:
        if node.type == "import_statement":
            source_node = node.child_by_field_name("source")
            if source_node is not None:
                imported = module_name(source_node)
                if imported:
                    facts.imported_modules.add(imported)
            clause = next((child for child in node.children if child.type == "import_clause"), None)
            if clause is not None:
                facts.bindings.update(identifiers(clause))
        elif node.type == "variable_declarator":
            name_node = node.child_by_field_name("name")
            if name_node is not None:
                facts.bindings.update(identifiers(name_node))
        elif node.type in {"function_declaration", "generator_function_declaration", "class_declaration"}:
            name_node = node.child_by_field_name("name")
            if name_node is not None:
                facts.bindings.add(text(name_node))
        elif node.type in {"formal_parameters", "catch_clause"}:
            facts.bindings.update(identifiers(node))
        elif node.type == "member_expression":
            object_node = node.child_by_field_name("object")
            property_node = node.child_by_field_name("property")
            if object_node is not None and object_node.type == "identifier" and property_node is not None:
                facts.root_member_uses.append((
                    text(object_node), text(property_node), node.start_point[0] + 1,
                ))
        elif node.type == "call_expression":
            function_node = node.child_by_field_name("function")
            arguments_node = node.child_by_field_name("arguments")
            if function_node is not None and function_node.type == "identifier":
                function_name = text(function_node)
                facts.direct_calls.add(function_name)
                if function_name in {"require", "import"} and arguments_node is not None:
                    string_node = next(
                        (child for child in arguments_node.children if child.type in {"string", "template_string"}),
                        None,
                    )
                    if string_node is not None:
                        imported = module_name(string_node)
                        if imported:
                            facts.imported_modules.add(imported)
        elif node.type in {"string", "template_string"}:
            value = module_name(node)
            if value:
                facts.string_literals.add(value)
        for child in node.children:
            traverse(child)

    traverse(tree.root_node)
    return facts


def _javascript_tree(file: PlannedFile):
    parser = _tree_sitter_javascript_parser()
    if parser is None:
        return None, b""
    source = file.content.encode("utf-8")
    tree = parser.parse(source)
    if tree.root_node.has_error:
        return None, source
    return tree, source


def _javascript_node_text(source: bytes, node) -> str:
    return source[node.start_byte:node.end_byte].decode("utf-8", errors="replace")


def _javascript_descendants(node):
    yield node
    for child in node.children:
        yield from _javascript_descendants(child)


def _javascript_nonzero_literal(source: bytes, node) -> bool:
    value = _javascript_node_text(source, node).strip()
    if not re.fullmatch(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)", value):
        return False
    try:
        return float(value) != 0
    except ValueError:
        return False


def _handler_propagates_failure(handler, source: bytes) -> bool:
    for node in _javascript_descendants(handler):
        if node.type == "throw_statement":
            return True
        if node.type == "assignment_expression":
            left = node.child_by_field_name("left")
            right = node.child_by_field_name("right")
            if (
                left is not None and right is not None
                and re.sub(r"\s+", "", _javascript_node_text(source, left)) == "process.exitCode"
                and _javascript_nonzero_literal(source, right)
            ):
                return True
        if node.type != "call_expression":
            continue
        function = node.child_by_field_name("function")
        arguments = node.child_by_field_name("arguments")
        if function is None or arguments is None:
            continue
        function_text = re.sub(r"\s+", "", _javascript_node_text(source, function))
        values = list(arguments.named_children)
        if function_text == "process.exit" and values and _javascript_nonzero_literal(source, values[0]):
            return True
    return False


def _handler_logs_failure(handler, source: bytes) -> bool:
    for node in _javascript_descendants(handler):
        if node.type != "member_expression":
            continue
        value = re.sub(r"\s+", "", _javascript_node_text(source, node))
        if value in {"console.error", "console.log"}:
            return True
    return False


def _test_failure_propagation_issues(
    file: PlannedFile,
    *,
    phase: str,
) -> list[PlanValidationIssue]:
    tree, source = _javascript_tree(file)
    if tree is None:
        if re.search(r"\.catch\s*\(\s*console\.(?:error|log)\s*\)", file.content):
            return [_static_issue(
                "TEST_FAILURE_NOT_PROPAGATED", f"files[{file.normalized_path}].content",
                "O teste captura uma rejeicao apenas para a registar e pode terminar com exit code zero.",
                phase=phase, file=file.normalized_path,
                expected="catch handler that throws or sets a non-zero process exit status",
                actual=".catch(console logger)",
                suggestion="Propaga a falha com throw, process.exitCode nao zero ou process.exit nao zero.",
            )]
        return []

    for node in _javascript_descendants(tree.root_node):
        handler = None
        actual = ""
        if node.type == "call_expression":
            function = node.child_by_field_name("function")
            arguments = node.child_by_field_name("arguments")
            if function is None or arguments is None:
                continue
            function_text = re.sub(r"\s+", "", _javascript_node_text(source, function))
            if not function_text.endswith(".catch") or not arguments.named_children:
                continue
            handler = arguments.named_children[0]
            actual = _javascript_node_text(source, handler).strip()
        elif node.type == "catch_clause":
            handler = node
            actual = "catch handler that only logs the failure"
        if handler is None or _handler_propagates_failure(handler, source):
            continue
        if not _handler_logs_failure(handler, source):
            continue
        return [_static_issue(
            "TEST_FAILURE_NOT_PROPAGATED", f"files[{file.normalized_path}].content",
            "O teste captura uma falha apenas para a registar e pode produzir falso sucesso.",
            phase=phase, file=file.normalized_path, line=node.start_point[0] + 1,
            expected="throw captured error or set process.exitCode/process.exit to a non-zero value",
            actual=actual,
            suggestion="Propaga a falha com throw, process.exitCode nao zero ou process.exit nao zero.",
        )]
    return []


def _javascript_persistence_operations(file: PlannedFile) -> tuple[set[str], set[str]]:
    facts = _javascript_facts(file)
    fs_imported = bool({
        value.removeprefix("node:") for value in facts.imported_modules
    } & {"fs", "fs/promises"})
    if not fs_imported:
        return set(), set()
    tree, source = _javascript_tree(file)
    if tree is None:
        return set(), set()
    reads: set[str] = set()
    writes: set[str] = set()
    for node in _javascript_descendants(tree.root_node):
        if node.type != "call_expression":
            continue
        function = node.child_by_field_name("function")
        if function is None:
            continue
        call = re.sub(r"\s+", "", _javascript_node_text(source, function))
        operation = call.rsplit(".", 1)[-1]
        if operation in FS_READ_OPERATIONS:
            reads.add(operation)
        if operation in FS_WRITE_OPERATIONS:
            writes.add(operation)
    return reads, writes


def _persistence_evidence(files: list[PlannedFile]) -> tuple[bool, str]:
    fs_reads: set[str] = set()
    fs_writes: set[str] = set()
    fs_paths: list[str] = []
    for file in files:
        reads, writes = _javascript_persistence_operations(file)
        if reads or writes:
            fs_paths.append(file.normalized_path)
            fs_reads.update(reads)
            fs_writes.update(writes)
        compact = re.sub(r"\s+", "", file.content)
        if "localStorage.getItem(" in compact and "localStorage.setItem(" in compact:
            return True, f"{file.normalized_path}: localStorage read/write"
        if "indexedDB.open(" in compact and ".transaction(" in compact:
            return True, f"{file.normalized_path}: IndexedDB"
        lowered = file.content.lower()
        if "sqlite3" in lowered and re.search(r"\b(select|pragma)\b", lowered) and re.search(
            r"\b(insert|update|delete|replace|create\s+table)\b", lowered
        ):
            return True, f"{file.normalized_path}: SQLite read/write"
        if re.search(r"\bopen\s*\([^\n]+[\"']r", file.content) and re.search(
            r"\bopen\s*\([^\n]+[\"'](?:w|a|x)", file.content
        ):
            return True, f"{file.normalized_path}: file read/write"
    if fs_reads and fs_writes:
        return True, (
            f"{sorted(set(fs_paths))}: fs reads={sorted(fs_reads)}, writes={sorted(fs_writes)}"
        )
    return False, "no durable read/write mechanism in mapped persistence artifacts"


def _normalized_node_dependency(value: str) -> str:
    clean = value.removeprefix("node:")
    if clean.startswith((".", "/")):
        return ""
    return "/".join(clean.split("/")[:2]) if clean.startswith("@") else clean.split("/", 1)[0]


def _static_issue(
    code: str,
    field_path: str,
    message: str,
    *,
    phase: str,
    file: str = "",
    line: int | None = None,
    symbol: str = "",
    target: str = "",
    expected: str = "",
    actual: str = "",
    component: str = "",
    suggestion: str,
) -> PlanValidationIssue:
    return _validation_issue(
        code,
        field_path,
        message,
        expected_type=expected,
        value=actual,
        repairable=False,
        suggestion=suggestion,
        phase=phase,
        file=file,
        line=line,
        symbol=symbol,
        target=target,
        actual=actual,
        component=component,
    )


def _command_target_issues(
    command: str,
    field_path: str,
    source: PlannedFileSystem,
    *,
    phase: str,
) -> list[PlanValidationIssue]:
    errors: list[PlanValidationIssue] = []
    target_pattern = r'(?:"[^"\r\n]+"|\'[^\'\r\n]+\'|[^\s]+)'
    for segment in _command_segments(command):
        for match in re.finditer(rf"(?i)\bnode\s+--check\s+({target_pattern})", segment):
            target = _command_target(match.group(1))
            extension = Path(target).suffix.lower()
            if extension not in {".js", ".mjs", ".cjs"}:
                errors.append(_static_issue(
                    "COMMAND_TARGET_INVALID", field_path,
                    f"node --check nao suporta o target {target}.",
                    phase=phase, file=target, target=target,
                    expected="JavaScript source file",
                    actual=f"{_language_for_extension(extension).upper()} file",
                    suggestion="Usa node --check apenas com ficheiros .js, .mjs ou .cjs.",
                ))
            elif not source.exists(target):
                errors.append(_static_issue(
                    "MISSING_ENTRYPOINT", field_path,
                    f"O target do comando nao existe: {target}.",
                    phase=phase, file=target, target=target,
                    expected="planned JavaScript source file", actual="missing file",
                    suggestion="Corrige o script para apontar para um ficheiro JavaScript planeado.",
                ))
        for match in re.finditer(
            rf"(?i)\b(?:python(?:\.exe)?|[^\s]+python[^\s]*)\s+-m\s+py_compile\s+({target_pattern})",
            segment,
        ):
            target = _command_target(match.group(1))
            extension = Path(target).suffix.lower()
            if extension != ".py":
                errors.append(_static_issue(
                    "COMMAND_TARGET_INVALID", field_path,
                    f"py_compile nao suporta o target {target}.",
                    phase=phase, file=target, target=target,
                    expected="Python source file",
                    actual=f"{_language_for_extension(extension).upper()} file",
                    suggestion="Usa py_compile apenas com ficheiros Python .py.",
                ))
            elif not source.exists(target):
                errors.append(_static_issue(
                    "MISSING_ENTRYPOINT", field_path,
                    f"O target de py_compile nao existe: {target}.",
                    phase=phase, file=target, target=target,
                    expected="planned Python source file", actual="missing file",
                    suggestion="Corrige o comando para um ficheiro Python planeado.",
                ))
        node_script = re.match(rf"(?i)^node\s+(?!-)({target_pattern})", segment)
        if node_script:
            target = _command_target(node_script.group(1))
            if Path(target).suffix.lower() in {".js", ".mjs", ".cjs"} and not source.exists(target):
                errors.append(_static_issue(
                    "MISSING_ENTRYPOINT", field_path,
                    f"O script Node aponta para ficheiro inexistente: {target}.",
                    phase=phase, file=target, target=target,
                    expected="planned JavaScript source file", actual="missing file",
                    suggestion="Cria o ficheiro no plano ou corrige o target do script.",
                ))
    return errors


def _plan_package_from_source(source: PlannedFileSystem) -> tuple[dict[str, Any], list[PlanValidationIssue]]:
    package_file = source.get("package.json")
    if package_file is None:
        return {}, []
    try:
        value = json.loads(package_file.content)
    except ValueError as exc:
        return {}, [_static_issue(
            "INVALID_PACKAGE_JSON", "files[package.json].content",
            f"package.json invalido no plano: {exc}",
            phase="PLAN_SEMANTIC_VALIDATION", file="package.json",
            expected="valid JSON object", actual="invalid JSON",
            suggestion="Corrige apenas o JSON de package.json.",
        )]
    if not isinstance(value, dict):
        return {}, [_static_issue(
            "INVALID_PACKAGE_JSON_TYPE", "files[package.json].content",
            "package.json do plano deve ser um objeto.",
            phase="PLAN_SEMANTIC_VALIDATION", file="package.json",
            expected="JSON object", actual=type(value).__name__,
            suggestion="Devolve um objeto JSON em package.json.",
        )]
    return value, []


def _test_explicitly_references_entrypoint(
    test_file: PlannedFile,
    facts: _JavaScriptFacts,
    entrypoints: list[str],
) -> bool:
    test_parent = PurePosixPath(test_file.normalized_path).parent
    for literal in facts.imported_modules | facts.string_literals:
        normalized_literal = literal.replace("\\", "/")
        if normalized_literal.startswith("."):
            resolved = str((test_parent / normalized_literal)).replace("\\", "/")
            parts: list[str] = []
            for part in PurePosixPath(resolved).parts:
                if part == ".." and parts:
                    parts.pop()
                elif part not in {".", ".."}:
                    parts.append(part)
            normalized_literal = "/".join(parts)
        for entrypoint in entrypoints:
            normalized_entrypoint = _normalize_relative_path_syntax(entrypoint)
            candidates = {normalized_entrypoint, normalized_entrypoint.removesuffix(Path(normalized_entrypoint).suffix)}
            if normalized_literal in candidates:
                return True
    return False


def _deduplicate_issues(issues: list[PlanValidationIssue]) -> list[PlanValidationIssue]:
    result: list[PlanValidationIssue] = []
    seen: set[tuple[Any, ...]] = set()
    for issue in issues:
        key = (issue.code, issue.field_path, issue.file, issue.line, issue.symbol, issue.target)
        if key not in seen:
            seen.add(key)
            result.append(issue)
    return result


def analyze_project_artifacts(
    source: PlannedFileSystem,
    *,
    components: list[str],
    required_components: list[str],
    entrypoints: list[str],
    component_files: dict[str, list[str]],
    dependencies: list[str],
    setup_commands: list[str],
    validation_commands: list[str],
    preview_command: str,
    preview_strategy: dict[str, Any],
    phase: str = "PLAN_SEMANTIC_VALIDATION",
    command_specs: list[tuple[str, str]] | None = None,
) -> StaticAnalysisResult:
    errors: list[PlanValidationIssue] = []
    warnings = list(source.warnings)
    package, package_errors = _plan_package_from_source(source)
    for issue in package_errors:
        errors.append(PlanValidationIssue(**{**issue.to_dict(), "phase": phase}))
    scripts = package.get("scripts") or {}
    if not isinstance(scripts, dict):
        scripts = {}

    commands = list(command_specs or [])
    if not command_specs:
        commands.extend((f"setup_commands[{index}]", command) for index, command in enumerate(setup_commands))
        commands.extend((f"validation_commands[{index}]", command) for index, command in enumerate(validation_commands))
        if preview_command:
            commands.append(("preview_command", preview_command))
    for name, script in scripts.items():
        if isinstance(script, str):
            commands.append((f"package.json.scripts.{name}", script))
    for field_path, command in commands:
        errors.extend(_command_target_issues(command, field_path, source, phase=phase))

    facts_by_path: dict[str, _JavaScriptFacts] = {}
    imported_modules: set[str] = set()
    for file in source.files.values():
        if file.extension not in {".js", ".mjs", ".cjs", ".jsx", ".ts", ".tsx"}:
            continue
        facts = _javascript_facts(file)
        facts_by_path[file.normalized_path] = facts
        imported_modules.update(
            dependency for dependency in (
                _normalized_node_dependency(value) for value in facts.imported_modules
            ) if dependency
        )
        if facts.warnings:
            warnings.extend(_static_issue(
                "JAVASCRIPT_PARSE_WARNING", f"files[{file.normalized_path}].content",
                warning, phase=phase, file=file.normalized_path,
                expected="structurally parseable JavaScript", actual="parse unavailable or incomplete",
                suggestion="Revê a sintaxe; nenhum MISSING_IMPORT foi inferido por suspeita.",
            ) for warning in facts.warnings)
            continue
        namespace_candidates = set(NODE_BUILTINS)
        namespace_candidates.update(
            dependency for dependency in dependencies
            if re.fullmatch(r"[A-Za-z_$][\w$]*", dependency)
        )
        for symbol, _property, line in facts.root_member_uses:
            if symbol in namespace_candidates and symbol not in facts.bindings:
                errors.append(_static_issue(
                    "MISSING_IMPORT", f"files[{file.normalized_path}].content",
                    f'{symbol} e usado sem uma declaracao local ou import/require correspondente.',
                    phase=phase, file=file.normalized_path, line=line, symbol=symbol,
                    expected=f'Import or require the Node.js built-in module "{symbol}".' if symbol in NODE_BUILTINS else "local declaration or module import",
                    actual=f"undeclared identifier {symbol}",
                    suggestion=(
                        f'Import or require the Node.js built-in module "{symbol}".'
                        if symbol in NODE_BUILTINS
                        else f"Importa ou declara {symbol} antes de o utilizar."
                    ),
                ))

    declared = set(dependencies)
    for field_name in ("dependencies", "devDependencies"):
        value = package.get(field_name) or {}
        if isinstance(value, dict):
            declared.update(str(item) for item in value)
    external_imports = imported_modules - NODE_BUILTINS
    for dependency in sorted(external_imports - declared):
        errors.append(_static_issue(
            "MISSING_DECLARED_DEPENDENCY", "dependencies",
            f"A dependencia {dependency} e usada mas nao esta declarada.",
            phase=phase, symbol=dependency,
            expected="dependency declared in the plan or package.json",
            actual="imported external dependency",
            suggestion="Declara a dependencia no plano e package.json ou remove o import.",
        ))

    for index, entrypoint in enumerate(entrypoints):
        if not source.exists(entrypoint):
            errors.append(_static_issue(
                "MISSING_ENTRYPOINT", f"entrypoints[{index}]",
                f"Entrypoint planeado inexistente: {entrypoint}.",
                phase=phase, file=entrypoint, target=entrypoint,
                expected="path present in planned files", actual="missing file",
                suggestion="Corrige entrypoints para ficheiros presentes no plano.",
            ))

    declared_components = list(dict.fromkeys(components))
    for component in declared_components:
        if component not in FUNCTIONAL_COMPONENTS:
            continue
        mapped = list(component_files.get(component) or [])
        existing = [path for path in mapped if source.exists(path)]
        if existing:
            continue
        errors.append(_static_issue(
            "DECLARED_COMPONENT_WITHOUT_ARTIFACTS", f"component_files.{component}",
            f"O componente declarado {component} nao tem nenhum artefacto real mapeado.",
            phase=phase, component=component,
            expected="at least one component_files path present in the planned files",
            actual=json.dumps(mapped, ensure_ascii=False),
            suggestion=(
                f"Mapeia {component} para pelo menos um ficheiro existente que implemente o componente."
            ),
        ))

    if (
        "persistence" in required_components
        and ("persistence" in components or "persistence" in component_files)
    ):
        persistence_paths = [
            path for path in component_files.get("persistence", []) if source.exists(path)
        ]
        persistence_files = [source.get(path) for path in persistence_paths]
        persistence_files = [file for file in persistence_files if file is not None]
        implemented, evidence = _persistence_evidence(persistence_files)
        if not implemented:
            backend_candidates = [
                path for path in component_files.get("backend", []) if source.exists(path)
            ]
            target = next((
                path for path in persistence_paths + backend_candidates
                if Path(path).suffix.lower() in {".js", ".mjs", ".cjs", ".ts", ".py"}
            ), persistence_paths[0] if persistence_paths else (backend_candidates[0] if backend_candidates else ""))
            errors.append(_static_issue(
                "PERSISTENCE_NOT_IMPLEMENTED", "component_files.persistence",
                "O componente persistence nao demonstra leitura e escrita duravel; estado em memoria nao e persistencia.",
                phase=phase, file=target, target=target, component="persistence",
                expected="mapped artifact implementing durable read and write operations",
                actual=evidence,
                suggestion=(
                    "Associa persistence a um artefacto existente que implemente leitura e escrita duravel."
                ),
            ))

    health_path = str(preview_strategy.get("healthcheck_path") or "/health")
    backend_paths = list(component_files.get("backend") or [])
    backend_contents = [
        file.content for path in backend_paths if (file := source.get(path)) is not None
    ]
    if "backend" in required_components and not any(health_path in content for content in backend_contents):
        errors.append(_static_issue(
            "MISSING_HEALTH_ROUTE", "preview_strategy.healthcheck_path",
            f"Nenhum artefacto backend contem evidencia textual da rota {health_path}.",
            phase=phase, target=health_path, component="backend",
            expected="health route in a mapped backend artifact", actual="route not found",
            suggestion="Implementa a rota de healthcheck no backend associado.",
        ))

    backend_entrypoints = [
        path for path in entrypoints
        if path in backend_paths or Path(path).suffix.lower() in {".js", ".mjs", ".cjs", ".py"}
    ]
    if "backend" in required_components and "tests" in required_components:
        for file in source.files.values():
            if "test" not in Path(file.normalized_path).stem.lower() and "spec" not in Path(file.normalized_path).stem.lower():
                continue
            facts = facts_by_path.get(file.normalized_path)
            if facts is None or facts.warnings:
                continue
            waits_for_health = health_path in file.content and any(
                root in {"http", "https"} and prop == "get"
                for root, prop, _line in facts.root_member_uses
            ) or (health_path in file.content and "fetch" in facts.direct_calls)
            starts_own_server = any(
                prop == "createServer" for _root, prop, _line in facts.root_member_uses
            ) or "createServer" in facts.direct_calls
            references_backend = _test_explicitly_references_entrypoint(
                file, facts, backend_entrypoints
            )
            if waits_for_health and starts_own_server and not references_backend:
                errors.append(_static_issue(
                    "TEST_DOES_NOT_EXERCISE_ENTRYPOINT", f"files[{file.normalized_path}].content",
                    "O teste cria um servidor alternativo para /health sem importar ou iniciar o backend declarado.",
                    phase=phase, file=file.normalized_path,
                    target=backend_entrypoints[0] if backend_entrypoints else "backend entrypoint",
                    expected="test imports, requires, spawns or executes the declared backend entrypoint",
                    actual="isolated alternate server",
                    suggestion="Importa ou inicia explicitamente o backend entrypoint declarado no teste.",
                ))

    if "tests" in required_components:
        for file in source.files.values():
            if "test" not in Path(file.normalized_path).stem.lower() and "spec" not in Path(file.normalized_path).stem.lower():
                continue
            if file.extension not in {".js", ".mjs", ".cjs", ".jsx", ".ts", ".tsx"}:
                continue
            errors.extend(_test_failure_propagation_issues(file, phase=phase))

    component_extensions = {
        "frontend": {".html", ".jsx", ".tsx"},
        "backend": {".js", ".mjs", ".cjs", ".py"},
    }
    for component, extensions in component_extensions.items():
        if component not in required_components:
            continue
        mapped = component_files.get(component) or []
        candidates = [source.get(path) for path in mapped] if mapped else list(source.files.values())
        if not any(file is not None and file.extension in extensions for file in candidates):
            errors.append(_static_issue(
                "MISSING_REQUIRED_COMPONENT", f"component_files.{component}",
                f"O componente {component} nao tem artefacto compativel.",
                phase=phase, component=component,
                expected=f"mapped artifact with one of {sorted(extensions)}",
                actual="no compatible artifact",
                suggestion=f"Mapeia {component} para um ficheiro planeado do tipo suportado.",
            ))

    if "preview" in required_components and not preview_command.strip() and not preview_strategy:
        errors.append(_static_issue(
            "MISSING_PREVIEW_IMPLEMENTATION", "preview_strategy",
            "O plano declara preview sem comando ou estrategia coerente.",
            phase=phase, component="preview",
            expected="preview_command or preview_strategy", actual="missing preview implementation",
            suggestion="Declara uma estrategia de preview coerente com o frontend planeado.",
        ))

    return StaticAnalysisResult(
        errors=_deduplicate_issues(errors),
        warnings=_deduplicate_issues(warnings),
        checked_components=list(dict.fromkeys(required_components)),
        checked_entrypoints=list(entrypoints),
        checked_scripts=sorted(str(item) for item in scripts),
        checked_dependencies=sorted(declared | external_imports),
        virtual_files=source.metadata(),
    )


def _analyze_normalized_plan_artifacts(
    data: dict[str, Any],
    prompt: str,
    *,
    phase: str = "PLAN_SEMANTIC_VALIDATION",
) -> tuple[PlannedFileSystem, StaticAnalysisResult]:
    source = PlannedFileSystem.from_plan_data(data)
    files = [ProjectFile(path=item.normalized_path, content=item.content) for item in source.files.values()]
    components = list(data.get("components") or [])
    required = list(dict.fromkeys(_requested_components(prompt) + components))
    result = analyze_project_artifacts(
        source,
        components=components,
        required_components=required,
        entrypoints=list(data.get("entrypoints") or []),
        component_files=dict(data.get("component_files") or {}),
        dependencies=list(data.get("dependencies") or []),
        setup_commands=list(data.get("setup_commands") or []),
        validation_commands=list(data.get("validation_commands") or []),
        preview_command=str(data.get("preview_command") or ""),
        preview_strategy=dict(data.get("preview_strategy") or {}),
        phase=phase,
    )
    return source, result


def _command_for_semantic_issue(
    data: dict[str, Any],
    source: PlannedFileSystem,
    issue: PlanValidationIssue,
) -> tuple[str, str]:
    field_path = issue.field_path
    if field_path.startswith("package.json.scripts."):
        package, _errors = _plan_package_from_source(source)
        script_name = field_path.removeprefix("package.json.scripts.")
        script = (package.get("scripts") or {}).get(script_name, "")
        return "package.json", str(script or "")
    for field_name in ("setup_commands", "validation_commands"):
        match = re.fullmatch(rf"{field_name}\[(\d+)\]", field_path)
        if match:
            values = data.get(field_name) or []
            index = int(match.group(1))
            return "", str(values[index]) if index < len(values) else ""
    if field_path == "preview_command":
        return "", str(data.get("preview_command") or "")
    return "", ""


def semantic_error_artifact_mappings(
    data: dict[str, Any],
    source: PlannedFileSystem,
    errors: list[PlanValidationIssue],
) -> list[SemanticErrorArtifactMapping]:
    component_files = dict(data.get("component_files") or {})
    mappings: list[SemanticErrorArtifactMapping] = []
    for issue in errors:
        affected: list[str] = []
        evidence: dict[str, Any] = {
            "field_path": issue.field_path,
            "file": issue.file,
            "line": issue.line,
            "symbol": issue.symbol,
            "target": issue.target,
            "expected": issue.expected or issue.expected_type,
            "actual": issue.actual or issue.offending_value,
        }
        postconditions = [issue.suggestion] if issue.suggestion else []
        content_dependent = False

        command_file, command = _command_for_semantic_issue(data, source, issue)
        if issue.code == "COMMAND_TARGET_INVALID":
            affected.extend(path for path in (command_file, issue.target) if source.exists(path))
            evidence.update({
                "command_artifact": command_file or "plan metadata",
                "command": command,
                "target": issue.target,
                "detected_type": issue.actual,
                "accepted_types": issue.expected or "JavaScript source file",
            })
            postconditions = [
                "The complete command must not apply node --check to HTML, CSS, JSON or directories.",
                "Every command target must exist in the corrected virtual file system and use a supported type.",
            ]
            content_dependent = bool(command_file)
        elif issue.code == "TEST_DOES_NOT_EXERCISE_ENTRYPOINT":
            affected.extend(path for path in (issue.file, issue.target) if source.exists(path))
            evidence.update({
                "test_artifact": issue.file,
                "backend_entrypoint": issue.target,
                "alternate_server_evidence": issue.actual or "isolated alternate server",
                "expected_mechanism": "import, start or invoke the declared backend entrypoint",
            })
            postconditions = [
                f"The test must import, start or invoke the real backend entrypoint {issue.target}.",
                "The test must not replace the declared backend with an alternate synthetic server.",
            ]
            content_dependent = True
        elif issue.code == "TEST_FAILURE_NOT_PROPAGATED":
            if source.exists(issue.file):
                affected.append(issue.file)
            evidence.update({
                "test_artifact": issue.file,
                "rejected_handler": issue.actual,
                "accepted_propagation": [
                    "throw captured error",
                    "process.exitCode = non-zero",
                    "process.exit(non-zero)",
                ],
            })
            postconditions = [
                "Every caught test failure must be rethrown or set a non-zero process exit status.",
                "A console.error or console.log call alone does not propagate a test failure.",
            ]
            content_dependent = True
        elif issue.code == "DECLARED_COMPONENT_WITHOUT_ARTIFACTS":
            evidence.update({
                "component": issue.component,
                "received_mapping": issue.actual,
                "expected_artifacts": issue.expected,
            })
            if issue.component == "persistence":
                affected.extend(
                    path for path in component_files.get("backend", []) if source.exists(path)
                )
            postconditions = [
                f"component_files.{issue.component} must contain at least one existing planned artifact."
            ]
        elif issue.code == "PERSISTENCE_NOT_IMPLEMENTED":
            affected.extend(
                path
                for component in ("persistence", "backend")
                for path in component_files.get(component, [])
                if source.exists(path)
                and Path(path).suffix.lower() in {".js", ".mjs", ".cjs", ".jsx", ".ts", ".tsx", ".py"}
            )
            evidence.update({
                "component": "persistence",
                "persistence_artifacts": list(component_files.get("persistence") or []),
                "durability_evidence": issue.actual,
            })
            postconditions = [
                "A mapped existing artifact must implement durable read and write operations.",
                "Module arrays, objects, Map, Set or variables alone do not satisfy persistence.",
                "For dependency-free Node.js plans, node:fs or node:fs/promises may implement the durable storage.",
            ]
            content_dependent = bool(affected)
        elif issue.code == "MISSING_IMPORT":
            if source.exists(issue.file):
                affected.append(issue.file)
            evidence["missing_binding"] = issue.symbol
            postconditions = [
                f"The corrected artifact must introduce a valid local binding for {issue.symbol} before use."
            ]
            content_dependent = bool(affected)
        elif issue.code == "MISSING_HEALTH_ROUTE":
            affected.extend(path for path in component_files.get("backend", []) if source.exists(path))
            postconditions = [
                f"A mapped backend artifact must implement the declared health route {issue.target}."
            ]
            content_dependent = bool(affected)
        elif issue.code == "MISSING_DECLARED_DEPENDENCY":
            if source.exists("package.json"):
                affected.append("package.json")
            if source.exists(issue.file):
                affected.append(issue.file)
            postconditions = [
                "The external module must be declared consistently or removed from all source imports."
            ]
            content_dependent = bool(affected)
        else:
            match = re.match(r"files\[([^\]]+)\]", issue.field_path)
            for path in (issue.file, match.group(1) if match else ""):
                if source.exists(path):
                    affected.append(_normalize_relative_path_syntax(path))

        mappings.append(SemanticErrorArtifactMapping(
            code=issue.code,
            message=issue.message,
            affected_artifacts=list(dict.fromkeys(affected)),
            evidence={key: value for key, value in evidence.items() if value is not None and value != ""},
            required_postconditions=list(dict.fromkeys(item for item in postconditions if item)),
            content_dependent=content_dependent,
        ))
    return mappings


def _semantic_errors(data: dict[str, Any], prompt: str) -> list[PlanValidationIssue]:
    errors: list[PlanValidationIssue] = []
    files = [ProjectFile(path=item["path"], content=item["content"]) for item in data["files"]]
    components = list(data["components"])
    if not components:
        components = _infer_components(data["stack"], files)
    entrypoints = list(data["entrypoints"])
    component_files = dict(data["component_files"])
    validation_commands = list(data["validation_commands"])
    requested_components = _requested_components(prompt)

    missing_promises = sorted(set(requested_components) - set(components))
    if missing_promises:
        errors.append(_validation_issue(
            "MISSING_REQUESTED_COMPONENTS", "components",
            f"Plano nao promete componentes pedidos: {missing_promises}.",
            expected_type="array containing requested components", value=components, repairable=False,
            suggestion="Adiciona os componentes pedidos e os respetivos ficheiros reais.",
        ))
    file_paths = {item.path for item in files}
    if "frontend" in requested_components and "backend" in requested_components:
        unmapped = [component for component in ("frontend", "backend") if not component_files.get(component)]
        if unmapped:
            errors.append(_validation_issue(
                "MISSING_COMPONENT_MAPPING", "component_files",
                f"Plano full stack sem component_files para: {unmapped}.",
                expected_type="object[array[string]]", value=component_files, repairable=False,
                suggestion="Mapeia frontend e backend para ficheiros que existam no plano.",
            ))
        missing_mapped_files = [
            path for component in ("frontend", "backend")
            for path in component_files.get(component, []) if path not in file_paths
        ]
        if missing_mapped_files:
            errors.append(_validation_issue(
                "MAPPED_FILE_NOT_FOUND", "component_files",
                f"component_files referencia ficheiros inexistentes: {missing_mapped_files}.",
                expected_type="paths present in files", value=missing_mapped_files, repairable=False,
                suggestion="Corrige o mapping sem inventar ou omitir componentes.",
            ))
        if not entrypoints:
            errors.append(_validation_issue(
                "MISSING_ENTRYPOINTS", "entrypoints", "Plano full stack sem entrypoints explicitos.",
                expected_type="non-empty array[string]", value=entrypoints, repairable=False,
                suggestion="Indica os entrypoints reais do frontend e backend.",
            ))
        if not validation_commands:
            errors.append(_validation_issue(
                "MISSING_VALIDATION_COMMANDS", "validation_commands",
                "Plano full stack sem validation_commands reais.",
                expected_type="non-empty array[string]", value=validation_commands, repairable=False,
                suggestion="Inclui comandos finitos que validem os componentes reais.",
            ))

    required_by_plan = set(requested_components) | set(components)
    if "tests" in required_by_plan:
        test_files = [
            item for item in files
            if "test" in Path(item.path).stem.lower() or "spec" in Path(item.path).stem.lower()
        ]
        component_paths = list(entrypoints)
        for mapped_paths in component_files.values():
            component_paths.extend(mapped_paths)
        markers = {
            marker
            for path in component_paths
            for marker in (
                path.lower().replace("\\", "/"), Path(path).name.lower(), Path(path).stem.lower(),
            )
            if len(marker) >= 3 and "test" not in marker and "spec" not in marker
        }
        test_content = "\n".join(item.content.lower().replace("\\", "/") for item in test_files)
        if not test_files or not any(marker in test_content for marker in markers):
            errors.append(_validation_issue(
                "TESTS_DO_NOT_EXERCISE_PROJECT", "files",
                "Os testes prometidos nao referenciam entrypoints ou componentes reais da aplicacao.",
                expected_type="tests referencing real project entrypoints", value=test_files, repairable=False,
                suggestion="Cria testes reais para os entrypoints ou componentes declarados.",
            ))
    _source, static_analysis = _analyze_normalized_plan_artifacts(data, prompt)
    errors.extend(static_analysis.errors)
    return _deduplicate_issues(errors)


def _security_errors(data: dict[str, Any]) -> list[PlanValidationIssue]:
    errors: list[PlanValidationIssue] = []
    for index, item in enumerate(data["files"]):
        path = item["path"]
        content = item["content"]
        path_field = f"files[{index}].path"
        unsafe_reason = ""
        if path.startswith("/") or re.match(r"^[a-zA-Z]:", path):
            unsafe_reason = "path absoluto"
        elif path == ".." or path.startswith("../") or "/../" in path:
            unsafe_reason = "path fora do projeto"
        elif path.lower().startswith("obsidian_vault/") or "/obsidian_vault/" in path.lower():
            unsafe_reason = "path dentro do Obsidian"
        if unsafe_reason:
            errors.append(_validation_issue(
                "UNSAFE_FILE_PATH", path_field, f"Path recusado ({unsafe_reason}): {path}",
                expected_type="safe project-relative path", value=path, repairable=False,
                suggestion="Usa um path relativo dentro da pasta do projeto e fora do Obsidian.",
            ))
        if len(content.encode("utf-8")) > MAX_FILE_BYTES:
            errors.append(_validation_issue(
                "FILE_TOO_LARGE", f"files[{index}].content",
                f"Ficheiro excede o tamanho maximo: {path}", expected_type=f"<= {MAX_FILE_BYTES} UTF-8 bytes",
                value=content, repairable=False, suggestion="Reduz o ficheiro sem omitir componentes obrigatorios.",
                sensitive=True,
            ))
    commands = list(data["setup_commands"]) + list(data["validation_commands"]) + [data["preview_command"]]
    for index, command in enumerate(commands):
        if command and "obsidian_vault" in command.lower():
            errors.append(_validation_issue(
                "OBSIDIAN_COMMAND_FORBIDDEN", f"commands[{index}]",
                "Um comando do plano referencia Obsidian.", expected_type="project-local command",
                value=command, repairable=False, suggestion="Remove a referencia ao Obsidian do comando.",
                sensitive=True,
            ))
    return errors


def _validated_project_plan_from_normalized(data: dict[str, Any], prompt: str) -> ProjectPlan:
    schema_errors = _schema_errors(data)
    if schema_errors:
        raise ProjectPlanValidationError("PLAN_SCHEMA_INVALID", schema_errors)
    semantic_errors = _semantic_errors(data, prompt)
    if semantic_errors:
        raise ProjectPlanValidationError("PLAN_SEMANTIC_INVALID", semantic_errors)
    security_errors = _security_errors(data)
    if security_errors:
        raise ProjectPlanValidationError("PLAN_SECURITY_INVALID", security_errors)

    files = [
        ProjectFile(path=_safe_relative_file_path(item["path"]), content=item["content"])
        for item in data["files"]
    ]
    components = list(data["components"]) or _infer_components(data["stack"], files)
    return ProjectPlan(
        project_name=data["project_name"].strip(),
        stack=data["stack"].strip(),
        files=files,
        validation_commands=list(data["validation_commands"]),
        preview_command=data["preview_command"].strip(),
        components=components,
        dependencies=list(data["dependencies"]),
        setup_commands=list(data["setup_commands"]),
        entrypoints=[_safe_relative_file_path(path) for path in data["entrypoints"]],
        preview_strategy=dict(data["preview_strategy"]),
        component_files={
            component: [_safe_relative_file_path(path) for path in paths]
            for component, paths in data["component_files"].items()
        },
        constraints=list(data["constraints"]),
        rationale=data["rationale"].strip(),
    )


def validate_project_plan(data: dict[str, Any], prompt: str = "") -> ProjectPlan:
    normalized, _repairs = repair_project_plan_mechanically(data)
    return _validated_project_plan_from_normalized(normalized, prompt)


def _assert_project_child(project_rel_dir: str, relative_file: str) -> str:
    project_abs = ag_tools.resolve_workspace_path(project_rel_dir)
    file_abs = ag_tools.resolve_workspace_path(f"{project_rel_dir}/{relative_file}")
    if os.path.commonpath([project_abs, file_abs]) != project_abs:
        raise ProjectBuilderError(f"Ficheiro fora da pasta do projeto: {relative_file}")
    return file_abs


def _command_is_project_safe(command: str) -> tuple[bool, str]:
    allowed, reason = ag_tools.validate_local_command(command)
    if not allowed:
        return False, reason
    lowered = normalize_prompt(command)
    for pattern in PROJECT_COMMAND_DENYLIST:
        if re.search(pattern, lowered):
            return False, "comando long-running, instalacao ou preview nao permitido como validacao"
    if "obsidian_vault" in lowered:
        return False, "comando referencia Obsidian"
    return True, ""


def _result_ok(output: str) -> bool:
    text = normalize_prompt(output)
    if any(marker in text for marker in ["erro de seguranca", "erro ao executar", "excedeu o tempo limite"]):
        return False
    match = re.search(r"c[oó]digo\s+(\d+)", text)
    if match and match.group(1) != "0":
        return False
    return True


def _sanitize_command(command: str) -> str:
    return re.sub(r"\s+", " ", str(command or "")).strip()[:500]


def _validate_project_working_directory(working_directory: str, project_dir: str) -> str:
    candidate = os.path.realpath(os.path.abspath(str(working_directory or "")))
    expected = os.path.realpath(os.path.abspath(str(project_dir or "")))
    projects_root = os.path.realpath(ag_tools.resolve_workspace_path(PROJECT_ROOT_REL))
    workspace_root = os.path.realpath(ag_tools.resolve_workspace_path("."))

    if os.path.normcase(candidate) == os.path.normcase(workspace_root):
        raise ProjectBuilderError("working_directory nao pode ser o root global do JARVIS.")
    try:
        inside_projects = os.path.commonpath([projects_root, candidate]) == projects_root
    except ValueError:
        inside_projects = False
    if not inside_projects:
        raise ProjectBuilderError("working_directory deve ficar dentro de workspace/projects.")
    relative_parts = Path(os.path.relpath(candidate, projects_root)).parts
    if any("obsidian" in part.lower() for part in relative_parts):
        raise ProjectBuilderError("working_directory no Obsidian nao e permitido.")
    if os.path.normcase(candidate) != os.path.normcase(expected):
        raise ProjectBuilderError("working_directory nao corresponde ao projeto atual.")
    if not os.path.isdir(candidate):
        raise ProjectBuilderError("working_directory nao existe ou nao e um diretorio.")
    return candidate


def _command_output(exit_code: int | None, stdout: str, stderr: str, timed_out: bool) -> str:
    if timed_out:
        status = "Erro: O comando excedeu o tempo limite."
    elif exit_code is None:
        status = "Erro controlado ao preparar o comando."
    else:
        status = f"Comando terminado com codigo {exit_code}."
    return f"{status}\n\n[STDOUT]\n{stdout}\n\n[STDERR]\n{stderr}"


def _stream_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def _process_creation_options() -> dict[str, Any]:
    if os.name == "nt":
        flags = int(getattr(subprocess, "CREATE_NO_WINDOW", 0))
        flags |= int(getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
        return {"creationflags": flags} if flags else {}
    return {"start_new_session": True}


def _pid_exists(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        try:
            import ctypes
            from ctypes import wintypes

            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
            kernel32.OpenProcess.restype = wintypes.HANDLE
            kernel32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
            kernel32.GetExitCodeProcess.restype = wintypes.BOOL
            kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
            kernel32.CloseHandle.restype = wintypes.BOOL
            process = kernel32.OpenProcess(0x1000, False, pid)
            if not process:
                return False
            try:
                exit_code = wintypes.DWORD()
                if not kernel32.GetExitCodeProcess(process, ctypes.byref(exit_code)):
                    return False
                return exit_code.value == 259  # STILL_ACTIVE
            finally:
                kernel32.CloseHandle(process)
        except (AttributeError, OSError):
            return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


async def _terminate_owned_process_tree(
    process: subprocess.Popen, grace_seconds: float = 3.0
) -> bool:
    if process.poll() is not None:
        return True
    if os.name == "nt":
        try:
            process.send_signal(signal.CTRL_BREAK_EVENT)
        except (AttributeError, OSError):
            try:
                process.terminate()
            except OSError:
                pass
    else:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            return True
        except OSError:
            try:
                process.terminate()
            except OSError:
                pass

    deadline = time.monotonic() + max(0.1, grace_seconds)
    while process.poll() is None and time.monotonic() < deadline:
        await asyncio.sleep(0.05)
    if process.poll() is None:
        if os.name == "nt":
            await _taskkill_owned_pids([process.pid], timeout=max(0.5, grace_seconds))
        else:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except OSError:
                try:
                    process.kill()
                except OSError:
                    pass
        force_deadline = time.monotonic() + max(0.5, grace_seconds)
        while process.poll() is None and time.monotonic() < force_deadline:
            await asyncio.sleep(0.05)
    if process.poll() is None:
        try:
            process.kill()
        except OSError:
            pass
        final_deadline = time.monotonic() + 0.5
        while process.poll() is None and time.monotonic() < final_deadline:
            await asyncio.sleep(0.05)
    for stream in (process.stdout, process.stderr, process.stdin):
        if stream is not None and not getattr(stream, "closed", False):
            try:
                stream.close()
            except OSError:
                pass
    return process.poll() is not None and not _pid_exists(process.pid)


class _WindowsJob:
    def __init__(self):
        self.handle = None
        self.assigned = False
        if os.name != "nt":
            return
        try:
            import ctypes
            from ctypes import wintypes

            class IO_COUNTERS(ctypes.Structure):
                _fields_ = [
                    ("ReadOperationCount", ctypes.c_ulonglong),
                    ("WriteOperationCount", ctypes.c_ulonglong),
                    ("OtherOperationCount", ctypes.c_ulonglong),
                    ("ReadTransferCount", ctypes.c_ulonglong),
                    ("WriteTransferCount", ctypes.c_ulonglong),
                    ("OtherTransferCount", ctypes.c_ulonglong),
                ]

            class BASIC_LIMITS(ctypes.Structure):
                _fields_ = [
                    ("PerProcessUserTimeLimit", ctypes.c_longlong),
                    ("PerJobUserTimeLimit", ctypes.c_longlong),
                    ("LimitFlags", wintypes.DWORD),
                    ("MinimumWorkingSetSize", ctypes.c_size_t),
                    ("MaximumWorkingSetSize", ctypes.c_size_t),
                    ("ActiveProcessLimit", wintypes.DWORD),
                    ("Affinity", ctypes.c_size_t),
                    ("PriorityClass", wintypes.DWORD),
                    ("SchedulingClass", wintypes.DWORD),
                ]

            class EXTENDED_LIMITS(ctypes.Structure):
                _fields_ = [
                    ("BasicLimitInformation", BASIC_LIMITS),
                    ("IoInfo", IO_COUNTERS),
                    ("ProcessMemoryLimit", ctypes.c_size_t),
                    ("JobMemoryLimit", ctypes.c_size_t),
                    ("PeakProcessMemoryUsed", ctypes.c_size_t),
                    ("PeakJobMemoryUsed", ctypes.c_size_t),
                ]

            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
            kernel32.CreateJobObjectW.restype = wintypes.HANDLE
            kernel32.SetInformationJobObject.argtypes = [
                wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD,
            ]
            kernel32.SetInformationJobObject.restype = wintypes.BOOL
            kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
            kernel32.OpenProcess.restype = wintypes.HANDLE
            kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
            kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
            kernel32.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
            kernel32.TerminateJobObject.restype = wintypes.BOOL
            kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
            kernel32.CloseHandle.restype = wintypes.BOOL
            handle = kernel32.CreateJobObjectW(None, None)
            if not handle:
                return
            limits = EXTENDED_LIMITS()
            limits.BasicLimitInformation.LimitFlags = 0x00002000
            if not kernel32.SetInformationJobObject(
                handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)
            ):
                kernel32.CloseHandle(handle)
                return
            self.handle = handle
            self._kernel32 = kernel32
        except (AttributeError, OSError, TypeError):
            self.handle = None

    def assign(self, pid: int) -> bool:
        if self.handle is None:
            return False
        process_handle = self._kernel32.OpenProcess(0x0001 | 0x0100 | 0x1000, False, pid)
        if not process_handle:
            return False
        try:
            self.assigned = bool(
                self._kernel32.AssignProcessToJobObject(self.handle, process_handle)
            )
            return self.assigned
        finally:
            self._kernel32.CloseHandle(process_handle)

    def terminate(self) -> bool:
        if self.handle is None or not self.assigned:
            return False
        return bool(self._kernel32.TerminateJobObject(self.handle, 1))

    def close(self) -> None:
        if self.handle is not None:
            self._kernel32.CloseHandle(self.handle)
            self.handle = None


def _windows_descendant_pids(root_pid: int) -> list[int]:
    if os.name != "nt":
        return []
    try:
        import ctypes
        from ctypes import wintypes

        class PROCESSENTRY32W(ctypes.Structure):
            _fields_ = [
                ("dwSize", wintypes.DWORD),
                ("cntUsage", wintypes.DWORD),
                ("th32ProcessID", wintypes.DWORD),
                ("th32DefaultHeapID", ctypes.c_void_p),
                ("th32ModuleID", wintypes.DWORD),
                ("cntThreads", wintypes.DWORD),
                ("th32ParentProcessID", wintypes.DWORD),
                ("pcPriClassBase", wintypes.LONG),
                ("dwFlags", wintypes.DWORD),
                ("szExeFile", wintypes.WCHAR * 260),
            ]

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
        kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
        kernel32.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.c_void_p]
        kernel32.Process32FirstW.restype = wintypes.BOOL
        kernel32.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.c_void_p]
        kernel32.Process32NextW.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL
        snapshot = kernel32.CreateToolhelp32Snapshot(0x00000002, 0)
        if snapshot in (0, ctypes.c_void_p(-1).value):
            return []
        relationships: dict[int, list[int]] = {}
        entry = PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(entry)
        try:
            success = kernel32.Process32FirstW(snapshot, ctypes.byref(entry))
            while success:
                relationships.setdefault(int(entry.th32ParentProcessID), []).append(
                    int(entry.th32ProcessID)
                )
                success = kernel32.Process32NextW(snapshot, ctypes.byref(entry))
        finally:
            kernel32.CloseHandle(snapshot)
        descendants: list[int] = []
        pending = list(relationships.get(root_pid, []))
        while pending:
            pid = pending.pop()
            if pid in descendants:
                continue
            descendants.append(pid)
            pending.extend(relationships.get(pid, []))
        return descendants
    except (AttributeError, OSError, TypeError):
        return []


class _BoundedPipeOutput:
    def __init__(self, limit_bytes: int):
        self.limit_bytes = max(256, int(limit_bytes))
        self.prefix_limit = self.limit_bytes // 2
        self.suffix_limit = self.limit_bytes - self.prefix_limit
        self.prefix = bytearray()
        self.suffix = bytearray()
        self.total_bytes = 0
        self.closed = False
        self.cancelled = False

    async def drain(self, reader: asyncio.StreamReader, stream_name: str, debug: dict[str, Any]) -> None:
        try:
            while True:
                chunk = await reader.read(65536)
                if not chunk:
                    self.closed = True
                    debug[f"{stream_name}_closed_at"] = time.monotonic()
                    logger.debug("project_builder.process.%s_closed", stream_name)
                    return
                self.total_bytes += len(chunk)
                if len(self.prefix) < self.prefix_limit:
                    take = min(self.prefix_limit - len(self.prefix), len(chunk))
                    self.prefix.extend(chunk[:take])
                self.suffix.extend(chunk)
                if len(self.suffix) > self.suffix_limit:
                    del self.suffix[:-self.suffix_limit]
        except asyncio.CancelledError:
            self.cancelled = True
            raise

    @property
    def truncated(self) -> bool:
        return self.total_bytes > self.limit_bytes

    def text(self) -> str:
        if not self.truncated:
            data = bytes(self.prefix)
            if self.total_bytes > len(self.prefix):
                data += bytes(self.suffix[-(self.total_bytes - len(self.prefix)):])
            return data.decode("utf-8", errors="replace")
        marker = f"\n...[output truncated; total_bytes={self.total_bytes}]...\n".encode()
        return (bytes(self.prefix) + marker + bytes(self.suffix)).decode("utf-8", errors="replace")


async def _taskkill_owned_pids(pids: list[int], timeout: float) -> None:
    if os.name != "nt":
        return
    deadline = time.monotonic() + max(0.1, timeout)
    for pid in list(dict.fromkeys(pid for pid in pids if pid > 0)):
        if not _pid_exists(pid):
            continue
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return
        killer: asyncio.subprocess.Process | None = None
        try:
            killer = await asyncio.create_subprocess_exec(
                "taskkill.exe", "/PID", str(pid), "/T", "/F",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
                **_process_creation_options(),
            )
            await asyncio.wait_for(killer.wait(), timeout=remaining)
        except (OSError, asyncio.TimeoutError):
            if killer is not None and killer.returncode is None:
                try:
                    killer.kill()
                except ProcessLookupError:
                    pass
                try:
                    await asyncio.wait_for(killer.wait(), timeout=0.5)
                except asyncio.TimeoutError:
                    pass


async def _cancel_task_finitely(
    task: asyncio.Task | None,
    timeout: float,
    cleanup_errors: list[str],
    label: str,
) -> None:
    if task is None or task.done():
        return
    task.cancel()
    try:
        await asyncio.wait_for(asyncio.shield(task), timeout=timeout)
    except asyncio.CancelledError:
        return
    except asyncio.TimeoutError:
        cleanup_errors.append(f"{label}_cancel_timeout")
    except Exception as exc:
        cleanup_errors.append(f"{label}_cancel_error:{type(exc).__name__}")


async def _run_project_command(
    command: str,
    working_directory: str,
    project_dir: str,
    timeout: float = 60.0,
    environment: dict[str, str] | None = None,
    *,
    command_id: str = "",
    category: str = "SYNTAX",
    required: bool = True,
    journal: ProjectBuildJournal | None = None,
    output_limit_bytes: int = 64 * 1024,
    graceful_shutdown_seconds: float = 0.5,
    force_shutdown_seconds: float = 2.0,
    reader_shutdown_seconds: float = 1.0,
) -> CommandResult:
    clean_command = _sanitize_command(command)
    recorder = getattr(journal, "flight_recorder", None) if journal is not None else None
    started = time.monotonic()
    if recorder is not None:
        recorder.event(
            "command_execution_started",
            phase="TECHNICAL_VALIDATION",
            metadata={
                "command_id": command_id,
                "category": category,
                "command_sha256": hashlib.sha256(clean_command.encode("utf-8")).hexdigest(),
                "working_directory": working_directory,
            },
        )
    try:
        safe, reason = _command_is_project_safe(command)
        if not safe:
            raise ProjectBuilderError(reason)
        resolved_cwd = _validate_project_working_directory(working_directory, project_dir)
        if timeout <= 0:
            raise ProjectBuilderError("timeout deve ser positivo.")
        if environment is not None and not isinstance(environment, dict):
            raise ProjectBuilderError("environment deve ser um objeto de strings.")
        process_environment = os.environ.copy()
        if environment:
            process_environment.update({str(key): str(value) for key, value in environment.items()})
    except (OSError, ProjectBuilderError, ValueError) as exc:
        duration = time.monotonic() - started
        stderr = f"Comando '{clean_command}' nao executado: {exc}"
        if recorder is not None:
            recorder.event(
                "command_execution_failed",
                phase="TECHNICAL_VALIDATION",
                status="FAILED",
                error=exc,
                metadata={"command_id": command_id, "blocked": True},
            )
        return CommandResult(
            command=clean_command,
            ok=False,
            output=_command_output(None, "", stderr, False),
            working_directory=os.path.realpath(os.path.abspath(str(working_directory or ""))),
            exit_code=None,
            stderr=stderr,
            duration=duration,
            status="BLOCKED",
            error_category="VALIDATION_PLAN_INVALID",
            command_id=command_id,
            category=category,
            required=required,
        )

    if os.name == "nt":
        powershell_command = (
            f"& {{ {command} }}; "
            "if ($null -ne $LASTEXITCODE) { exit $LASTEXITCODE }; "
            "if (-not $?) { exit 1 }"
        )
        shell_command = [
            "powershell.exe", "-NoProfile", "-NonInteractive", "-Command", powershell_command,
        ]
    else:
        shell_command = ["/bin/sh", "-lc", command]

    process: asyncio.subprocess.Process | None = None
    stdout_state = _BoundedPipeOutput(output_limit_bytes)
    stderr_state = _BoundedPipeOutput(output_limit_bytes)
    stdout_task: asyncio.Task | None = None
    stderr_task: asyncio.Task | None = None
    wait_task: asyncio.Task | None = None
    monitor_task: asyncio.Task | None = None
    monitor_stop = asyncio.Event()
    job = _WindowsJob()
    timed_out = False
    termination_attempted = False
    termination_succeeded: bool | None = None
    cleanup_completed = False
    cleanup_errors: list[str] = []
    descendant_pids: set[int] = set()
    debug: dict[str, Any] = {}
    result: CommandResult | None = None
    command_fingerprint = hashlib.sha256(clean_command.encode("utf-8")).hexdigest()[:12]

    async def monitor() -> None:
        while not monitor_stop.is_set():
            if process is not None:
                descendants = _windows_descendant_pids(process.pid)
                descendant_pids.update(descendants)
                registry = _owned_process_registry.get(process.pid)
                if registry is not None:
                    registry["descendant_pids"] = sorted(descendant_pids)
            if journal is not None:
                journal.heartbeat()
            try:
                await asyncio.wait_for(monitor_stop.wait(), timeout=0.2)
            except asyncio.TimeoutError:
                pass

    async def force_owned_tree() -> None:
        nonlocal termination_attempted
        termination_attempted = True
        logger.debug(
            "project_builder.process.force_stop %s",
            json.dumps({"pid": process.pid if process else None, "command_id": command_id}),
        )
        if process is None:
            return
        if os.name == "nt":
            job.terminate()
            await _taskkill_owned_pids(
                [process.pid, *sorted(descendant_pids)], force_shutdown_seconds
            )
        else:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except OSError:
                try:
                    process.kill()
                except ProcessLookupError:
                    pass

    try:
        process = await asyncio.create_subprocess_exec(
            *shell_command,
            cwd=resolved_cwd,
            env=process_environment,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            **_process_creation_options(),
        )
        job_assigned = job.assign(process.pid)
        _owned_process_registry[process.pid] = {
            "command_id": command_id,
            "started_at": _utc_timestamp(),
            "descendant_pids": [],
            "job_assigned": job_assigned,
        }
        logger.debug(
            "project_builder.process.started %s",
            json.dumps({
                "pid": process.pid,
                "command_id": command_id,
                "command_fingerprint": command_fingerprint,
                "command_length": len(clean_command),
            }),
        )
        if journal is not None:
            journal.process_started(command_id, process.pid, category, process_group=str(process.pid))
        if recorder is not None:
            recorder.event(
                "process_started",
                phase="TECHNICAL_VALIDATION",
                metadata={"command_id": command_id, "pid": process.pid, "category": category},
            )
        stdout_task = asyncio.create_task(stdout_state.drain(process.stdout, "stdout", debug))
        stderr_task = asyncio.create_task(stderr_state.drain(process.stderr, "stderr", debug))
        wait_task = asyncio.create_task(process.wait())
        monitor_task = asyncio.create_task(monitor())
        try:
            await asyncio.wait_for(asyncio.shield(wait_task), timeout=timeout)
            debug["parent_exited_at"] = time.monotonic()
            logger.debug("project_builder.process.parent_exited %s", json.dumps({"pid": process.pid}))
        except asyncio.TimeoutError:
            timed_out = True
            termination_attempted = True
            debug["timeout_at"] = time.monotonic()
            logger.debug("project_builder.process.timeout %s", json.dumps({"pid": process.pid}))
            if os.name == "nt":
                try:
                    os.kill(process.pid, signal.CTRL_BREAK_EVENT)
                except (AttributeError, OSError):
                    try:
                        process.terminate()
                    except ProcessLookupError:
                        pass
            else:
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except OSError:
                    try:
                        process.terminate()
                    except ProcessLookupError:
                        pass
            logger.debug("project_builder.process.graceful_stop %s", json.dumps({"pid": process.pid}))
            try:
                await asyncio.wait_for(asyncio.shield(wait_task), timeout=graceful_shutdown_seconds)
            except asyncio.TimeoutError:
                await force_owned_tree()
                try:
                    await asyncio.wait_for(asyncio.shield(wait_task), timeout=force_shutdown_seconds)
                except asyncio.TimeoutError:
                    cleanup_errors.append("parent_wait_timeout_after_force")
        finally:
            if process.stdin is not None:
                process.stdin.close()

        descendant_pids.update(_windows_descendant_pids(process.pid))
        alive_descendants = [pid for pid in descendant_pids if _pid_exists(pid)]
        if alive_descendants:
            await force_owned_tree()
        job.close()
        if process.returncode is None:
            await force_owned_tree()
            if wait_task is not None and not wait_task.done():
                try:
                    await asyncio.wait_for(asyncio.shield(wait_task), timeout=force_shutdown_seconds)
                except asyncio.TimeoutError:
                    cleanup_errors.append("parent_wait_timeout_in_cleanup")

        for task, label in ((stdout_task, "stdout_reader"), (stderr_task, "stderr_reader")):
            if task is None or task.done():
                continue
            try:
                await asyncio.wait_for(asyncio.shield(task), timeout=reader_shutdown_seconds)
            except asyncio.TimeoutError:
                logger.debug(
                    "project_builder.process.readers_cancelled %s",
                    json.dumps({"pid": process.pid, "reader": label}),
                )
                await _cancel_task_finitely(task, reader_shutdown_seconds, cleanup_errors, label)

        alive_owned = [
            pid for pid in [process.pid, *sorted(descendant_pids)] if _pid_exists(pid)
        ]
        termination_succeeded = not alive_owned
        cleanup_completed = termination_succeeded and all(
            task is None or task.done() for task in (stdout_task, stderr_task, wait_task)
        )
        stdout = _sanitize_persisted_output(stdout_state.text(), output_limit_bytes + 256)
        stderr = _sanitize_persisted_output(stderr_state.text(), output_limit_bytes + 256)
        if timed_out:
            stderr = f"{stderr}\nComando excedeu o timeout obrigatorio de {timeout:.1f}s.".strip()
        duration = time.monotonic() - started
        exit_code = None if timed_out else process.returncode
        result = CommandResult(
            command=clean_command,
            ok=not timed_out and process.returncode == 0,
            output=_command_output(exit_code, stdout, stderr, timed_out),
            working_directory=resolved_cwd,
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            duration=duration,
            timed_out=timed_out,
            category=category,
            required=required,
            status="PASSED" if not timed_out and process.returncode == 0 else "FAILED",
            error_category="COMMAND_TIMEOUT" if timed_out else "",
            command_id=command_id,
            process_id=process.pid,
            termination_confirmed=termination_succeeded,
            process_started=True,
            termination_attempted=termination_attempted,
            termination_succeeded=termination_succeeded,
            descendant_count=len(descendant_pids),
            stdout_truncated=stdout_state.truncated,
            stderr_truncated=stderr_state.truncated,
            cleanup_completed=cleanup_completed,
            cleanup_errors=cleanup_errors,
        )
        if recorder is not None:
            recorder.event(
                "command_stdout_progress",
                phase="TECHNICAL_VALIDATION",
                metadata={
                    "command_id": command_id,
                    "bytes": stdout_state.total_bytes,
                    "lines": stdout.count("\n") + (1 if stdout else 0),
                    "truncated": stdout_state.truncated,
                },
            )
            recorder.event(
                "command_stderr_progress",
                phase="TECHNICAL_VALIDATION",
                metadata={
                    "command_id": command_id,
                    "bytes": stderr_state.total_bytes,
                    "lines": stderr.count("\n") + (1 if stderr else 0),
                    "truncated": stderr_state.truncated,
                },
            )
            recorder.event(
                "process_timeout" if timed_out else "command_execution_completed",
                phase="TECHNICAL_VALIDATION",
                status="FAILED" if timed_out or not result.ok else "COMPLETED",
                metadata={
                    "command_id": command_id,
                    "pid": process.pid,
                    "exit_code": result.exit_code,
                    "duration_ms": round(duration * 1000, 3),
                    "timed_out": timed_out,
                },
            )
        return result
    except OSError as exc:
        duration = time.monotonic() - started
        stderr = f"Falha ao iniciar o comando '{clean_command}': {exc}"
        result = CommandResult(
            command=clean_command,
            ok=False,
            output=_command_output(None, "", stderr, False),
            working_directory=resolved_cwd,
            exit_code=None,
            stderr=stderr,
            duration=duration,
            status="FAILED",
            error_category="PROCESS_START_FAILED",
            command_id=command_id,
            category=category,
            required=required,
            cleanup_completed=True,
        )
        if recorder is not None:
            recorder.event("command_execution_failed", phase="TECHNICAL_VALIDATION", status="FAILED", error=exc, metadata={"command_id": command_id})
        return result
    finally:
        monitor_stop.set()
        await _cancel_task_finitely(monitor_task, 1.0, cleanup_errors, "monitor")
        if process is not None:
            if process.stdin is not None:
                try:
                    process.stdin.close()
                except (OSError, RuntimeError):
                    cleanup_errors.append("stdin_close_error")
            # Closing an assigned Job Object terminates descendants that still own
            # inherited pipe handles, including after the direct parent has exited.
            job.close()
            if process.returncode is None:
                await force_owned_tree()
                if wait_task is not None and not wait_task.done():
                    try:
                        await asyncio.wait_for(
                            asyncio.shield(wait_task), timeout=force_shutdown_seconds
                        )
                    except asyncio.TimeoutError:
                        cleanup_errors.append("parent_wait_timeout_in_finally")
            for task, label in (
                (stdout_task, "stdout_reader"),
                (stderr_task, "stderr_reader"),
                (wait_task, "wait_task"),
            ):
                await _cancel_task_finitely(task, 1.0, cleanup_errors, label)
            alive_owned = [
                pid for pid in [process.pid, *sorted(descendant_pids)] if _pid_exists(pid)
            ]
            termination_succeeded = not alive_owned
            cleanup_completed = termination_succeeded and not cleanup_errors and all(
                task is None or task.done()
                for task in (stdout_task, stderr_task, wait_task, monitor_task)
            )
            if result is not None:
                result.termination_attempted = termination_attempted
                result.termination_succeeded = termination_succeeded
                result.termination_confirmed = termination_succeeded
                result.descendant_count = len(descendant_pids)
                result.cleanup_completed = cleanup_completed
                result.cleanup_errors = list(cleanup_errors)
            _owned_process_registry.pop(process.pid, None)
            if journal is not None:
                journal.process_finished(
                    command_id,
                    process.pid,
                    termination_confirmed=termination_succeeded,
                )
            if recorder is not None:
                recorder.event(
                    "process_terminated",
                    phase="TECHNICAL_VALIDATION",
                    status="COMPLETED" if termination_succeeded else "FAILED",
                    metadata={"command_id": command_id, "pid": process.pid, "termination_confirmed": termination_succeeded},
                )
        else:
            job.close()
        logger.debug(
            "project_builder.process.cleanup_complete %s",
            json.dumps({
                "pid": process.pid if process else None,
                "cleanup_errors": cleanup_errors,
                "stdout_closed": stdout_state.closed,
                "stderr_closed": stderr_state.closed,
            }),
        )
        if recorder is not None:
            recorder.event(
                "process_cleanup_completed",
                phase="TECHNICAL_VALIDATION",
                status="COMPLETED" if cleanup_completed else "FAILED",
                metadata={"command_id": command_id, "cleanup_completed": cleanup_completed, "cleanup_errors": cleanup_errors},
            )


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _preview_python_executable() -> str:
    if os.name != "nt":
        return sys.executable
    executable = Path(sys.executable)
    pythonw = executable.with_name("pythonw.exe")
    if pythonw.exists():
        return str(pythonw)
    return sys.executable


def _project_has_previewable_file(project_dir: str) -> bool:
    for root, dirs, files in os.walk(project_dir):
        dirs[:] = [item for item in dirs if item not in {"node_modules", ".git", "__pycache__"}]
        if any(filename.lower() == "index.html" for filename in files):
            return True
    return False


def start_static_preview(project_dir: str, serve_directory: str | None = None) -> tuple[bool, str]:
    project_dir = _validate_project_working_directory(project_dir, project_dir)
    preview_root = os.path.realpath(os.path.abspath(serve_directory or project_dir))
    try:
        if os.path.commonpath([project_dir, preview_root]) != project_dir:
            raise ProjectBuilderError("Diretorio de preview fora do projeto.")
    except ValueError as exc:
        raise ProjectBuilderError("Diretorio de preview fora do projeto.") from exc
    if not os.path.isdir(preview_root) or not _project_has_previewable_file(preview_root):
        return False, ""
    port = _find_free_port()
    command = [
        _preview_python_executable(),
        "-m",
        "http.server",
        str(port),
        "--bind",
        "127.0.0.1",
        "--directory",
        preview_root,
    ]
    kwargs: dict[str, Any] = {
        "cwd": project_dir,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "stdin": subprocess.DEVNULL,
    }
    if os.name == "nt":
        flags = 0
        for flag_name in ("CREATE_NO_WINDOW", "DETACHED_PROCESS", "CREATE_NEW_PROCESS_GROUP"):
            flags |= int(getattr(subprocess, flag_name, 0))
        if flags:
            kwargs["creationflags"] = flags
    else:
        kwargs["start_new_session"] = True
    process = subprocess.Popen(command, **kwargs)
    _preview_processes.append(process)
    return True, f"http://127.0.0.1:{port}/"


def _project_builder_setting(name: str, default: str) -> str:
    environment_value = os.getenv(name)
    if environment_value is not None and environment_value.strip():
        return environment_value.strip()
    try:
        values = dotenv_values(ag_tools.resolve_workspace_path(".env"))
    except OSError:
        values = {}
    file_value = values.get(name)
    return str(file_value).strip() if file_value is not None and str(file_value).strip() else default


def _positive_float_setting(name: str, default: float) -> float:
    try:
        value = float(_project_builder_setting(name, str(default)))
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


def _positive_int_setting(name: str, default: int) -> int:
    try:
        value = int(_project_builder_setting(name, str(default)))
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


def project_builder_plan_timeout_config() -> PlanTimeoutConfig:
    return PlanTimeoutConfig(
        connect=_positive_float_setting("PROJECT_BUILDER_PLAN_CONNECT_TIMEOUT", 5.0),
        read=_positive_float_setting("PROJECT_BUILDER_PLAN_READ_TIMEOUT", 300.0),
        write=_positive_float_setting("PROJECT_BUILDER_PLAN_WRITE_TIMEOUT", 15.0),
        pool=_positive_float_setting("PROJECT_BUILDER_PLAN_POOL_TIMEOUT", 5.0),
    )


def _is_focal_correction_prompt(correction: str | None) -> bool:
    if not correction:
        return False
    try:
        payload = json.loads(correction)
    except (TypeError, ValueError):
        return False
    return isinstance(payload, dict) and payload.get("protocol") == FOCAL_CORRECTION_PROTOCOL


def _project_plan_field_json_schema(field_name: str) -> dict[str, Any]:
    spec = PROJECT_PLAN_SCHEMA["properties"].get(field_name) or {}
    field_type = spec.get("type")
    if field_type == "string":
        schema: dict[str, Any] = {"type": "string"}
    elif field_type == "array[string]":
        schema = {"type": "array", "items": {"type": "string"}}
    elif field_type == "object[array[string]]":
        schema = {
            "type": "object",
            "additionalProperties": {"type": "array", "items": {"type": "string"}},
        }
    elif field_type == "object":
        schema = {"type": "object"}
    else:
        schema = {}
    allowed_items = spec.get("allowed_items")
    if field_type == "array[string]" and allowed_items:
        schema["items"]["enum"] = list(allowed_items)
    return schema


def _focal_correction_response_schema(correction: str | dict[str, Any]) -> dict[str, Any]:
    payload = json.loads(correction) if isinstance(correction, str) else deepcopy(correction)
    if not isinstance(payload, dict) or payload.get("protocol") != FOCAL_CORRECTION_PROTOCOL:
        raise ValueError("A correcao nao usa o protocolo focal suportado.")

    allowed_plan_updates = sorted({
        str(field_name)
        for field_name in payload.get("allowed_plan_updates") or []
        if str(field_name) in PROJECT_PLAN_SCHEMA["properties"]
    })
    allowed_replacements = sorted({
        str(path) for path in payload.get("allowed_replacements") or [] if str(path)
    })
    plan_update_context = payload.get("plan_update_context") or {}

    plan_update_properties: dict[str, Any] = {}
    for field_name in allowed_plan_updates:
        field_schema = _project_plan_field_json_schema(field_name)
        if field_name == "components":
            expected = (plan_update_context.get("components") or {}).get(
                "expected_final_complete_value"
            )
            if isinstance(expected, list) and all(isinstance(item, str) for item in expected):
                field_schema = {"const": list(expected)}
        plan_update_properties[field_name] = field_schema

    replacement_item: dict[str, Any] = {
        "type": "object",
        "required": ["path", "content"],
        "additionalProperties": False,
        "properties": {
            "path": {"type": "string"},
            "content": {"type": "string", "minLength": 1},
        },
    }
    replacements_schema: dict[str, Any] = {
        "type": "array",
        "items": replacement_item,
    }
    if allowed_replacements:
        replacement_item["properties"]["path"]["enum"] = allowed_replacements
    else:
        replacements_schema["maxItems"] = 0

    return {
        "type": "object",
        "required": ["plan_updates", "replacements"],
        "additionalProperties": False,
        "properties": {
            "plan_updates": {
                "type": "object",
                "properties": plan_update_properties,
                "additionalProperties": False,
            },
            "replacements": replacements_schema,
        },
    }


def _ollama_generation_contract(correction: str | None) -> _OllamaGenerationContract:
    if not _is_focal_correction_prompt(correction):
        return _OllamaGenerationContract(response_format="json")
    schema = _focal_correction_response_schema(str(correction))
    encoded = json.dumps(
        schema,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return _OllamaGenerationContract(
        response_format=schema,
        structured_output_enabled=True,
        correction_schema_sha256=hashlib.sha256(encoded).hexdigest(),
        correction_schema_length=len(encoded),
        correction_schema_version=FOCAL_CORRECTION_SCHEMA_VERSION,
        streaming_enabled=True,
    )


def _is_structured_output_rejection(response_body: str) -> bool:
    normalized = response_body.casefold()
    structured_markers = ("json schema", "json_schema", "structured output", "format")
    rejection_markers = (
        "unsupported", "not supported", "does not support", "unknown", "not implemented",
    )
    return (
        any(marker in normalized for marker in structured_markers)
        and any(marker in normalized for marker in rejection_markers)
    )


def _ollama_messages(prompt: str, correction: str | None, compact: bool) -> list[dict[str, str]]:
    if _is_focal_correction_prompt(correction):
        return [
            {
                "role": "system",
                "content": (
                    "You are a deterministic focal project-plan corrector. Return exactly one valid JSON "
                    "object matching the supplied focal response schema. Do not return markdown, prose, a "
                    "complete project plan, unchanged files, patches, or artifacts outside the allowlists."
                ),
            },
            {"role": "user", "content": str(correction)},
        ]
    schema_text = project_plan_schema_prompt()
    correction_text = f"\nSchema correction required (structured):\n{correction}" if correction else ""
    if compact:
        system = (
            "Return one strict JSON object only. No markdown, prose, tools or hidden reasoning. "
            "Preserve every requested component, constraint, stack requirement and validation. "
            + (
                "Return the required correction envelope containing the complete corrected_plan and "
                "correction_manifest. Return complete file contents, never patches or unchanged placeholders."
                if correction else
                "Return the complete project plan, not a patch."
            )
        )
        user = (
            f"Authoritative schema used by the validator:\n{schema_text}\n"
            + (
                "The authoritative project schema applies to corrected_plan inside the correction envelope. "
                if correction else ""
            )
            + "Use the exact declared types. Paths in files must be unique. entrypoints must be an array "
            "of strings. Do not omit required fields. Do not add unknown top-level or file properties. "
            "File contents must remain complete; tests must exercise real entrypoints; commands must be finite.\n"
            f"Objective and mandatory constraints:\n{prompt}{correction_text}"
        )
    else:
        system = (
            "Es um gerador de planos de projeto. Responde apenas JSON valido, sem markdown ou prosa. "
            "Nao chames ferramentas nem reveles raciocinio interno. Nao uses Obsidian. "
            "Nao escrevas ficheiros .md para codigo. Todos os paths devem ser relativos ao projeto. "
            "Os testes devem exercitar entrypoints e componentes reais; testes triviais nao sao validacao. "
            "Como instalacoes arbitrarias sao bloqueadas, prefere standard-library sem dependencias externas."
        )
        user = (
            f"Cria um plano que cumpra este schema autoritativo:\n{schema_text}\n"
            "Os paths em files devem ser unicos e entrypoints deve ser sempre array de strings. "
            "Nao omitas campos obrigatorios nem adiciones propriedades desconhecidas. "
            "Os comandos executam no root do projeto e devem terminar rapidamente. "
            f"Pedido e constraints obrigatorias:\n{prompt}{correction_text}"
        )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def _ollama_message_length(messages: list[dict[str, str]]) -> int:
    return sum(len(str(item.get("content") or "").encode("utf-8")) for item in messages)


class OllamaPlanRequester:
    def __init__(
        self,
        *,
        transport: Any | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        heartbeat: Callable[[], None] | None = None,
        flight_recorder: Any | None = None,
        model_harness: ModelHarness | None = None,
    ):
        self.provider = PLAN_PROVIDER
        self.model = _project_builder_setting("OLLAMA_MODEL", "qwen3.5:9b")
        self.timeout_config = project_builder_plan_timeout_config()
        self.max_output_tokens = _positive_int_setting("PROJECT_BUILDER_PLAN_MAX_OUTPUT_TOKENS", 16_384)
        self.num_ctx = _positive_int_setting("PROJECT_BUILDER_PLAN_CONTEXT_TOKENS", 32_768)
        self.keep_alive = _project_builder_setting("PROJECT_BUILDER_PLAN_KEEP_ALIVE", "15m")
        self.backoff = _positive_float_setting("PROJECT_BUILDER_PLAN_RETRY_BACKOFF", 1.0)
        self.transport = transport
        self.sleep = sleep
        self.heartbeat_callback = heartbeat
        self.flight_recorder = flight_recorder
        self._last_heartbeat = 0.0
        self.attempts: list[PlanAttemptRecord] = []
        self.readiness_checks: list[dict[str, Any]] = []
        self.first_error: dict[str, str] | None = None
        self.final_error: dict[str, str] | None = None
        self.prompt_length = 0
        self.context_builder = ContextBuilder()
        self.harness_operation_id = f"project_builder:{uuid.uuid4().hex}"
        if model_harness is None:
            if transport is None:
                model_harness = get_model_harness()
            else:
                model_harness = create_runtime_model_harness(
                    ollama_provider=OllamaChatProvider(
                        default_model=self.model,
                        transport=transport,
                        keep_alive=self.keep_alive,
                    )
                )
        self.model_harness = model_harness

    def _heartbeat(self, *, force: bool = False) -> None:
        now = time.monotonic()
        if self.heartbeat_callback is None or (not force and now - self._last_heartbeat < 2.0):
            return
        self.heartbeat_callback()
        self._last_heartbeat = now

    def _record(self, event: str, *, phase: str = "REQUESTER", attempt: int = 0, metadata: dict[str, Any] | None = None, status: str = "OBSERVED", error: BaseException | None = None, progress_counter: int | None = None) -> None:
        if self.flight_recorder is not None:
            if progress_counter is not None and hasattr(self.flight_recorder, "next_progress"):
                progress_counter = self.flight_recorder.next_progress()
            self.flight_recorder.event(
                event,
                phase=phase,
                attempt=attempt,
                metadata=metadata,
                status=status,
                error=error,
                progress_counter=progress_counter,
            )

    @property
    def attempt_count(self) -> int:
        return len(self.attempts)

    def diagnostics(self) -> dict[str, Any]:
        completed = next((item for item in reversed(self.attempts) if item.final_plan_hash), None)
        latest = self.attempts[-1] if self.attempts else None
        harness_diagnostics = getattr(
            self.model_harness,
            "diagnostics",
            None,
        )
        return {
            "provider": self.provider,
            "model": self.model,
            "attempt_count": self.attempt_count,
            "durations": [round(item.duration, 4) for item in self.attempts],
            "timeout_config": self.timeout_config.to_dict(),
            "prompt_length": self.prompt_length,
            "base_prompt_length": max((item.base_prompt_length for item in self.attempts), default=0),
            "correction_prompt_length": max(
                (item.correction_prompt_length for item in self.attempts), default=0
            ),
            "effective_prompt_length": latest.effective_prompt_length if latest else 0,
            "attempts": [asdict(item) for item in self.attempts],
            "readiness": list(self.readiness_checks),
            "generation_config": {
                "max_output_tokens": self.max_output_tokens,
                "context_tokens": self.num_ctx,
                "keep_alive": self.keep_alive,
                "stream": latest.streaming_enabled if latest else True,
                "json_format": True,
                "structured_output_enabled": (
                    latest.structured_output_enabled if latest else False
                ),
                "correction_schema_sha256": (
                    latest.correction_schema_sha256 if latest else ""
                ),
                "correction_schema_length": (
                    latest.correction_schema_length if latest else 0
                ),
                "correction_schema_version": (
                    latest.correction_schema_version if latest else ""
                ),
                "streaming_enabled": latest.streaming_enabled if latest else True,
            },
            "first_error": self.first_error,
            "final_error": self.final_error,
            "locally_repaired": bool(completed and completed.local_repairs),
            "local_repairs": list(completed.local_repairs) if completed else [],
            "corrected_by_model": bool(completed and completed.corrected_by_model),
            "final_plan_hash": completed.final_plan_hash if completed else "",
            "model_harness": (
                harness_diagnostics()
                if callable(harness_diagnostics)
                else {"injected": True}
            ),
        }

    def planning_error(self, category: str, message: str) -> ProjectBuilderPlanningError:
        self.final_error = {"category": category, "error_type": category, "message": message}
        return ProjectBuilderPlanningError(category, message, self.diagnostics())

    def validation_error(self, failure: _PlanValidationFailure) -> ProjectBuilderPlanningError:
        messages = {
            "PLAN_JSON_INVALID": "O plano devolvido nao e JSON valido.",
            "PLAN_SCHEMA_INVALID": "O plano JSON nao cumpre o schema obrigatorio.",
            "PLAN_SEMANTIC_INVALID": "O plano JSON nao cumpre os requisitos semanticos.",
            "PLAN_SECURITY_INVALID": "O plano JSON viola a politica de seguranca.",
            "PLAN_CORRECTION_FAILED": "A correcao final nao demonstrou eficacia observavel.",
        }
        message = messages.get(failure.category, "O plano devolvido e invalido.")
        return self.planning_error(failure.category, message)

    def note_validation_failure(self, failure: _PlanValidationFailure) -> None:
        error_message = (
            "O plano devolvido nao e JSON valido."
            if failure.category == "PLAN_JSON_INVALID"
            else str(failure.cause)
        )
        error_data = {
            "category": failure.category,
            "error_type": type(failure.cause).__name__,
            "message": error_message[:500],
        }
        if self.attempts:
            record = self.attempts[-1]
            record.status = "FAILED"
            record.error_type = error_data["error_type"]
            record.error_category = failure.category
            record.raw_response_length = failure.raw_response_length
            record.parse_status = failure.parse_status
            record.local_repairs = list(failure.local_repairs)
            structured_errors = [issue.to_dict() for issue in failure.errors]
            if failure.category == "PLAN_SCHEMA_INVALID":
                record.schema_errors = structured_errors
            elif failure.category == "PLAN_SEMANTIC_INVALID":
                record.semantic_errors = structured_errors
            elif failure.category == "PLAN_SECURITY_INVALID":
                record.security_errors = structured_errors
            elif failure.category == "PLAN_CORRECTION_FAILED":
                record.correction_errors = structured_errors
            record.retry_reason = (
                f"correction:{failure.category}"
                if self.attempt_count < PLAN_MAX_ATTEMPTS
                else ""
            )
        if self.first_error is None:
            self.first_error = error_data
        self.final_error = error_data

    def note_plan_processing(self, result: _ProcessedProjectPlan, *, corrected_by_model: bool) -> None:
        if not self.attempts:
            return
        record = self.attempts[-1]
        record.raw_response_length = result.raw_response_length
        record.parse_status = result.parse_status
        record.local_repairs = list(result.local_repairs)
        record.corrected_by_model = corrected_by_model
        record.final_plan_hash = result.final_plan_hash
        self.final_error = None

    async def _generate(
        self,
        prompt: str,
        correction: str | None,
        attempt: int,
        generation_contract: _OllamaGenerationContract,
    ) -> str:
        compact = attempt > 1
        messages = _ollama_messages(prompt, correction, compact)
        candidates = (
            (
                ContextCandidate(
                    source="project_builder:focal_correction",
                    kind="correction",
                    content=correction,
                    relevance_score=1.0,
                    explicitly_requested=True,
                ),
            )
            if correction
            else ()
        )
        context = self.context_builder.build(ContextBuildRequest(
            task_summary="ProjectBuilder structured planning",
            candidates=candidates,
            allowed_kinds=("correction",),
            max_items=1,
            max_chars=max(1, len(correction or "")),
        ))
        expected_format = (
            OutputFormat.JSON_SCHEMA
            if generation_contract.structured_output_enabled
            else OutputFormat.JSON
        )

        def on_provider_event(
            event: str,
            metadata: dict[str, Any],
            status: str,
        ) -> None:
            self._heartbeat(force=event != "stream_progress")
            event_metadata = dict(metadata)
            if event == "readiness_check_completed":
                readiness = {
                    "attempt": attempt,
                    **event_metadata,
                }
                self.readiness_checks.append(readiness)
                event_metadata = readiness
            elif event == "http_request_started":
                event_metadata.update({
                    "prompt_bytes": len(prompt.encode("utf-8")),
                    "correction_bytes": (
                        len(correction.encode("utf-8"))
                        if correction
                        else 0
                    ),
                })
            elif (
                event == "stream_completed"
                and self.flight_recorder is not None
            ):
                self.flight_recorder.write_payload_metrics({
                    "attempt": attempt,
                    **event_metadata,
                })
            self._record(
                event,
                attempt=attempt,
                status=status,
                metadata=event_metadata,
                progress_counter=(
                    int(event_metadata.get("chunks") or 0)
                    if event == "stream_progress"
                    else None
                ),
            )

        provider_options = OllamaExecutionOptions(
            connect_timeout=self.timeout_config.connect,
            read_timeout=self.timeout_config.read,
            write_timeout=self.timeout_config.write,
            pool_timeout=self.timeout_config.pool,
            readiness_timeout=min(self.timeout_config.read, 15.0),
            keep_alive=self.keep_alive,
            require_readiness=True,
            require_done=True,
            output_character_limit=self.max_output_tokens * 12,
            event_callback=on_provider_event,
        )
        self._record(
            "model_attempt_started",
            attempt=attempt,
            metadata={
                "phase": (
                    "plan_correction" if correction else "plan"
                ),
            },
        )
        request = ModelRequest(
            task_profile="STRUCTURED_EXTRACTION",
            system_prompt=messages[0]["content"],
            user_prompt=messages[1]["content"],
            context=context,
            allowed_tools=(),
            expected_output=ExpectedOutput(
                format=expected_format,
                schema=(
                    generation_contract.response_format
                    if isinstance(
                        generation_contract.response_format,
                        dict,
                    )
                    else None
                ),
                defer_validation=True,
                validation_owner="ProjectBuilder",
            ),
            temperature=0,
            max_context_tokens=self.num_ctx,
            max_output_tokens=self.max_output_tokens,
            metadata={
                "consumer": "ProjectBuilder",
                "phase": (
                    "plan_correction" if correction else "plan"
                ),
                "attempt": attempt,
                "structured_output_enabled": (
                    generation_contract.structured_output_enabled
                ),
                "correction_schema_sha256": (
                    generation_contract.correction_schema_sha256
                ),
                "progress_key": self.harness_operation_id,
            },
            model_preferences=ModelPreferences(
                providers=(self.provider,),
                models=(self.model,),
                mode="chat",
            ),
            execution_constraints=ExecutionConstraints(
                max_attempts=1,
                timeout_seconds=self.timeout_config.read,
                streaming=generation_contract.streaming_enabled,
                thinking=False,
                allow_recovery=False,
                stop_on_no_progress=False,
                provider_payload=provider_options,
            ),
        )
        response = await self.model_harness.execute(request)
        if response.status != ModelResponseStatus.SUCCEEDED:
            if response.provider_exception is not None:
                raise self._provider_failure(
                    response.provider_exception,
                ) from response.provider_exception
            raise _PlanAttemptFailure(
                "PLAN_HTTP_ERROR",
                "O Model Harness nao concluiu a chamada de planeamento.",
                retryable=False,
                error_type=response.status.value,
                partial_response=bool(response.raw_text),
            )
        if self.flight_recorder is not None:
            self.flight_recorder.write_raw_artifact(
                f"response_attempt_{attempt}.jsonl",
                response.raw_text,
            )
        return response.raw_text

    def _provider_failure(
        self,
        error: BaseException,
    ) -> _PlanAttemptFailure:
        error_type = type(error).__name__
        partial = bool(
            getattr(error, "partial_response", False)
        )
        if isinstance(error, OllamaModelNotFoundError):
            return _PlanAttemptFailure(
                "MODEL_NOT_FOUND",
                str(error),
                retryable=False,
                error_type=error_type,
                partial_response=partial,
            )
        if isinstance(
            error,
            OllamaStructuredOutputUnsupportedError,
        ):
            return _PlanAttemptFailure(
                "CORRECTION_STRUCTURED_OUTPUT_UNSUPPORTED",
                str(error),
                retryable=False,
                error_type=error_type,
                partial_response=partial,
            )
        if isinstance(error, OllamaOutputLimitError):
            return _PlanAttemptFailure(
                "PLAN_OUTPUT_LIMIT_EXCEEDED",
                str(error),
                retryable=False,
                error_type=error_type,
                partial_response=partial,
            )
        if isinstance(error, OllamaIncompleteResponseError):
            return _PlanAttemptFailure(
                "PLAN_HTTP_ERROR",
                str(error),
                retryable=False,
                error_type=error_type,
                partial_response=partial,
            )
        if error_type in {
            "ConnectTimeout",
            "ConnectError",
            "PoolTimeout",
        }:
            return _PlanAttemptFailure(
                "OLLAMA_UNAVAILABLE",
                "Nao foi possivel ligar ao Ollama para gerar o plano.",
                retryable=True,
                error_type=error_type,
                partial_response=partial,
            )
        if error_type == "ReadTimeout":
            latest_readiness = (
                self.readiness_checks[-1]
                if self.readiness_checks
                else {}
            )
            category = (
                "MODEL_LOAD_TIMEOUT"
                if latest_readiness.get("model_loaded") is False
                and not partial
                else "PLAN_READ_TIMEOUT"
            )
            return _PlanAttemptFailure(
                category,
                "Ollama excedeu o timeout de leitura durante o planeamento.",
                retryable=True,
                error_type=error_type,
                partial_response=partial,
            )
        response = getattr(error, "response", None)
        status_code = getattr(response, "status_code", None)
        if isinstance(status_code, int):
            return _PlanAttemptFailure(
                "PLAN_HTTP_ERROR",
                f"Ollama planning devolveu HTTP {status_code}.",
                retryable=status_code >= 500,
                error_type=error_type,
                partial_response=partial,
            )
        if isinstance(error, OllamaProviderResponseError):
            return _PlanAttemptFailure(
                "PLAN_HTTP_ERROR",
                str(error),
                retryable=False,
                error_type=error_type,
                partial_response=partial,
            )
        return _PlanAttemptFailure(
            "PLAN_HTTP_ERROR",
            "Erro controlado no provider durante o planeamento.",
            retryable=False,
            error_type=error_type,
            partial_response=partial,
        )

    async def __call__(self, prompt: str, correction: str | None = None) -> str:
        self._record(
            "requester_started",
            metadata={
                "prompt_bytes": len(prompt.encode("utf-8")),
                "correction_bytes": len(correction.encode("utf-8")) if correction else 0,
            },
        )
        self._heartbeat(force=True)
        self.prompt_length = max(self.prompt_length, len(prompt.encode("utf-8")))
        while self.attempt_count < PLAN_MAX_ATTEMPTS:
            attempt = self.attempt_count + 1
            phase = "plan_correction" if correction else ("plan_retry" if attempt > 1 else "plan")
            base_prompt_length = len(prompt.encode("utf-8"))
            correction_prompt_length = len(correction.encode("utf-8")) if correction else 0
            effective_prompt_length = _ollama_message_length(
                _ollama_messages(prompt, correction, attempt > 1)
            )
            generation_contract = _ollama_generation_contract(correction)
            started = time.monotonic()
            try:
                result = await self._generate(
                    prompt,
                    correction,
                    attempt,
                    generation_contract,
                )
            except _PlanAttemptFailure as failure:
                duration = time.monotonic() - started
                can_retry = (
                    failure.retryable
                    and failure.category in PLAN_RETRYABLE_CATEGORIES
                    and attempt < PLAN_MAX_ATTEMPTS
                )
                retry_reason = f"retryable:{failure.category}" if can_retry else ""
                record = PlanAttemptRecord(
                    attempt=attempt,
                    phase=phase,
                    duration=duration,
                    prompt_length=len(prompt.encode("utf-8")),
                    status="FAILED",
                    error_type=failure.error_type,
                    error_category=failure.category,
                    retry_reason=retry_reason,
                    partial_response=failure.partial_response,
                    base_prompt_length=base_prompt_length,
                    correction_prompt_length=correction_prompt_length,
                    effective_prompt_length=effective_prompt_length,
                    structured_output_enabled=generation_contract.structured_output_enabled,
                    correction_schema_sha256=generation_contract.correction_schema_sha256,
                    correction_schema_length=generation_contract.correction_schema_length,
                    correction_schema_version=generation_contract.correction_schema_version,
                    streaming_enabled=generation_contract.streaming_enabled,
                )
                self.attempts.append(record)
                error_data = {
                    "category": failure.category,
                    "error_type": failure.error_type,
                    "message": failure.message,
                }
                if self.first_error is None:
                    self.first_error = error_data
                self.final_error = error_data
                logger.warning(
                    "project_builder.plan_attempt_failed %s",
                    json.dumps({
                        "provider": self.provider,
                        "model": self.model,
                        "attempt": attempt,
                        "duration": round(duration, 4),
                        "phase": phase,
                        "prompt_length": record.prompt_length,
                        "base_prompt_length": base_prompt_length,
                        "correction_prompt_length": correction_prompt_length,
                        "effective_prompt_length": effective_prompt_length,
                        "error_type": failure.error_type,
                        "category": failure.category,
                        "retry_reason": retry_reason,
                        "partial_response": failure.partial_response,
                        "structured_output_enabled": generation_contract.structured_output_enabled,
                        "correction_schema_sha256": generation_contract.correction_schema_sha256,
                        "correction_schema_length": generation_contract.correction_schema_length,
                        "correction_schema_version": generation_contract.correction_schema_version,
                        "streaming_enabled": generation_contract.streaming_enabled,
                    }, ensure_ascii=True),
                )
                if can_retry:
                    self._record(
                        "request_retry_scheduled",
                        attempt=attempt,
                        metadata={"retry_reason": retry_reason},
                    )
                    await self.sleep(self.backoff)
                    continue
                self._record("requester_failed", attempt=attempt, status="FAILED", error=failure)
                raise ProjectBuilderPlanningError(
                    failure.category,
                    failure.message,
                    self.diagnostics(),
                ) from failure
            duration = time.monotonic() - started
            response_length = len(result.encode("utf-8"))
            self.attempts.append(PlanAttemptRecord(
                attempt=attempt,
                phase=phase,
                duration=duration,
                prompt_length=len(prompt.encode("utf-8")),
                status="SUCCEEDED",
                response_length=response_length,
                raw_response_length=response_length,
                base_prompt_length=base_prompt_length,
                correction_prompt_length=correction_prompt_length,
                effective_prompt_length=effective_prompt_length,
                structured_output_enabled=generation_contract.structured_output_enabled,
                correction_schema_sha256=generation_contract.correction_schema_sha256,
                correction_schema_length=generation_contract.correction_schema_length,
                correction_schema_version=generation_contract.correction_schema_version,
                streaming_enabled=generation_contract.streaming_enabled,
            ))
            self.final_error = None
            self._record("requester_completed", attempt=attempt, status="COMPLETED", metadata={
                "response_bytes": response_length,
                "duration_ms": round(duration * 1000, 3),
                "response_sha256": hashlib.sha256(result.encode("utf-8")).hexdigest(),
            })
            logger.info(
                "project_builder.plan_attempt_succeeded %s",
                json.dumps({
                    "provider": self.provider,
                    "model": self.model,
                    "attempt": attempt,
                    "duration": round(duration, 4),
                    "phase": phase,
                    "prompt_length": len(prompt.encode("utf-8")),
                    "base_prompt_length": base_prompt_length,
                    "correction_prompt_length": correction_prompt_length,
                    "effective_prompt_length": effective_prompt_length,
                    "response_length": response_length,
                    "structured_output_enabled": generation_contract.structured_output_enabled,
                    "correction_schema_sha256": generation_contract.correction_schema_sha256,
                    "correction_schema_length": generation_contract.correction_schema_length,
                    "correction_schema_version": generation_contract.correction_schema_version,
                    "streaming_enabled": generation_contract.streaming_enabled,
                }, ensure_ascii=True),
            )
            return result
        raise self.planning_error("PLAN_HTTP_ERROR", "O limite total de tentativas foi atingido.")


async def request_project_plan_from_ollama(prompt: str, correction: str | None = None) -> str:
    requester = OllamaPlanRequester()
    return await requester(prompt, correction)


async def _maybe_await_plan(requester: PlanRequester, prompt: str, correction: str | None) -> str | dict[str, Any]:
    result = requester(prompt, correction)
    if asyncio.iscoroutine(result):
        return await result
    return result


def _prompt_with_intent_constraints(prompt: str, intent: ProjectCreationIntent) -> str:
    constraints = {
        "negative_constraints": intent.negative_constraints,
        "excluded_targets": intent.excluded_targets,
        "separate_work_not_executed": intent.separate_work,
    }
    return (
        f"{prompt}\n\n"
        "ProjectBuilder intent constraints (mandatory):\n"
        f"{json.dumps(constraints, ensure_ascii=False)}\n"
        "Do not create files, commands, dependencies or preview targets that violate these constraints. "
        "Work listed in separate_work_not_executed is outside this project plan."
    )


def _raw_plan_length(raw: str | dict[str, Any]) -> int:
    if isinstance(raw, dict):
        return len(json.dumps(raw, ensure_ascii=False).encode("utf-8"))
    return len(str(raw or "").encode("utf-8"))


def _plan_hash(data: dict[str, Any]) -> str:
    canonical = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _planning_response_payload(raw: str | dict[str, Any]) -> tuple[str, str, int]:
    if isinstance(raw, dict):
        serialized = json.dumps(raw, ensure_ascii=False, separators=(",", ":"))
    else:
        serialized = str(raw or "")
    encoded = serialized.encode("utf-8")
    return (
        _sanitize_persisted_output(serialized, limit=200_000),
        hashlib.sha256(encoded).hexdigest(),
        len(encoded),
    )


def _planning_validation_record(
    label: str,
    raw: str | dict[str, Any],
    outcome: _ProcessedProjectPlan | _PlanValidationFailure,
) -> dict[str, Any]:
    response, response_hash, response_length = _planning_response_payload(raw)
    if isinstance(outcome, _ProcessedProjectPlan):
        return {
            "label": label,
            "response": response,
            "response_sha256": response_hash,
            "response_length": response_length,
            "category": "VALID",
            "parse_status": outcome.parse_status,
            "local_repairs": deepcopy(outcome.local_repairs),
            "errors": [],
            "virtual_files": deepcopy(outcome.virtual_files),
            "static_analysis": deepcopy(outcome.static_analysis),
            "error_artifact_mappings": deepcopy(outcome.error_artifact_mappings),
            "correction_manifest": deepcopy(outcome.correction_manifest),
            "correction_effectiveness": deepcopy(outcome.correction_effectiveness),
            "plan_hash": outcome.final_plan_hash,
        }
    return {
        "label": label,
        "response": response,
        "response_sha256": response_hash,
        "response_length": response_length,
        "category": outcome.category,
        "parse_status": outcome.parse_status,
        "local_repairs": deepcopy(outcome.local_repairs),
        "errors": [item.to_dict() for item in outcome.errors],
        "virtual_files": deepcopy(outcome.virtual_files),
        "static_analysis": deepcopy(outcome.static_analysis),
        "error_artifact_mappings": deepcopy(outcome.error_artifact_mappings),
        "correction_manifest": deepcopy(outcome.correction_manifest),
        "correction_effectiveness": deepcopy(outcome.correction_effectiveness),
        "plan_hash": _plan_hash(outcome.parsed_plan) if outcome.parsed_plan else "",
    }


def _with_validation_history(
    diagnostics: dict[str, Any],
    history: list[dict[str, Any]],
    correction: str | None,
    base_prompt: str = "",
) -> dict[str, Any]:
    result = deepcopy(diagnostics)
    result["validation_history"] = deepcopy(history)
    base_prompt_length = len(base_prompt.encode("utf-8")) if base_prompt else int(
        result.get("base_prompt_length") or result.get("prompt_length") or 0
    )
    correction_prompt_length = len(correction.encode("utf-8")) if correction else 0
    result["base_prompt_length"] = base_prompt_length
    result["correction_prompt_sha256"] = (
        hashlib.sha256(correction.encode("utf-8")).hexdigest() if correction else ""
    )
    result["correction_prompt_length"] = correction_prompt_length
    if not result.get("effective_prompt_length"):
        result["effective_prompt_length"] = correction_prompt_length or base_prompt_length
    if _is_focal_correction_prompt(correction):
        correction_payload = json.loads(str(correction))
        result["focal_correction_protocol"] = correction_payload.get("protocol")
        result["focal_protocol_version"] = correction_payload.get("protocol")
        result["correction_error_count"] = len(correction_payload.get("errors") or [])
        result["correction_files_sent_count"] = len(correction_payload.get("affected_files") or {})
    if history:
        result["final_validation"] = deepcopy(history[-1])
        result["error_artifact_mappings"] = deepcopy(
            history[0].get("error_artifact_mappings") or []
        )
        result["correction_manifest"] = deepcopy(
            history[-1].get("correction_manifest") or []
        )
        result["correction_effectiveness"] = deepcopy(
            history[-1].get("correction_effectiveness") or {}
        )
        effectiveness = result["correction_effectiveness"]
        if effectiveness:
            result["correction_replacements_received"] = int(
                effectiveness.get("replacements_received") or 0
            )
            result["correction_replacements_applied"] = int(
                effectiveness.get("replacements_applied") or 0
            )
            result["correction_plan_update_fields"] = list(
                effectiveness.get("plan_update_fields") or []
            )
            result["correction_manifest_verified"] = bool(
                effectiveness.get("manifest_verified")
            )
            result["correction_revalidation"] = deepcopy(
                effectiveness.get("revalidation") or {}
            )
            result["correction_rejection_reason"] = str(
                effectiveness.get("rejection_reason") or ""
            )
            result["model_manifest_accepted"] = bool(
                effectiveness.get("model_manifest_accepted", False)
            )
            result["derived_changed_plan_fields"] = list(
                effectiveness.get("derived_changed_plan_fields") or []
            )
            result["derived_changed_files"] = list(
                effectiveness.get("derived_changed_files") or []
            )
            result["unchanged_replacements"] = list(
                effectiveness.get("unchanged_replacements") or []
            )
            result["error_resolution_statuses"] = dict(
                effectiveness.get("error_resolution_statuses") or {}
            )
            result["correction_revalidation_executed"] = bool(
                effectiveness.get("revalidation_executed", False)
            )
    return result


def _planning_errors_from_diagnostics(
    diagnostics: dict[str, Any],
    fallback_category: str,
) -> list[dict[str, Any]]:
    final_validation = diagnostics.get("final_validation") or {}
    records = [final_validation]
    if fallback_category == "PLAN_CORRECTION_FAILED":
        records = list(diagnostics.get("validation_history") or records)
    errors: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for record in records:
        for item in record.get("errors") or []:
            normalized = deepcopy(item)
            normalized["category"] = (
                normalized.get("category") or normalized.get("code") or fallback_category
            )
            normalized["phase"] = normalized.get("phase") or "PLAN_SEMANTIC_VALIDATION"
            normalized["suggested_fix"] = (
                normalized.get("suggested_fix") or normalized.get("suggestion") or ""
            )
            normalized["retryable"] = False
            key = (
                str(normalized.get("category") or ""),
                str(normalized.get("field_path") or ""),
                str(normalized.get("file") or ""),
                str(normalized.get("message") or ""),
            )
            if key not in seen:
                seen.add(key)
                errors.append(normalized)
    return errors


def _validated_raw_project_plan(raw: str | dict[str, Any], prompt: str) -> _ProcessedProjectPlan:
    raw_response_length = _raw_plan_length(raw)
    try:
        data = extract_json_object(raw)
    except Exception as exc:
        issue = _validation_issue(
            "INVALID_JSON",
            "$",
            str(exc),
            expected_type="JSON object",
            value=str(raw or ""),
            repairable=False,
            suggestion="Devolve um unico objeto JSON completo sem markdown ou texto adicional.",
            sensitive=True,
        )
        raise _PlanValidationFailure(
            "PLAN_JSON_INVALID",
            ProjectPlanValidationError("PLAN_JSON_INVALID", [issue]),
            raw_response_length=raw_response_length,
            parse_status="INVALID_JSON",
            errors=[issue],
        ) from exc

    normalized, repairs = repair_project_plan_mechanically(data)
    try:
        plan = _validated_project_plan_from_normalized(normalized, prompt)
    except ProjectPlanValidationError as exc:
        virtual_files: list[dict[str, Any]] = []
        static_analysis: dict[str, Any] = {}
        error_artifact_mappings: list[dict[str, Any]] = []
        if exc.category == "PLAN_SEMANTIC_INVALID" and not _schema_errors(normalized):
            source, analysis = _analyze_normalized_plan_artifacts(normalized, prompt)
            virtual_files = source.metadata()
            static_analysis = analysis.to_dict()
            error_artifact_mappings = [
                item.to_dict()
                for item in semantic_error_artifact_mappings(normalized, source, exc.issues)
            ]
        raise _PlanValidationFailure(
            exc.category,
            exc,
            raw_response_length=raw_response_length,
            parse_status="PARSED",
            local_repairs=repairs,
            errors=exc.issues,
            parsed_plan=normalized,
            virtual_files=virtual_files,
            static_analysis=static_analysis,
            error_artifact_mappings=error_artifact_mappings,
        ) from exc
    final_hash = _plan_hash(normalized)
    source, analysis = _analyze_normalized_plan_artifacts(normalized, prompt)
    return _ProcessedProjectPlan(
        plan=plan,
        normalized_data=normalized,
        raw_response_length=raw_response_length,
        parse_status="PARSED",
        local_repairs=repairs,
        final_plan_hash=final_hash,
        virtual_files=source.metadata(),
        static_analysis=analysis.to_dict(),
    )


def _correction_contract_issue(
    code: str,
    message: str,
    *,
    field_path: str = "correction_manifest",
    file: str = "",
    expected: str = "valid correction manifest",
    actual: str = "",
    suggestion: str,
) -> PlanValidationIssue:
    return _validation_issue(
        code,
        field_path,
        message,
        expected_type=expected,
        value=actual,
        repairable=False,
        suggestion=suggestion,
        phase="CORRECTION_EFFECTIVENESS",
        file=file,
        target=file,
        actual=actual,
    )


def _safe_correction_source(data: dict[str, Any] | None) -> PlannedFileSystem:
    if not isinstance(data, dict) or _schema_errors(data):
        return PlannedFileSystem(files={})
    return PlannedFileSystem.from_plan_data(data)


def _correction_response_envelope(
    raw: str | dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]], list[PlanValidationIssue]]:
    payload = extract_json_object(raw)
    errors: list[PlanValidationIssue] = []
    legacy_plan = "corrected_plan" not in payload and "correction_manifest" not in payload
    corrected_plan = payload if legacy_plan else payload.get("corrected_plan")
    manifest = payload.get("correction_manifest") if not legacy_plan else None
    if not isinstance(corrected_plan, dict):
        errors.append(_correction_contract_issue(
            "CORRECTION_MANIFEST_INVALID",
            "A resposta de correcao nao contem corrected_plan como objeto JSON completo.",
            field_path="corrected_plan",
            expected="complete corrected project plan object",
            actual=type(corrected_plan).__name__,
            suggestion="Devolve corrected_plan com o plano completo dentro do envelope obrigatorio.",
        ))
        corrected_plan = {}
    if manifest is None:
        errors.append(_correction_contract_issue(
            "CORRECTION_MANIFEST_MISSING",
            "A segunda resposta nao contem correction_manifest.",
            expected="array of correction manifest entries",
            actual="missing",
            suggestion="Inclui um manifesto para todos os error_code recebidos na prompt de correcao.",
        ))
        return corrected_plan, [], errors
    if not isinstance(manifest, list):
        errors.append(_correction_contract_issue(
            "CORRECTION_MANIFEST_INVALID",
            "correction_manifest deve ser uma lista.",
            expected="array",
            actual=type(manifest).__name__,
            suggestion="Usa uma lista de objetos com error_code, changed_artifacts e resolution.",
        ))
        return corrected_plan, [], errors
    normalized_manifest: list[dict[str, Any]] = []
    for index, item in enumerate(manifest):
        field_path = f"correction_manifest[{index}]"
        if not isinstance(item, dict):
            errors.append(_correction_contract_issue(
                "CORRECTION_MANIFEST_INVALID",
                f"{field_path} deve ser um objeto.",
                field_path=field_path,
                expected="manifest object",
                actual=type(item).__name__,
                suggestion="Usa error_code, changed_artifacts e resolution em cada entrada.",
            ))
            continue
        error_code = item.get("error_code")
        changed = item.get("changed_artifacts")
        resolution = item.get("resolution")
        if (
            not isinstance(error_code, str) or not error_code.strip()
            or not isinstance(changed, list)
            or not all(isinstance(path, str) and path.strip() for path in changed)
            or not isinstance(resolution, str) or not resolution.strip()
        ):
            errors.append(_correction_contract_issue(
                "CORRECTION_MANIFEST_INVALID",
                f"{field_path} nao cumpre o schema obrigatorio.",
                field_path=field_path,
                expected="error_code:string, changed_artifacts:array[string], resolution:string",
                actual=_summarize_offending(item),
                suggestion="Preenche integralmente os tres campos obrigatorios do manifesto.",
            ))
            continue
        normalized_manifest.append({
            "error_code": error_code.strip(),
            "changed_artifacts": list(dict.fromkeys(
                _normalize_relative_path_syntax(path) for path in changed
            )),
            "resolution": resolution.strip(),
        })
    return corrected_plan, normalized_manifest, errors


def validate_correction_effectiveness(
    first_failure: _PlanValidationFailure,
    corrected_plan: dict[str, Any],
    manifest: list[dict[str, Any]],
    envelope_errors: list[PlanValidationIssue] | None = None,
) -> CorrectionEffectivenessResult:
    before_source = _safe_correction_source(first_failure.parsed_plan)
    after_source = _safe_correction_source(corrected_plan)
    before_hashes = before_source.hashes()
    after_hashes = after_source.hashes()
    changed = sorted(
        path for path in set(before_hashes) | set(after_hashes)
        if before_hashes.get(path) != after_hashes.get(path)
    )
    mappings = deepcopy(first_failure.error_artifact_mappings)
    errors = list(envelope_errors or [])
    first_codes = list(dict.fromkeys(issue.code for issue in first_failure.errors))
    manifest_codes = [item["error_code"] for item in manifest]

    missing_codes = sorted(set(first_codes) - set(manifest_codes))
    extra_codes = sorted(set(manifest_codes) - set(first_codes))
    if missing_codes or extra_codes:
        errors.append(_correction_contract_issue(
            "CORRECTION_MANIFEST_INVALID",
            "O manifesto nao corresponde exatamente aos error_code da primeira validacao.",
            expected=f"error codes {first_codes}",
            actual=f"missing={missing_codes}; extra={extra_codes}",
            suggestion="Inclui uma resolucao para cada erro recebido e nao inventes novos error_code.",
        ))

    for index, item in enumerate(manifest):
        for path in item["changed_artifacts"]:
            if path not in after_hashes:
                errors.append(_correction_contract_issue(
                    "CORRECTION_MANIFEST_INVALID",
                    f"O manifesto referencia um artefacto inexistente: {path}.",
                    field_path=f"correction_manifest[{index}].changed_artifacts",
                    file=path,
                    expected="artifact present in corrected_plan.files",
                    actual="missing artifact",
                    suggestion="Referencia apenas paths completos devolvidos no corrected_plan.",
                ))
            elif before_hashes.get(path) == after_hashes.get(path):
                errors.append(_correction_contract_issue(
                    "CORRECTION_DECLARED_FILE_UNCHANGED",
                    f"O manifesto declara {path} como alterado, mas o hash nao mudou.",
                    field_path=f"correction_manifest[{index}].changed_artifacts",
                    file=path,
                    expected="different content hash",
                    actual=after_hashes[path],
                    suggestion="Altera realmente o conteudo necessario ou remove a declaracao falsa.",
                ))

    unchanged_affected: set[str] = set()
    for mapping in mappings:
        if not mapping.get("content_dependent"):
            continue
        affected = {
            _normalize_relative_path_syntax(path)
            for path in mapping.get("affected_artifacts") or []
        }
        if not affected:
            continue
        entries = [item for item in manifest if item["error_code"] == mapping.get("code")]
        declared = {
            path for item in entries for path in item.get("changed_artifacts") or []
        }
        if not declared.intersection(affected):
            errors.append(_correction_contract_issue(
                "CORRECTION_AFFECTED_ARTIFACT_OMITTED",
                f'O manifesto de {mapping.get("code")} nao referencia nenhum artefacto afetado.',
                expected=f"one of {sorted(affected)}",
                actual=f"declared {sorted(declared)}",
                suggestion="Declara pelo menos um artefacto afetado que foi integralmente corrigido.",
            ))
        changed_affected = affected.intersection(changed)
        unchanged_affected.update(
            path for path in affected
            if path in before_hashes and before_hashes.get(path) == after_hashes.get(path)
        )
        if not changed_affected:
            errors.append(_correction_contract_issue(
                "CORRECTION_NO_EFFECT",
                f'A correcao nao alterou nenhum artefacto afetado por {mapping.get("code")}.' ,
                expected=f"observable change in one of {sorted(affected)}",
                actual="all affected content hashes unchanged",
                suggestion="Corrige integralmente pelo menos um artefacto implicado; metadados isolados nao resolvem este erro.",
            ))

    errors = _deduplicate_issues(errors)
    return CorrectionEffectivenessResult(
        valid=not errors,
        errors=errors,
        error_artifact_mappings=mappings,
        correction_manifest=deepcopy(manifest),
        hashes_before=before_hashes,
        hashes_after=after_hashes,
        changed_artifacts=changed,
        unchanged_affected_artifacts=sorted(unchanged_affected),
    )


def _validated_legacy_correction_response(
    raw: str | dict[str, Any],
    prompt: str,
    first_failure: _PlanValidationFailure,
) -> _ProcessedProjectPlan:
    raw_response_length = _raw_plan_length(raw)
    try:
        corrected_plan, manifest, envelope_errors = _correction_response_envelope(raw)
    except Exception:
        return _validated_raw_project_plan(raw, prompt)

    normalized, _repairs = repair_project_plan_mechanically(corrected_plan)
    schema_errors = _schema_errors(normalized)
    if schema_errors and not envelope_errors:
        try:
            return _validated_raw_project_plan(corrected_plan, prompt)
        except _PlanValidationFailure as failure:
            failure.correction_manifest = deepcopy(manifest)
            raise

    effectiveness = validate_correction_effectiveness(
        first_failure,
        normalized,
        manifest,
        envelope_errors,
    )
    if not effectiveness.valid:
        source = _safe_correction_source(normalized)
        cause = ProjectPlanValidationError("PLAN_CORRECTION_FAILED", effectiveness.errors)
        raise _PlanValidationFailure(
            "PLAN_CORRECTION_FAILED",
            cause,
            raw_response_length=raw_response_length,
            parse_status="PARSED",
            local_repairs=_repairs,
            errors=effectiveness.errors,
            parsed_plan=normalized,
            virtual_files=source.metadata(),
            error_artifact_mappings=deepcopy(first_failure.error_artifact_mappings),
            correction_manifest=deepcopy(manifest),
            correction_effectiveness=effectiveness.to_dict(),
        ) from cause

    try:
        processed = _validated_raw_project_plan(corrected_plan, prompt)
    except _PlanValidationFailure as failure:
        failure.error_artifact_mappings = deepcopy(first_failure.error_artifact_mappings)
        failure.correction_manifest = deepcopy(manifest)
        failure.correction_effectiveness = effectiveness.to_dict()
        failure.raw_response_length = raw_response_length
        raise
    processed.raw_response_length = raw_response_length
    processed.error_artifact_mappings = deepcopy(first_failure.error_artifact_mappings)
    processed.correction_manifest = deepcopy(manifest)
    processed.correction_effectiveness = effectiveness.to_dict()
    return processed


def _focal_plan_field_for_issue(issue: PlanValidationIssue) -> str:
    explicit = FOCAL_PLAN_UPDATE_FIELDS_BY_ERROR.get(issue.code) or set()
    if explicit:
        return sorted(explicit)[0] if len(explicit) == 1 else ""
    field_name = re.split(r"[.\[]", str(issue.field_path or ""), maxsplit=1)[0]
    if field_name in PROJECT_PLAN_SCHEMA["properties"] and field_name not in {
        "files", "project_name", "stack", "rationale", "constraints",
    }:
        return field_name
    return ""


def _focal_correction_scope(
    failure: _PlanValidationFailure,
) -> tuple[dict[str, dict[str, list[str]]], list[str], list[str]]:
    source = _safe_correction_source(failure.parsed_plan)
    scope_by_error: dict[str, dict[str, list[str]]] = {
        issue.code: {"plan_updates": [], "replacements": []}
        for issue in failure.errors
    }
    mappings_by_code: dict[str, list[dict[str, Any]]] = {}
    for mapping in failure.error_artifact_mappings:
        mappings_by_code.setdefault(str(mapping.get("code") or ""), []).append(mapping)

    for issue in failure.errors:
        scope = scope_by_error[issue.code]
        plan_fields = set(FOCAL_PLAN_UPDATE_FIELDS_BY_ERROR.get(issue.code) or set())
        inferred_field = _focal_plan_field_for_issue(issue)
        if inferred_field:
            plan_fields.add(inferred_field)
        scope["plan_updates"] = sorted(plan_fields)

        replacement_paths: set[str] = set()
        for mapping in mappings_by_code.get(issue.code, []):
            if issue.code == "COMMAND_TARGET_INVALID":
                command_artifact = str((mapping.get("evidence") or {}).get("command_artifact") or "")
                if source.exists(command_artifact):
                    replacement_paths.add(_normalize_relative_path_syntax(command_artifact))
                continue
            replacement_paths.update(
                _normalize_relative_path_syntax(path)
                for path in mapping.get("affected_artifacts") or []
                if source.exists(path)
            )
        if issue.code != "COMMAND_TARGET_INVALID" and source.exists(issue.file):
            replacement_paths.add(_normalize_relative_path_syntax(issue.file))
        scope["replacements"] = sorted(replacement_paths)

    allowed_plan_updates = sorted({
        field_name
        for scope in scope_by_error.values()
        for field_name in scope["plan_updates"]
    })
    allowed_replacements = sorted({
        path
        for scope in scope_by_error.values()
        for path in scope["replacements"]
    })
    return scope_by_error, allowed_plan_updates, allowed_replacements


def _strict_focal_path(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ProjectBuilderError("O path focal deve ser uma string nao vazia.")
    raw = value.strip().replace("\\", "/")
    if raw.startswith("/") or re.match(r"^[a-zA-Z]:", raw):
        raise ProjectBuilderError(f"Path focal absoluto recusado: {value}")
    return _normalize_relative_path_syntax(_safe_relative_file_path(raw))


def _strict_focal_correction_envelope(
    raw: str | dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, str]], list[PlanValidationIssue]]:
    errors: list[PlanValidationIssue] = []
    try:
        if isinstance(raw, dict):
            payload = deepcopy(raw)
        else:
            payload = json.loads(str(raw or "").strip())
    except (TypeError, ValueError) as exc:
        errors.append(_correction_contract_issue(
            "CORRECTION_JSON_INVALID",
            "A resposta focal nao e um objeto JSON estrito.",
            field_path="$",
            expected="one JSON object without markdown or surrounding text",
            actual=type(exc).__name__,
            suggestion="Responde apenas com JSON sintaticamente valido.",
        ))
        return {}, [], errors
    if not isinstance(payload, dict):
        errors.append(_correction_contract_issue(
            "CORRECTION_RESPONSE_SCHEMA_INVALID",
            "A resposta focal deve ser um objeto JSON.",
            field_path="$",
            expected="object",
            actual=type(payload).__name__,
            suggestion="Usa apenas plan_updates e replacements.",
        ))
        return {}, [], errors

    payload_keys = set(payload)
    unknown = sorted(payload_keys - FOCAL_CORRECTION_RESPONSE_KEYS)
    missing = sorted(FOCAL_CORRECTION_RESPONSE_KEYS - payload_keys)
    if "corrected_plan" in payload_keys or any(
        key in PROJECT_PLAN_SCHEMA["properties"] for key in unknown
    ):
        errors.append(_correction_contract_issue(
            "CORRECTION_FULL_PLAN_FORBIDDEN",
            "A resposta tentou devolver um plano completo em vez de uma correcao focal.",
            field_path="$",
            expected="plan_updates and replacements only",
            actual=f"keys={sorted(payload_keys)}",
            suggestion="Devolve apenas os campos e ficheiros realmente alterados.",
        ))
    elif unknown:
        errors.append(_correction_contract_issue(
            "CORRECTION_RESPONSE_SCHEMA_INVALID",
            f"A resposta focal contem campos desconhecidos: {unknown}.",
            field_path="$",
            expected=f"keys={sorted(FOCAL_CORRECTION_RESPONSE_KEYS)}",
            actual=f"unknown={unknown}",
            suggestion="Remove todos os campos fora do schema focal.",
        ))
    if missing:
        errors.append(_correction_contract_issue(
            "CORRECTION_RESPONSE_SCHEMA_INVALID",
            f"A resposta focal omite campos obrigatorios: {missing}.",
            field_path="$",
            expected=f"keys={sorted(FOCAL_CORRECTION_RESPONSE_KEYS)}",
            actual=f"missing={missing}",
            suggestion="Inclui plan_updates e replacements.",
        ))

    plan_updates = payload.get("plan_updates")
    if not isinstance(plan_updates, dict):
        errors.append(_correction_contract_issue(
            "CORRECTION_RESPONSE_SCHEMA_INVALID",
            "plan_updates deve ser um objeto.",
            field_path="plan_updates",
            expected="object",
            actual=type(plan_updates).__name__,
            suggestion="Usa um objeto vazio quando nenhum campo do plano muda.",
        ))
        plan_updates = {}

    replacements_raw = payload.get("replacements")
    replacements: list[dict[str, str]] = []
    seen_paths: set[str] = set()
    if not isinstance(replacements_raw, list):
        errors.append(_correction_contract_issue(
            "CORRECTION_RESPONSE_SCHEMA_INVALID",
            "replacements deve ser uma lista.",
            field_path="replacements",
            expected="array",
            actual=type(replacements_raw).__name__,
            suggestion="Usa uma lista vazia quando nenhum ficheiro muda.",
        ))
        replacements_raw = []
    for index, item in enumerate(replacements_raw):
        field_path = f"replacements[{index}]"
        if not isinstance(item, dict) or set(item) != {"path", "content"}:
            errors.append(_correction_contract_issue(
                "CORRECTION_REPLACEMENT_INVALID",
                f"{field_path} deve conter apenas path e content.",
                field_path=field_path,
                expected="path:string, content:string",
                actual=_summarize_offending(item),
                suggestion="Devolve o conteudo integral do ficheiro substituido.",
            ))
            continue
        try:
            path = _strict_focal_path(item.get("path"))
        except ProjectBuilderError as exc:
            errors.append(_correction_contract_issue(
                "CORRECTION_REPLACEMENT_INVALID",
                str(exc),
                field_path=f"{field_path}.path",
                expected="safe project-relative path",
                actual=str(item.get("path") or ""),
                suggestion="Usa um path permitido dentro do projeto.",
            ))
            continue
        content = item.get("content")
        if not isinstance(content, str) or not content:
            errors.append(_correction_contract_issue(
                "CORRECTION_REPLACEMENT_INVALID",
                f"{field_path}.content deve ser uma string integral nao vazia.",
                field_path=f"{field_path}.content",
                file=path,
                expected="non-empty string",
                actual="empty string" if content == "" else type(content).__name__,
                suggestion="Devolve o conteudo completo do ficheiro.",
            ))
            continue
        if path in seen_paths:
            errors.append(_correction_contract_issue(
                "CORRECTION_DUPLICATE_PATH",
                f"O path {path} aparece mais do que uma vez em replacements.",
                field_path=f"{field_path}.path",
                file=path,
                expected="unique replacement path",
                actual=path,
                suggestion="Inclui cada ficheiro alterado exatamente uma vez.",
            ))
            continue
        seen_paths.add(path)
        replacements.append({"path": path, "content": content})

    return deepcopy(plan_updates), replacements, _deduplicate_issues(errors)


def _focal_error_resolution_statuses(
    first_failure: _PlanValidationFailure,
    revalidation_errors: list[PlanValidationIssue] | None = None,
    *,
    semantic_evaluated: bool,
) -> dict[str, str]:
    original_codes = list(dict.fromkeys(issue.code for issue in first_failure.errors))
    if not semantic_evaluated:
        return {code: "NOT_EVALUATED" for code in original_codes}
    remaining_codes = {issue.code for issue in revalidation_errors or []}
    return {
        code: "UNRESOLVED" if code in remaining_codes else "RESOLVED"
        for code in original_codes
    }


def _derived_focal_manifest(
    first_failure: _PlanValidationFailure,
    scope_by_error: dict[str, dict[str, list[str]]],
    original_plan: dict[str, Any],
    candidate: dict[str, Any],
    hashes_before: dict[str, str],
    hashes_after: dict[str, str],
    changed_plan_fields: list[str],
    changed_files: list[str],
    resolution_statuses: dict[str, str],
) -> list[dict[str, Any]]:
    changed_plan = set(changed_plan_fields)
    changed_paths = set(changed_files)
    manifest: list[dict[str, Any]] = []
    for code in dict.fromkeys(issue.code for issue in first_failure.errors):
        scope = scope_by_error.get(code) or {"plan_updates": [], "replacements": []}
        scoped_plan_fields = sorted(changed_plan.intersection(scope.get("plan_updates") or []))
        scoped_files = sorted(changed_paths.intersection(scope.get("replacements") or []))
        evidence: dict[str, Any] = {}
        if scoped_plan_fields:
            evidence["plan_fields"] = {
                field_name: {
                    "before": deepcopy(original_plan.get(field_name)),
                    "after": deepcopy(candidate.get(field_name)),
                }
                for field_name in scoped_plan_fields
            }
        if scoped_files:
            evidence["file_hashes"] = {
                path: {
                    "hash_before": hashes_before.get(path, ""),
                    "hash_after": hashes_after.get(path, ""),
                }
                for path in scoped_files
            }
        manifest.append({
            "error_code": code,
            "changed_artifacts": scoped_plan_fields + scoped_files,
            "resolution_status": resolution_statuses.get(code, "NOT_EVALUATED"),
            "evidence": evidence,
        })
    return manifest


def _focal_failure(
    first_failure: _PlanValidationFailure,
    raw_response_length: int,
    errors: list[PlanValidationIssue],
    effectiveness: CorrectionEffectivenessResult,
    manifest: list[dict[str, Any]],
    *,
    category: str = "PLAN_CORRECTION_FAILED",
    static_analysis: dict[str, Any] | None = None,
) -> _PlanValidationFailure:
    effectiveness.valid = False
    effectiveness.errors = list(errors)
    if errors and not effectiveness.rejection_reason:
        effectiveness.rejection_reason = errors[0].code
    cause = ProjectPlanValidationError(category, errors)
    return _PlanValidationFailure(
        category,
        cause,
        raw_response_length=raw_response_length,
        parse_status="PARSED" if errors and errors[0].code != "CORRECTION_JSON_INVALID" else "INVALID_JSON",
        errors=errors,
        parsed_plan=deepcopy(first_failure.parsed_plan),
        virtual_files=_safe_correction_source(first_failure.parsed_plan).metadata(),
        static_analysis=deepcopy(static_analysis or {}),
        error_artifact_mappings=deepcopy(first_failure.error_artifact_mappings),
        correction_manifest=deepcopy(manifest),
        correction_effectiveness=effectiveness.to_dict(),
    )


def _validated_focal_correction_response(
    raw: str | dict[str, Any],
    prompt: str,
    first_failure: _PlanValidationFailure,
) -> _ProcessedProjectPlan:
    raw_response_length = _raw_plan_length(raw)
    original_plan = deepcopy(first_failure.parsed_plan or {})
    original_plan_hash = _plan_hash(original_plan) if original_plan else ""
    before_source = _safe_correction_source(original_plan)
    scope_by_error, allowed_plan_updates, allowed_replacements = _focal_correction_scope(first_failure)
    plan_updates, replacements, errors = _strict_focal_correction_envelope(raw)
    resolution_statuses = _focal_error_resolution_statuses(
        first_failure,
        semantic_evaluated=False,
    )
    manifest: list[dict[str, Any]] = []
    unchanged_replacements: list[str] = []
    effectiveness = CorrectionEffectivenessResult(
        valid=False,
        protocol=FOCAL_CORRECTION_PROTOCOL,
        plan_updates=deepcopy(plan_updates),
        allowed_plan_updates=allowed_plan_updates,
        allowed_replacements=allowed_replacements,
        replacements_received=len(replacements),
        hashes_before=before_source.hashes(),
        hashes_after=before_source.hashes(),
        error_artifact_mappings=deepcopy(first_failure.error_artifact_mappings),
        correction_manifest=[],
        model_manifest_accepted=False,
        error_resolution_statuses=resolution_statuses,
        revalidation={
            "structural": "NOT_RUN",
            "semantic": "NOT_RUN",
            "integrity": "NOT_RUN",
        },
    )

    for field_name, value in plan_updates.items():
        if field_name not in allowed_plan_updates:
            errors.append(_correction_contract_issue(
                "CORRECTION_PLAN_UPDATE_OUT_OF_SCOPE",
                f"plan_updates tentou alterar o campo nao permitido {field_name}.",
                field_path=f"plan_updates.{field_name}",
                expected=f"one of {allowed_plan_updates}",
                actual=field_name,
                suggestion="Altera apenas campos explicitamente autorizados pelos erros.",
            ))
            continue
        if original_plan.get(field_name) == value:
            errors.append(_correction_contract_issue(
                "CORRECTION_DECLARED_PLAN_FIELD_UNCHANGED",
                f"plan_updates declara {field_name}, mas o valor nao mudou.",
                field_path=f"plan_updates.{field_name}",
                expected="different field value",
                actual=_summarize_offending(value),
                suggestion="Remove campos sem alteracao real.",
            ))
        if field_name == "components" and isinstance(value, list):
            original_components = list(original_plan.get("components") or [])
            requested_components = set(_requested_components(prompt))
            added = set(value) - set(original_components)
            if value[:len(original_components)] != original_components or not added.issubset(
                requested_components - set(original_components)
            ):
                errors.append(_correction_contract_issue(
                    "CORRECTION_PLAN_UPDATE_OUT_OF_SCOPE",
                    "A correcao de components deve apenas acrescentar componentes pedidos em falta.",
                    field_path="plan_updates.components",
                    expected=f"original prefix plus missing requested components {sorted(requested_components)}",
                    actual=_summarize_offending(value),
                    suggestion="Mantem os componentes existentes e acrescenta apenas os pedidos em falta.",
                ))

    replacement_by_path = {item["path"]: item["content"] for item in replacements}
    for path, content in replacement_by_path.items():
        original_file = before_source.get(path)
        if path not in allowed_replacements:
            errors.append(_correction_contract_issue(
                "CORRECTION_REPLACEMENT_OUT_OF_SCOPE",
                f"O replacement {path} esta fora da allowlist focal.",
                field_path="replacements",
                file=path,
                expected=f"one of {allowed_replacements}",
                actual=path,
                suggestion="Altera apenas ficheiros explicitamente implicados pelos erros.",
            ))
        elif original_file is None:
            errors.append(_correction_contract_issue(
                "CORRECTION_REPLACEMENT_FILE_NOT_FOUND",
                f"O replacement referencia um ficheiro inexistente: {path}.",
                field_path="replacements",
                file=path,
                expected="existing planned file",
                actual="missing",
                suggestion="Nao cries, removas ou renomeies ficheiros nesta correcao.",
            ))
        elif hashlib.sha256(content.encode("utf-8")).hexdigest() == original_file.content_hash:
            unchanged_replacements.append(path)
            errors.append(_correction_contract_issue(
                "CORRECTION_DECLARED_FILE_UNCHANGED",
                f"O replacement de {path} e identico ao conteudo original.",
                field_path="replacements",
                file=path,
                expected="different content hash",
                actual=original_file.content_hash,
                suggestion="Nao devolvas ficheiros que nao mudaram realmente.",
            ))

    errors = _deduplicate_issues(errors)
    if errors:
        effectiveness.unchanged_replacements = sorted(unchanged_replacements)
        manifest = _derived_focal_manifest(
            first_failure,
            scope_by_error,
            original_plan,
            original_plan,
            before_source.hashes(),
            before_source.hashes(),
            [],
            [],
            resolution_statuses,
        )
        effectiveness.correction_manifest = deepcopy(manifest)
        effectiveness.rejection_reason = errors[0].code
        raise _focal_failure(
            first_failure, raw_response_length, errors, effectiveness, manifest
        )

    candidate = deepcopy(original_plan)
    for field_name, value in plan_updates.items():
        candidate[field_name] = deepcopy(value)
    for item in candidate.get("files") or []:
        normalized_path = _normalize_relative_path_syntax(str(item.get("path") or ""))
        if normalized_path in replacement_by_path:
            item["content"] = replacement_by_path[normalized_path]
    after_source = _safe_correction_source(candidate)
    before_hashes = before_source.hashes()
    after_hashes = after_source.hashes()
    changed_files = sorted(
        path for path in set(before_hashes) | set(after_hashes)
        if before_hashes.get(path) != after_hashes.get(path)
    )
    changed_plan_fields = sorted(
        field_name for field_name in plan_updates
        if original_plan.get(field_name) != candidate.get(field_name)
    )
    actual_changes = set(changed_files) | set(changed_plan_fields)
    effectiveness.hashes_after = after_hashes
    effectiveness.changed_artifacts = sorted(actual_changes)
    effectiveness.derived_changed_plan_fields = changed_plan_fields
    effectiveness.derived_changed_files = changed_files
    effectiveness.unchanged_replacements = sorted(unchanged_replacements)
    effectiveness.replacements_applied = len(changed_files)
    effectiveness.unchanged_affected_artifacts = sorted(
        set(allowed_replacements) - set(changed_files)
    )
    manifest = _derived_focal_manifest(
        first_failure,
        scope_by_error,
        original_plan,
        candidate,
        before_hashes,
        after_hashes,
        changed_plan_fields,
        changed_files,
        resolution_statuses,
    )
    effectiveness.correction_manifest = deepcopy(manifest)

    if not actual_changes:
        pending_codes = list(dict.fromkeys(issue.code for issue in first_failure.errors))
        issue = _correction_contract_issue(
            "CORRECTION_NO_EFFECT",
            "A correcao focal nao alterou campos do plano nem ficheiros.",
            field_path="$",
            expected="at least one derived plan-field or file diff",
            actual=f"changed_plan_fields=[]; changed_files=[]; pending_errors={pending_codes}",
            suggestion="Devolve apenas alteracoes reais que resolvam os erros semanticos pendentes.",
        )
        effectiveness.rejection_reason = issue.code
        raise _focal_failure(
            first_failure, raw_response_length, [issue], effectiveness, manifest
        )

    try:
        processed = _validated_raw_project_plan(candidate, prompt)
    except _PlanValidationFailure as failure:
        effectiveness.revalidation_executed = True
        effectiveness.errors = list(failure.errors)
        if failure.category == "PLAN_SCHEMA_INVALID":
            effectiveness.revalidation["structural"] = "FAILED"
        else:
            effectiveness.revalidation["structural"] = "PASSED"
            effectiveness.revalidation["semantic"] = (
                "FAILED" if failure.category == "PLAN_SEMANTIC_INVALID" else "PASSED"
            )
            effectiveness.revalidation["integrity"] = (
                "FAILED" if failure.category == "PLAN_SECURITY_INVALID" else "NOT_COMPLETED"
            )
        effectiveness.revalidation["category"] = failure.category
        effectiveness.revalidation["errors"] = [item.to_dict() for item in failure.errors]
        effectiveness.rejection_reason = failure.errors[0].code if failure.errors else failure.category
        resolution_statuses = _focal_error_resolution_statuses(
            first_failure,
            failure.errors,
            semantic_evaluated=failure.category != "PLAN_SCHEMA_INVALID",
        )
        manifest = _derived_focal_manifest(
            first_failure,
            scope_by_error,
            original_plan,
            candidate,
            before_hashes,
            after_hashes,
            changed_plan_fields,
            changed_files,
            resolution_statuses,
        )
        effectiveness.error_resolution_statuses = resolution_statuses
        effectiveness.correction_manifest = deepcopy(manifest)
        failure.parsed_plan = deepcopy(original_plan)
        failure.virtual_files = before_source.metadata()
        failure.error_artifact_mappings = deepcopy(first_failure.error_artifact_mappings)
        failure.correction_manifest = deepcopy(manifest)
        failure.correction_effectiveness = effectiveness.to_dict()
        failure.raw_response_length = raw_response_length
        raise

    if processed.local_repairs or processed.normalized_data != candidate:
        issue = _correction_contract_issue(
            "CORRECTION_UNDECLARED_NORMALIZATION",
            "A correcao exigiria normalizacao adicional fora do patch focal declarado.",
            expected="candidate accepted without mechanical repairs",
            actual=f"repairs={processed.local_repairs}",
            suggestion="Devolve tipos e campos ja normalizados no protocolo focal.",
        )
        effectiveness.revalidation.update({
            "structural": "FAILED",
            "semantic": "NOT_RUN",
            "integrity": "NOT_RUN",
        })
        effectiveness.revalidation_executed = True
        effectiveness.rejection_reason = issue.code
        raise _focal_failure(
            first_failure, raw_response_length, [issue], effectiveness, manifest
        )
    if _plan_hash(first_failure.parsed_plan or {}) != original_plan_hash:
        issue = _correction_contract_issue(
            "CORRECTION_ORIGINAL_STATE_MUTATED",
            "O estado original foi alterado durante a correcao focal.",
            expected=original_plan_hash,
            actual=_plan_hash(first_failure.parsed_plan or {}),
            suggestion="Aplica a correcao apenas a uma copia profunda do plano e da VFS.",
        )
        effectiveness.rejection_reason = issue.code
        raise _focal_failure(
            first_failure, raw_response_length, [issue], effectiveness, manifest
        )

    effectiveness.valid = True
    effectiveness.revalidation_executed = True
    resolution_statuses = _focal_error_resolution_statuses(
        first_failure,
        semantic_evaluated=True,
    )
    manifest = _derived_focal_manifest(
        first_failure,
        scope_by_error,
        original_plan,
        candidate,
        before_hashes,
        after_hashes,
        changed_plan_fields,
        changed_files,
        resolution_statuses,
    )
    effectiveness.error_resolution_statuses = resolution_statuses
    effectiveness.correction_manifest = deepcopy(manifest)
    effectiveness.manifest_verified = True
    effectiveness.revalidation = {
        "structural": "PASSED",
        "semantic": "PASSED",
        "integrity": "PASSED",
        "category": "VALID",
        "errors": [],
    }
    effectiveness.rejection_reason = ""
    processed.raw_response_length = raw_response_length
    processed.error_artifact_mappings = deepcopy(first_failure.error_artifact_mappings)
    processed.correction_manifest = deepcopy(manifest)
    processed.correction_effectiveness = effectiveness.to_dict()
    return processed


def _validated_correction_response(
    raw: str | dict[str, Any],
    prompt: str,
    first_failure: _PlanValidationFailure,
) -> _ProcessedProjectPlan:
    if first_failure.category == "PLAN_SEMANTIC_INVALID":
        return _validated_focal_correction_response(raw, prompt, first_failure)
    return _validated_legacy_correction_response(raw, prompt, first_failure)


def _legacy_structured_plan_correction(
    failure: _PlanValidationFailure,
    previous_raw: str | dict[str, Any],
) -> str:
    previous_plan: Any = failure.parsed_plan if failure.parsed_plan is not None else None
    source = _safe_correction_source(failure.parsed_plan)
    mappings = deepcopy(failure.error_artifact_mappings)
    affected_paths = list(dict.fromkeys(
        path
        for mapping in mappings
        for path in mapping.get("affected_artifacts") or []
        if source.exists(path)
    ))
    affected_artifacts = {
        path: {
            "content_hash": source.get(path).content_hash,
            "language": source.get(path).language,
            "component": source.get(path).component,
            "content": source.get(path).content,
        }
        for path in affected_paths
    }
    payload: dict[str, Any] = {
        "instruction": (
            "Return one JSON object with corrected_plan and correction_manifest. "
            "This is the second and final model call; there is no third correction."
        ),
        "category": failure.category,
        "response_schema": {
            "corrected_plan": "complete project plan matching the authoritative project schema",
            "correction_manifest": [{
                "error_code": "one error code received below",
                "changed_artifacts": ["existing/path/returned/in/corrected_plan"],
                "resolution": "specific explanation of how the postconditions are satisfied",
            }],
        },
        "normalized_previous_plan": previous_plan,
        "invalid_previous_plan": previous_plan,
        "previous_plan_included": previous_plan is not None,
        "virtual_file_system": deepcopy(failure.virtual_files),
        "affected_artifacts_with_full_content": affected_artifacts,
        "errors": [issue.to_dict() for issue in failure.errors],
        "semantic_error_artifact_mapping": mappings,
        "requirements": {
            "unique_file_paths": True,
            "entrypoints_type": "array[string]",
            "exact_field_types": True,
            "include_required_fields": True,
            "unknown_properties": False,
            "metadata_only_changes_do_not_fix_content_errors": True,
            "return_all_affected_artifacts_with_complete_content": True,
            "forbid_unchanged_placeholders": ["unchanged", "same as before", "partial patch"],
            "no_unnecessary_dependencies": True,
            "tests_must_not_create_alternate_server": True,
            "node_check_must_not_target_html": True,
            "no_third_call": True,
        },
    }
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def _focal_structured_plan_correction(failure: _PlanValidationFailure, prompt: str) -> str:
    source = _safe_correction_source(failure.parsed_plan)
    scope_by_error, allowed_plan_updates, allowed_replacements = _focal_correction_scope(failure)
    mappings_by_code: dict[str, list[dict[str, Any]]] = {}
    for mapping in failure.error_artifact_mappings:
        mappings_by_code.setdefault(str(mapping.get("code") or ""), []).append(mapping)

    errors_payload: list[dict[str, Any]] = []
    for code in dict.fromkeys(issue.code for issue in failure.errors):
        issues = [issue for issue in failure.errors if issue.code == code]
        mappings = mappings_by_code.get(code) or []
        evidence = [
            deepcopy(mapping.get("evidence") or {})
            for mapping in mappings
            if mapping.get("evidence")
        ]
        postconditions = list(dict.fromkeys(
            condition
            for mapping in mappings
            for condition in mapping.get("required_postconditions") or []
            if condition
        ))
        if not postconditions:
            postconditions = list(dict.fromkeys(
                issue.suggestion for issue in issues if issue.suggestion
            ))
        errors_payload.append({
            "error_code": code,
            "messages": [issue.message for issue in issues],
            "evidence": evidence,
            "required_postconditions": postconditions,
            "allowed_plan_updates": list(scope_by_error.get(code, {}).get("plan_updates") or []),
            "allowed_replacements": list(scope_by_error.get(code, {}).get("replacements") or []),
            "file_creation_allowed": False,
        })

    affected_files = {
        path: {
            "content_hash": source.get(path).content_hash,
            "language": source.get(path).language,
            "component": source.get(path).component,
            "content": source.get(path).content,
        }
        for path in allowed_replacements
        if source.get(path) is not None
    }
    original_components = list((failure.parsed_plan or {}).get("components") or [])
    requested_components = _requested_components(prompt)
    missing_components = [
        component for component in requested_components
        if component not in original_components
    ]
    expected_components = original_components + missing_components
    plan_update_context: dict[str, Any] = {}
    if "components" in allowed_plan_updates:
        plan_update_context["components"] = {
            "original_complete_value": original_components,
            "missing_requested_components": missing_components,
            "expected_final_complete_value": expected_components,
        }

    test_entrypoint_contracts: list[dict[str, Any]] = []
    for mapping in failure.error_artifact_mappings:
        if mapping.get("code") != "TEST_DOES_NOT_EXERCISE_ENTRYPOINT":
            continue
        evidence = mapping.get("evidence") or {}
        test_file = str(evidence.get("test_artifact") or "tests/run-tests.js")
        backend_entrypoint = str(evidence.get("backend_entrypoint") or "backend/server.js")
        test_entrypoint_contracts.append({
            "test_file": test_file,
            "backend_entrypoint": backend_entrypoint,
            "mandatory_postconditions": [
                f"{test_file} must import, start or execute {backend_entrypoint}.",
                f"{test_file} must make a real request to /health.",
                "The real backend process must always be terminated at the end of the test.",
            ],
            "forbidden": [
                f"Creating http.createServer inside {test_file} is forbidden.",
                "Keeping the previous synthetic server is forbidden.",
                "Do not claim that importing or starting the backend is impractical.",
            ],
            "precedence": "The required postconditions override model preferences or objections.",
            "failure_condition": (
                f"A response that keeps http.createServer in {test_file} has not corrected the error."
            ),
        })

    payload: dict[str, Any] = {
        "protocol": FOCAL_CORRECTION_PROTOCOL,
        "instruction": (
            "Correct only the listed semantic errors. Do not regenerate or return the complete plan. "
            "This is the second and final model call; there is no third correction."
        ),
        "response_schema": {
            "plan_updates": {
                "description": "only plan fields actually changed, each containing its complete final value",
                "allowed_fields": allowed_plan_updates,
                "value_semantics": "complete final values only; never append, add, patch or delta operations",
            },
            "replacements": [{
                "path": "one existing path from allowed_replacements",
                "content": "complete corrected file content",
            }],
        },
        "model_generated_manifest_forbidden": True,
        "errors": errors_payload,
        "allowed_plan_updates": allowed_plan_updates,
        "plan_update_context": plan_update_context,
        "plan_update_semantics": {
            "mandatory_rule": (
                "plan_updates não usa operações append, add, patch ou delta. "
                "Cada campo contém o seu valor final completo."
            ),
            "mandatory_components_example": {
                "Original": ["frontend", "backend", "persistence", "tests"],
                "Inválido": ["preview"],
                "Válido": ["frontend", "backend", "persistence", "tests", "preview"],
            },
        },
        "allowed_replacements": allowed_replacements,
        "replacement_allowlist_semantics": {
            "mandatory_rule": (
                "The files in allowed_replacements are an allowlist, not a list of mandatory changes."
            ),
            "rules": [
                "Return only files whose final content is actually different from the original content.",
                "Before including a replacement, silently compare it byte for byte with the original content.",
                "If the content is identical byte for byte, omit the replacement.",
                "An error may be resolved by changing only a subset of its allowed files.",
            ],
            "mandatory_subset_example": {
                "allowed_replacements": ["tests/run-tests.js", "backend/server.js"],
                "condition": "Only tests/run-tests.js needs to change.",
                "valid_response_fragment": {
                    "replacements": [{
                        "path": "tests/run-tests.js",
                        "content": "<complete corrected content of tests/run-tests.js>",
                    }],
                },
                "must_be_omitted": ["backend/server.js"],
            },
        },
        "affected_files": affected_files,
        "test_entrypoint_contracts": test_entrypoint_contracts,
        "requirements": [
            "Do not regenerate or return the complete project plan.",
            "Do not return files whose content is unchanged.",
            "Do not create, remove or rename files unless an error explicitly allows it.",
            "Return the complete content of every replaced file, never a partial patch.",
            "Treat every required_postcondition as mandatory; do not discuss or bypass it.",
            "Do not change artifacts outside the per-error allowlists.",
            "Do not return correction_manifest, changed_artifacts or any field outside response_schema.",
            "Every plan_updates field must contain its complete final value, never an append/add/patch/delta.",
            "Allowed replacement files are optional candidates; return only the changed subset.",
            "Return exactly one valid JSON object without markdown or additional text.",
        ],
        "silent_verification_before_response": [
            "Every error is actually resolved.",
            "Every returned plan update or replacement has a real content or value change.",
            "Every replacement path is allowed and appears exactly once.",
            "No artifact outside the requested scope changed.",
            "Every returned file has a content hash different from its original hash.",
            "components contains the complete final array, not only newly added components.",
            "The response is syntactically valid JSON matching response_schema.",
        ],
    }
    for contract in test_entrypoint_contracts:
        test_file = contract["test_file"]
        backend_entrypoint = contract["backend_entrypoint"]
        payload["silent_verification_before_response"].extend([
            f"{test_file} contains an executable reference to {backend_entrypoint}.",
            f"{test_file} does not contain http.createServer.",
            f"{test_file} makes a real request to /health.",
            "The backend is terminated at the end of the test, including on failure.",
        ])
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def _structured_plan_correction(
    failure: _PlanValidationFailure,
    previous_raw: str | dict[str, Any],
    prompt: str,
) -> str:
    if failure.category == "PLAN_SEMANTIC_INVALID":
        return _focal_structured_plan_correction(failure, prompt)
    return _legacy_structured_plan_correction(failure, previous_raw)


def _generic_plan_diagnostics(
    processed: _ProcessedProjectPlan,
    *,
    attempt_count: int,
    corrected_by_model: bool,
) -> dict[str, Any]:
    return {
        "attempt_count": attempt_count,
        "locally_repaired": bool(processed.local_repairs),
        "local_repairs": list(processed.local_repairs),
        "corrected_by_model": corrected_by_model,
        "final_plan_hash": processed.final_plan_hash,
        "attempts": [{
            "attempt": attempt_count,
            "raw_response_length": processed.raw_response_length,
            "parse_status": processed.parse_status,
            "local_repairs": list(processed.local_repairs),
            "schema_errors": [],
            "semantic_errors": [],
            "security_errors": [],
            "corrected_by_model": corrected_by_model,
            "final_plan_hash": processed.final_plan_hash,
        }],
        "virtual_files": deepcopy(processed.virtual_files),
        "static_analysis": deepcopy(processed.static_analysis),
    }


async def get_valid_project_plan(
    prompt: str,
    requester: PlanRequester | None = None,
    flight_recorder: Any | None = None,
) -> ProjectPlan:
    selected_requester: PlanRequester = requester or OllamaPlanRequester()
    ollama_requester = (
        selected_requester if isinstance(selected_requester, OllamaPlanRequester) else None
    )
    intent = detect_project_creation_intent(prompt)
    if flight_recorder is not None:
        flight_recorder.event(
            "prompt_build_started",
            phase="PREPARATION",
            metadata={"prompt_bytes": len(prompt.encode("utf-8"))},
        )
    planning_prompt = _prompt_with_intent_constraints(prompt, intent)
    if flight_recorder is not None:
        flight_recorder.event(
            "prompt_build_completed",
            phase="PREPARATION",
            metadata={
                "prompt_bytes": len(prompt.encode("utf-8")),
                "planning_prompt_bytes": len(planning_prompt.encode("utf-8")),
                "planning_prompt_sha256": hashlib.sha256(planning_prompt.encode("utf-8")).hexdigest(),
            },
        )
        flight_recorder.event(
            "request_payload_built",
            phase="PREPARATION",
            metadata={"planning_prompt_bytes": len(planning_prompt.encode("utf-8"))},
        )
    first_raw = await _maybe_await_plan(selected_requester, planning_prompt, None)
    corrected_by_model = False
    call_count = 1
    validation_history: list[dict[str, Any]] = []
    correction: str | None = None
    validation_event_names = (
        "structural_validation",
        "security_validation",
        "semantic_validation",
        "integrity_validation",
        "component_validation",
        "persistence_contract_validation",
        "entrypoint_validation",
        "preview_contract_validation",
    )
    try:
        if flight_recorder is not None:
            flight_recorder.event("requester_parse_started", phase="REQUESTER")
            flight_recorder.event("plan_decode_started", phase="PLAN")
            flight_recorder.event("plan_schema_validation_started", phase="PLAN")
            for event_name in validation_event_names:
                flight_recorder.event(f"{event_name}_started", phase="VALIDATION")
        processed = _validated_raw_project_plan(first_raw, prompt)
        if flight_recorder is not None:
            flight_recorder.event("requester_parse_completed", phase="REQUESTER", status="COMPLETED")
            flight_recorder.event("plan_schema_validation_completed", phase="PLAN", status="COMPLETED")
            flight_recorder.event("plan_decode_completed", phase="PLAN", status="COMPLETED", metadata={
                "plan_hash": processed.final_plan_hash,
            })
            for event_name in validation_event_names:
                flight_recorder.event(f"{event_name}_completed", phase="VALIDATION", status="COMPLETED")
    except _PlanValidationFailure as first_error:
        if flight_recorder is not None:
            flight_recorder.event("requester_parse_completed", phase="REQUESTER", status="FAILED", error=first_error.cause)
            flight_recorder.event(
                "plan_schema_validation_completed",
                phase="PLAN",
                status="FAILED",
                error=first_error.cause,
                metadata={"category": first_error.category},
            )
            for event_name in validation_event_names:
                flight_recorder.event(
                    f"{event_name}_completed",
                    phase="VALIDATION",
                    status="FAILED",
                    error=first_error.cause,
                    metadata={"category": first_error.category},
                )
        validation_history.append(_planning_validation_record("original", first_raw, first_error))
        if ollama_requester is not None:
            ollama_requester.note_validation_failure(first_error)
            if ollama_requester.attempt_count >= PLAN_MAX_ATTEMPTS:
                diagnostics = _with_validation_history(
                    ollama_requester.diagnostics(), validation_history, None, planning_prompt
                )
                raise ProjectBuilderPlanningError(
                    first_error.category,
                    "O plano devolvido e invalido e o limite de tentativas foi atingido.",
                    diagnostics,
                ) from first_error.cause
        correction = _structured_plan_correction(first_error, first_raw, prompt)
        if flight_recorder is not None:
            flight_recorder.event("focal_correction_started", phase="FOCAL_CORRECTION", metadata={
                "category": first_error.category,
            })
            flight_recorder.event("correction_prompt_built", phase="FOCAL_CORRECTION", metadata={
                "prompt_bytes": len(correction.encode("utf-8")),
                "prompt_sha256": hashlib.sha256(correction.encode("utf-8")).hexdigest(),
            })
            flight_recorder.event("correction_request_started", phase="FOCAL_CORRECTION")
        corrected_raw = await _maybe_await_plan(
            selected_requester,
            planning_prompt,
            correction,
        )
        call_count += 1
        corrected_by_model = True
        try:
            if flight_recorder is not None:
                flight_recorder.event("correction_response_received", phase="FOCAL_CORRECTION", metadata={
                    "response_bytes": len(str(corrected_raw).encode("utf-8")),
                })
                flight_recorder.event("correction_effectiveness_started", phase="FOCAL_CORRECTION")
            processed = _validated_correction_response(corrected_raw, prompt, first_error)
            if flight_recorder is not None:
                flight_recorder.event("correction_effectiveness_completed", phase="FOCAL_CORRECTION", status="COMPLETED")
                flight_recorder.event("correction_applied", phase="FOCAL_CORRECTION", status="COMPLETED", metadata={
                    "plan_hash": processed.final_plan_hash,
                })
                flight_recorder.event("focal_correction_completed", phase="FOCAL_CORRECTION", status="COMPLETED")
        except _PlanValidationFailure as second_error:
            if flight_recorder is not None:
                flight_recorder.event(
                    "correction_effectiveness_completed",
                    phase="FOCAL_CORRECTION",
                    status="FAILED",
                    error=second_error.cause,
                    metadata={"category": second_error.category},
                )
                flight_recorder.event(
                    "focal_correction_completed",
                    phase="FOCAL_CORRECTION",
                    status="FAILED",
                    error=second_error.cause,
                )
            validation_history.append(_planning_validation_record("corrected", corrected_raw, second_error))
            if ollama_requester is not None:
                ollama_requester.note_validation_failure(second_error)
                base_diagnostics = ollama_requester.diagnostics()
            else:
                base_diagnostics = {
                    "provider": "custom",
                    "model": "",
                    "attempt_count": call_count,
                    "durations": [],
                    "attempts": [],
                    "first_error": {
                        "category": first_error.category,
                        "message": str(first_error.cause)[:500],
                    },
                    "final_error": {
                        "category": second_error.category,
                        "message": str(second_error.cause)[:500],
                    },
                }
            diagnostics = _with_validation_history(
                base_diagnostics, validation_history, correction, planning_prompt
            )
            raise ProjectBuilderPlanningError(
                second_error.category,
                (
                    "A correcao nao demonstrou eficacia observavel e nao existe terceira chamada."
                    if second_error.category == "PLAN_CORRECTION_FAILED"
                    else "O plano JSON continua invalido depois da unica correcao permitida."
                ),
                diagnostics,
            ) from second_error.cause
        validation_history.append(_planning_validation_record("corrected", corrected_raw, processed))
    else:
        validation_history.append(_planning_validation_record("original", first_raw, processed))
    plan = processed.plan
    plan.normalized_data = deepcopy(processed.normalized_data)
    if ollama_requester is not None:
        ollama_requester.note_plan_processing(processed, corrected_by_model=corrected_by_model)
        plan.planning_diagnostics = _with_validation_history(
            ollama_requester.diagnostics(), validation_history, correction, planning_prompt
        )
    else:
        plan.planning_diagnostics = _with_validation_history(
            _generic_plan_diagnostics(
                processed,
                attempt_count=call_count,
                corrected_by_model=corrected_by_model,
            ),
            validation_history,
            correction,
            planning_prompt,
        )
    return plan


def _read_package_json(project_dir: str) -> dict[str, Any]:
    path = Path(project_dir, "package.json")
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ProjectBuilderError(f"package.json invalido: {exc}") from exc
    if not isinstance(value, dict):
        raise ProjectBuilderError("package.json deve ser um objeto.")
    return value


def _node_imports(project_dir: str) -> set[str]:
    imports: set[str] = set()
    for path in Path(project_dir).rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".js", ".mjs", ".cjs", ".jsx", ".ts", ".tsx"}:
            continue
        if any(part in {"node_modules", "dist", "build"} for part in path.parts):
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        matches = re.findall(
            r"(?:require\s*\(\s*|from\s+|import\s+)[\"']([^\"']+)[\"']",
            content,
        )
        for value in matches:
            if value.startswith((".", "/", "node:")):
                continue
            package = "/".join(value.split("/")[:2]) if value.startswith("@") else value.split("/", 1)[0]
            if package not in NODE_BUILTINS:
                imports.add(package)
    return imports


def _python_declared_dependencies(project_dir: str) -> list[str]:
    dependencies: list[str] = []
    requirements = Path(project_dir, "requirements.txt")
    if requirements.is_file():
        for line in requirements.read_text(encoding="utf-8").splitlines():
            clean = re.split(r"[<>=!~\[]", line.strip(), maxsplit=1)[0]
            if clean and not clean.startswith("#"):
                dependencies.append(clean)
    pyproject = Path(project_dir, "pyproject.toml")
    if pyproject.is_file():
        content = pyproject.read_text(encoding="utf-8")
        match = re.search(r"dependencies\s*=\s*\[(.*?)\]", content, flags=re.DOTALL)
        if match:
            for value in re.findall(r"[\"']([^\"']+)[\"']", match.group(1)):
                clean = re.split(r"[<>=!~\[]", value.strip(), maxsplit=1)[0]
                if clean:
                    dependencies.append(clean)
    return list(dict.fromkeys(dependencies))


def _category_for_command(command: str) -> str:
    clean = normalize_prompt(command)
    if any(term in clean for term in ("npm install", "npm ci", "pip install", "poetry install")):
        return "SETUP"
    if any(term in clean for term in (" test", "test ", "pytest", "jest")):
        return "TEST"
    if any(term in clean for term in (" build", "build ")):
        return "BUILD"
    if any(term in clean for term in ("lint", " check", "--check", "py_compile", "mypy", "ruff")):
        return "SYNTAX"
    return "TEST"


def _validation_static_error(
    category: str,
    message: str,
    *,
    phase: str = "VALIDATING",
    command_id: str = "",
    file: str = "",
    line: int | None = None,
    suggested_fix: str,
    retryable: bool = False,
) -> dict[str, Any]:
    return {
        "category": category,
        "phase": phase,
        "command_id": command_id,
        "file": file,
        "line": line,
        "message": message,
        "suggested_fix": suggested_fix,
        "retryable": retryable,
    }


def _plan_package_json(plan: ProjectPlan) -> dict[str, Any]:
    package_file = next((item for item in plan.files if item.path.lower() == "package.json"), None)
    if package_file is None:
        return {}
    try:
        value = json.loads(package_file.content)
    except ValueError:
        return {}
    return value if isinstance(value, dict) else {}


def _node_imports_from_files(files: list[ProjectFile]) -> set[str]:
    imports: set[str] = set()
    for item in files:
        if Path(item.path).suffix.lower() not in {".js", ".mjs", ".cjs", ".jsx", ".ts", ".tsx"}:
            continue
        for value in re.findall(
            r"(?:require\s*\(\s*|from\s+|import\s+)[\"']([^\"']+)[\"']",
            item.content,
        ):
            if value.startswith((".", "/", "node:")):
                continue
            imports.add("/".join(value.split("/")[:2]) if value.startswith("@") else value.split("/", 1)[0])
    return imports


def _command_target(value: str) -> str:
    return value.strip().strip("\"'").replace("\\", "/")


def _command_segments(command: str) -> list[str]:
    return [item.strip() for item in re.split(r"\s*(?:&&|\|\||;)\s*", command) if item.strip()]


def _prevalidation_errors_and_metadata(
    validation: ValidationPlan,
    plan: ProjectPlan,
    project_dir: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    source = PlannedFileSystem.from_materialized_project(project_dir, plan)
    all_checks = (
        validation.setup_commands
        + validation.validation_commands
        + validation.entrypoint_checks
        + validation.preview_checks
    )
    timeout_errors: list[dict[str, Any]] = []
    for check in all_checks:
        if check.required and (not isinstance(check.timeout, (int, float)) or check.timeout <= 0):
            timeout_errors.append(_validation_static_error(
                "VALIDATION_PLAN_INVALID",
                "Um check required nao tem timeout finito positivo.",
                command_id=check.check_id,
                suggested_fix="Define um timeout positivo para o check obrigatorio.",
            ))
    analysis = analyze_project_artifacts(
        source,
        components=list(plan.component_files),
        required_components=list(validation.required_components),
        entrypoints=list(plan.entrypoints),
        component_files=deepcopy(plan.component_files),
        dependencies=list(plan.dependencies),
        setup_commands=list(plan.setup_commands),
        validation_commands=list(plan.validation_commands),
        preview_command=plan.preview_command,
        preview_strategy=deepcopy(plan.preview_strategy),
        phase="PRE_VALIDATION",
        command_specs=[
            (f"validation_plan.{check.check_id}", check.command) for check in all_checks
        ],
    )
    errors = timeout_errors
    for issue in analysis.errors:
        value = issue.to_dict()
        value["category"] = value.pop("code")
        value["suggested_fix"] = value.pop("suggestion")
        value["command_id"] = value.get("field_path", "").removeprefix("validation_plan.") \
            if value.get("field_path", "").startswith("validation_plan.") else ""
        value["retryable"] = False
        errors.append(value)
    return errors, {
        "checked_components": analysis.checked_components,
        "checked_entrypoints": analysis.checked_entrypoints,
        "checked_scripts": analysis.checked_scripts,
        "checked_dependencies": analysis.checked_dependencies,
        "warnings": [item.to_dict() for item in analysis.warnings],
        "virtual_files": analysis.virtual_files,
    }


def prevalidate_validation_plan(
    validation: ValidationPlan,
    plan: ProjectPlan,
    project_dir: str,
) -> PreValidationResult:
    try:
        errors, metadata = _prevalidation_errors_and_metadata(validation, plan, project_dir)
    except ProjectBuilderInternalError:
        raise
    except Exception as exc:
        raise ProjectBuilderInternalError(
            "Falha interna durante a pre-validacao do ValidationPlan.", exc
        ) from exc
    for error in errors:
        error["phase"] = "PRE_VALIDATION"
        error["retryable"] = bool(error.get("retryable", True))
    suggested_fixes = list(dict.fromkeys(
        str(error.get("suggested_fix") or "").strip()
        for error in errors
        if str(error.get("suggested_fix") or "").strip()
    ))
    return PreValidationResult(
        valid=not errors,
        errors=errors,
        warnings=deepcopy(metadata.get("warnings") or []),
        checked_components=metadata["checked_components"],
        checked_entrypoints=metadata["checked_entrypoints"],
        checked_scripts=metadata["checked_scripts"],
        checked_dependencies=metadata["checked_dependencies"],
        blocked_commands=deepcopy(validation.blocked_commands),
        suggested_fixes=suggested_fixes,
    )


def _new_check(
    check_id: str,
    command: str,
    project_dir: str,
    category: str,
    source: str,
    required: bool = True,
    timeout: float | None = None,
    component: str = "",
) -> ValidationCheck:
    resolved_timeout = timeout if timeout is not None else COMMAND_TIMEOUT_DEFAULTS.get(category, 60.0)
    if required and (not isinstance(resolved_timeout, (int, float)) or resolved_timeout <= 0):
        raise ProjectBuilderError(f"Check required sem timeout finito: {check_id}")
    return ValidationCheck(
        check_id=check_id,
        command=command,
        working_directory=project_dir,
        category=category,
        required=required,
        source=source,
        timeout=float(resolved_timeout),
        component=component,
    )


def _project_context_entrypoints(project_dir: str) -> tuple[list[str], dict[str, Any] | None]:
    projects_root = Path(ag_tools.resolve_workspace_path(PROJECT_ROOT_REL))
    try:
        relative = Path(os.path.relpath(project_dir, projects_root))
    except ValueError:
        return [], None
    if len(relative.parts) != 1:
        return [], None
    try:
        context = ProjectContextService().index_project(relative.parts[0])
    except Exception:
        return [], None
    return list(context.entrypoints), context.to_dict()


def _materialize_validation_plan(
    prompt: str,
    plan: ProjectPlan,
    project_dir: str,
) -> tuple[ValidationPlan, dict[str, Any] | None]:
    requested = _requested_components(prompt)
    readable_files: list[ProjectFile] = []
    if Path(project_dir).is_dir():
        for path in Path(project_dir).rglob("*"):
            if not path.is_file() or path.stat().st_size > MAX_FILE_BYTES:
                continue
            try:
                content = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            readable_files.append(ProjectFile(
                path=os.path.relpath(str(path), project_dir).replace(os.sep, "/"),
                content=content,
            ))
    else:
        readable_files = list(plan.files)
    actual_inferred = _infer_components(plan.stack, readable_files)
    materialized = set(actual_inferred)
    for component, paths in plan.component_files.items():
        if (
            component not in {"frontend", "backend", "persistence", "tests", "preview"}
            and paths
            and all(Path(project_dir, path).is_file() for path in paths)
        ):
            materialized.add(component)
    required = list(dict.fromkeys(requested + plan.components))
    validation = ValidationPlan(
        required_components=required,
        requested_components=requested,
        promised_components=plan.components,
        materialized_components=sorted(materialized),
        missing_components=sorted(set(required) - materialized),
        rationale=plan.rationale or "Checks derived from the implementation plan and project metadata.",
    )

    package = _read_package_json(project_dir) if Path(project_dir).is_dir() else _plan_package_json(plan)
    declared_node = set(plan.dependencies)
    for field_name in ("dependencies", "devDependencies"):
        field_value = package.get(field_name) or {}
        if isinstance(field_value, dict):
            declared_node.update(str(name) for name in field_value)
    imported_node = _node_imports(project_dir) if Path(project_dir).is_dir() else _node_imports_from_files(plan.files)
    undeclared = sorted(imported_node - NODE_BUILTINS - declared_node)
    missing_installed = sorted(
        dependency for dependency in declared_node
        if not Path(project_dir, "node_modules", *dependency.split("/")).exists()
    )
    declared_python = _python_declared_dependencies(project_dir) if Path(project_dir).is_dir() else []
    missing_python = sorted(
        dependency for dependency in declared_python
        if importlib.util.find_spec(dependency.replace("-", "_")) is None
    )
    validation.missing_dependencies = (
        [f"undeclared:{item}" for item in undeclared]
        + [f"not_installed:{item}" for item in missing_installed]
        + [f"python_not_available:{item}" for item in missing_python]
    )

    for index, command in enumerate(plan.setup_commands, start=1):
        validation.setup_commands.append(
            _new_check(f"setup-{index}", command, project_dir, "SETUP", "ImplementationPlan")
        )
    if (missing_installed or missing_python) and not validation.setup_commands:
        check = _new_check(
            "setup-missing",
            "<required dependency setup>",
            project_dir,
            "SETUP",
            "Dependency discovery",
        )
        check.status = "SKIPPED"
        check.reason = "Dependencias declaradas estao em falta e o plano nao fornece setup_commands."
        validation.setup_commands.append(check)

    seen_commands: set[str] = set()
    for index, command in enumerate(plan.validation_commands, start=1):
        if _category_for_command(command) == "SETUP":
            if command not in {item.command for item in validation.setup_commands}:
                validation.setup_commands.append(
                    _new_check(f"setup-plan-{index}", command, project_dir, "SETUP", "ImplementationPlan")
                )
            continue
        seen_commands.add(command.lower())
        validation.validation_commands.append(
            _new_check(
                f"validation-{index}", command, project_dir,
                _category_for_command(command), "ImplementationPlan",
            )
        )

    scripts = package.get("scripts") or {}
    if isinstance(scripts, dict):
        for script_name, category in (
            ("test", "TEST"), ("lint", "SYNTAX"), ("build", "BUILD"), ("check", "SYNTAX"),
        ):
            if script_name not in scripts:
                continue
            command = f"npm run {script_name}"
            if command.lower() not in seen_commands:
                validation.validation_commands.append(
                    _new_check(
                        f"package-{script_name}", command, project_dir, category,
                        f"package.json scripts.{script_name}",
                    )
                )
                seen_commands.add(command.lower())
        expected_scripts: list[tuple[str, str]] = []
        if package and "tests" in required:
            expected_scripts.append(("test", "TEST"))
        if package and "frontend" in required:
            expected_scripts.append(("build", "BUILD"))
        for script_name, category in expected_scripts:
            if script_name in scripts:
                continue
            optional = _new_check(
                f"package-{script_name}-absent",
                f"npm run {script_name}",
                project_dir,
                category,
                f"package.json scripts.{script_name}",
                required=False,
            )
            optional.status = "SKIPPED"
            optional.reason = f"package.json nao declara scripts.{script_name}; usado fallback do plano."
            validation.optional_checks.append(optional)

    context_entrypoints, context_data = (
        _project_context_entrypoints(project_dir) if Path(project_dir).is_dir() else ([], None)
    )
    entrypoints = list(dict.fromkeys(plan.entrypoints + context_entrypoints))
    backend_mapping = set(plan.component_files.get("backend") or [])
    planned_file_paths = {item.path for item in plan.files}
    backend_entrypoints = [
        path for path in entrypoints
        if Path(path).suffix.lower() in {".js", ".mjs", ".cjs", ".py"}
        and (Path(project_dir, path).is_file() or path in planned_file_paths)
        and (not backend_mapping or path in backend_mapping)
    ]
    test_files = [
        item for item in readable_files
        if "test" in Path(item.path).stem.lower() or "spec" in Path(item.path).stem.lower()
    ]
    test_content = "\n".join(item.content.lower().replace("\\", "/") for item in test_files)
    entrypoint_markers = {
        marker
        for entrypoint in entrypoints
        for marker in (
            entrypoint.lower().replace("\\", "/"),
            Path(entrypoint).name.lower(),
            Path(entrypoint).stem.lower(),
        )
        if len(marker) >= 3
    }
    tests_linked = bool(test_files) and any(marker in test_content for marker in entrypoint_markers)
    if "tests" in required and not tests_linked:
        for check in validation.validation_commands:
            if check.category == "TEST":
                check.status = "SKIPPED"
                check.reason = "O teste nao referencia nenhum entrypoint materializado da aplicacao."
                check.evidence_eligible = False

    if "backend" in required:
        if backend_entrypoints:
            for index, entrypoint in enumerate(backend_entrypoints, start=1):
                validation.entrypoint_checks.append(
                    _new_check(
                        f"entrypoint-backend-{index}",
                        f"__jarvis_backend_health__:{entrypoint}",
                        project_dir,
                        "HEALTHCHECK",
                        "ProjectContext entrypoint",
                        timeout=10.0,
                        component="backend",
                    )
                )
        else:
            check = _new_check(
                "entrypoint-backend-missing", "<missing backend entrypoint>", project_dir,
                "ENTRYPOINT", "ProjectContext entrypoint", component="backend",
            )
            check.status = "SKIPPED"
            check.reason = "Nenhum entrypoint backend materializado."
            validation.entrypoint_checks.append(check)

    if "frontend" in required or "preview" in required:
        validation.preview_checks.append(
            _new_check(
                "preview-frontend", "__jarvis_static_preview__", project_dir,
                "PREVIEW", "Component coverage", timeout=10.0, component="frontend",
            )
        )
    return validation, context_data


def _result_for_unexecuted_check(check: ValidationCheck, status: str, reason: str) -> CommandResult:
    return CommandResult(
        command=_sanitize_command(check.command),
        ok=False,
        output=_command_output(None, "", reason, False),
        working_directory=check.working_directory,
        exit_code=None,
        stderr=reason,
        category=check.category,
        required=check.required,
        source=check.source,
        status=status,
        error_category="VALIDATION_PLAN_INVALID" if status in {"BLOCKED", "SKIPPED"} else "",
        command_id=check.check_id,
    )


async def _run_backend_healthcheck(
    check: ValidationCheck,
    project_dir: str,
    preview_strategy: dict[str, Any],
    journal: ProjectBuildJournal | None = None,
) -> CommandResult:
    recorder = getattr(journal, "flight_recorder", None) if journal is not None else None
    entrypoint = check.command.split(":", 1)[1]
    absolute_entrypoint = Path(project_dir, entrypoint)
    if not absolute_entrypoint.is_file():
        return _result_for_unexecuted_check(check, "SKIPPED", "Entrypoint backend inexistente.")
    suffix = absolute_entrypoint.suffix.lower()
    if suffix in {".js", ".mjs", ".cjs"}:
        executable = "node"
    elif suffix == ".py":
        executable = sys.executable
    else:
        return _result_for_unexecuted_check(check, "BLOCKED", "Tipo de entrypoint nao suportado.")
    port = _find_free_port()
    health_path = str(preview_strategy.get("healthcheck_path") or "/health").strip()
    if not health_path.startswith("/"):
        health_path = f"/{health_path}"
    health_url = f"http://127.0.0.1:{port}{health_path}"
    if recorder is not None:
        recorder.event(
            "healthcheck_started",
            phase="HEALTHCHECK",
            metadata={"entrypoint": entrypoint, "url": health_url},
        )
    environment = os.environ.copy()
    environment["PORT"] = str(port)
    started = time.monotonic()
    process: asyncio.subprocess.Process | None = None
    stdout_state = _BoundedPipeOutput(64 * 1024)
    stderr_state = _BoundedPipeOutput(64 * 1024)
    stdout_task: asyncio.Task | None = None
    stderr_task: asyncio.Task | None = None
    wait_task: asyncio.Task | None = None
    job = _WindowsJob()
    descendant_pids: set[int] = set()
    cleanup_errors: list[str] = []
    debug: dict[str, Any] = {}
    success = False
    reason = ""
    error_category = ""
    timed_out = False
    termination_attempted = False
    termination_confirmed: bool | None = None
    cleanup_completed = False
    interval = 0.1
    max_attempts = max(1, int(check.timeout / interval))
    attempts = 0

    async def probe() -> int | None:
        reader: asyncio.StreamReader | None = None
        writer: asyncio.StreamWriter | None = None
        probe_timeout = min(0.5, max(0.1, check.timeout))
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection("127.0.0.1", port), timeout=probe_timeout
            )
            request = (
                f"GET {health_path} HTTP/1.1\r\n"
                f"Host: 127.0.0.1:{port}\r\n"
                "Connection: close\r\n\r\n"
            ).encode("ascii")
            writer.write(request)
            await asyncio.wait_for(writer.drain(), timeout=probe_timeout)
            status_line = await asyncio.wait_for(reader.readline(), timeout=probe_timeout)
            parts = status_line.decode("ascii", errors="replace").strip().split()
            return int(parts[1]) if len(parts) >= 2 and parts[1].isdigit() else None
        except (OSError, asyncio.TimeoutError):
            return None
        finally:
            if writer is not None:
                writer.close()
                try:
                    await asyncio.wait_for(writer.wait_closed(), timeout=0.25)
                except (OSError, asyncio.TimeoutError):
                    pass

    async def stop_owned_process() -> None:
        nonlocal termination_attempted
        if process is None:
            return
        descendant_pids.update(_windows_descendant_pids(process.pid))
        alive_descendants = [pid for pid in descendant_pids if _pid_exists(pid)]
        if process.returncode is not None and not alive_descendants:
            return
        termination_attempted = True
        if process.returncode is None:
            if os.name == "nt":
                try:
                    os.kill(process.pid, signal.CTRL_BREAK_EVENT)
                except (AttributeError, OSError):
                    try:
                        process.terminate()
                    except ProcessLookupError:
                        pass
            else:
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except OSError:
                    try:
                        process.terminate()
                    except ProcessLookupError:
                        pass
            if wait_task is not None and not wait_task.done():
                try:
                    await asyncio.wait_for(asyncio.shield(wait_task), timeout=0.25)
                except asyncio.TimeoutError:
                    pass
        descendant_pids.update(_windows_descendant_pids(process.pid))
        alive_descendants = [pid for pid in descendant_pids if _pid_exists(pid)]
        if process.returncode is None or alive_descendants:
            if os.name == "nt":
                job.terminate()
                await _taskkill_owned_pids(
                    [process.pid, *sorted(descendant_pids)], timeout=1.5
                )
            else:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except OSError:
                    try:
                        process.kill()
                    except ProcessLookupError:
                        pass
        # Kill-on-close also handles descendants that outlived the direct parent
        # and retained inherited stdout/stderr handles.
        job.close()
        if wait_task is not None and not wait_task.done():
            try:
                await asyncio.wait_for(asyncio.shield(wait_task), timeout=1.5)
            except asyncio.TimeoutError:
                cleanup_errors.append("healthcheck_parent_wait_timeout")

    try:
        process = await asyncio.create_subprocess_exec(
            executable,
            entrypoint,
            cwd=project_dir,
            env=environment,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            **_process_creation_options(),
        )
        job_assigned = job.assign(process.pid)
        _owned_process_registry[process.pid] = {
            "command_id": check.check_id,
            "started_at": _utc_timestamp(),
            "descendant_pids": [],
            "job_assigned": job_assigned,
        }
        stdout_task = asyncio.create_task(stdout_state.drain(process.stdout, "stdout", debug))
        stderr_task = asyncio.create_task(stderr_state.drain(process.stderr, "stderr", debug))
        wait_task = asyncio.create_task(process.wait())
        if journal is not None:
            journal.process_started(
                check.check_id,
                process.pid,
                "HEALTHCHECK",
                process_group=str(process.pid),
            )
        deadline = time.monotonic() + check.timeout
        while time.monotonic() < deadline and attempts < max_attempts:
            attempts += 1
            descendant_pids.update(_windows_descendant_pids(process.pid))
            registry = _owned_process_registry.get(process.pid)
            if registry is not None:
                registry["descendant_pids"] = sorted(descendant_pids)
            if journal is not None:
                journal.heartbeat()
            if wait_task.done():
                await wait_task
                reason = f"Entrypoint terminou antes do healthcheck com codigo {process.returncode}."
                error_category = "PROCESS_EXITED_BEFORE_READY"
                break
            status = await probe()
            if status is not None:
                success = 200 <= status < 400
                if success:
                    break
                reason = f"Healthcheck devolveu HTTP {status}."
            await asyncio.sleep(interval)
        if not success and not reason:
            reason = f"Healthcheck nao respondeu em {check.timeout:.1f}s."
            error_category = "HEALTHCHECK_TIMEOUT"
            timed_out = True
    except OSError as exc:
        reason = f"Falha ao iniciar entrypoint: {exc}"
        error_category = "PROCESS_START_FAILED"
    finally:
        if process is not None:
            if process.stdin is not None:
                try:
                    process.stdin.close()
                except (OSError, RuntimeError):
                    cleanup_errors.append("healthcheck_stdin_close_error")
            await stop_owned_process()
            job.close()
            for task, label in (
                (stdout_task, "healthcheck_stdout_reader"),
                (stderr_task, "healthcheck_stderr_reader"),
                (wait_task, "healthcheck_wait_task"),
            ):
                await _cancel_task_finitely(task, 0.5, cleanup_errors, label)
            alive_owned = [
                pid for pid in [process.pid, *sorted(descendant_pids)] if _pid_exists(pid)
            ]
            termination_confirmed = not alive_owned
            cleanup_completed = termination_confirmed and not cleanup_errors and all(
                task is None or task.done() for task in (stdout_task, stderr_task, wait_task)
            )
            _owned_process_registry.pop(process.pid, None)
            if journal is not None:
                journal.process_finished(
                    check.check_id,
                    process.pid,
                    termination_confirmed=termination_confirmed,
                )
        else:
            job.close()
    stdout = _sanitize_persisted_output(stdout_state.text(), 64 * 1024 + 256)
    stderr = _sanitize_persisted_output(stderr_state.text(), 64 * 1024 + 256)
    duration = time.monotonic() - started
    exit_code = 0 if success else (process.returncode if process and process.returncode is not None else 1)
    if not success and reason:
        stderr = f"{stderr}\n{reason}".strip()
    if recorder is not None:
        recorder.event(
            "healthcheck_completed" if success else "healthcheck_failed",
            phase="HEALTHCHECK",
            status="COMPLETED" if success else "FAILED",
            metadata={
                "entrypoint": entrypoint,
                "url": health_url,
                "exit_code": exit_code,
                "duration_ms": round(duration * 1000, 3),
                "cleanup_completed": cleanup_completed,
            },
        )
    return CommandResult(
        command=f"{executable} {entrypoint} [healthcheck {health_url}]",
        ok=success,
        output=_command_output(exit_code, stdout, stderr, False),
        working_directory=project_dir,
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr,
        duration=duration,
        timed_out=timed_out,
        category="HEALTHCHECK",
        required=check.required,
        source=check.source,
        status="PASSED" if success else "FAILED",
        error_category=error_category,
        command_id=check.check_id,
        process_id=process.pid if process is not None else None,
        termination_confirmed=termination_confirmed,
        process_started=process is not None,
        termination_attempted=termination_attempted,
        termination_succeeded=termination_confirmed,
        descendant_count=len(descendant_pids),
        stdout_truncated=stdout_state.truncated,
        stderr_truncated=stderr_state.truncated,
        cleanup_completed=cleanup_completed,
        cleanup_errors=cleanup_errors,
    )


def _apply_result_to_check(
    validation: ValidationPlan,
    check: ValidationCheck,
    result: CommandResult,
) -> None:
    check.status = result.status
    check.reason = result.stderr if not result.ok else ""
    check.result = asdict(result)
    if result.ok and check.evidence_eligible:
        validation.technical_evidence.append({
            "check_id": check.check_id,
            "category": check.category,
            "component": check.component,
            "command": result.command,
            "working_directory": result.working_directory,
            "exit_code": result.exit_code,
            "source": check.source,
        })
    elif check.required:
        validation.failed_checks.append(check.check_id)


TECHNICAL_GATE_DEFENSE_CODES = {
    "DECLARED_COMPONENT_WITHOUT_ARTIFACTS",
    "PERSISTENCE_NOT_IMPLEMENTED",
    "TEST_FAILURE_NOT_PROPAGATED",
}


def _technical_gate_defense_issues(
    validation: ValidationPlan,
    plan: ProjectPlan,
    project_dir: str,
) -> list[PlanValidationIssue]:
    source = PlannedFileSystem.from_materialized_project(project_dir, plan)
    analysis = analyze_project_artifacts(
        source,
        components=list(plan.component_files),
        required_components=list(validation.required_components),
        entrypoints=list(plan.entrypoints),
        component_files=deepcopy(plan.component_files),
        dependencies=list(plan.dependencies),
        setup_commands=list(plan.setup_commands),
        validation_commands=list(plan.validation_commands),
        preview_command=plan.preview_command,
        preview_strategy=deepcopy(plan.preview_strategy),
        phase="TECHNICAL_VALIDATION_GATE",
    )
    return [issue for issue in analysis.errors if issue.code in TECHNICAL_GATE_DEFENSE_CODES]


async def _execute_validation_plan(
    validation: ValidationPlan,
    plan: ProjectPlan,
    project_dir: str,
    allow_preview: bool,
    journal: ProjectBuildJournal | None = None,
) -> tuple[list[CommandResult], list[SkippedCommand], bool, str]:
    executed: list[CommandResult] = []
    skipped: list[SkippedCommand] = []

    defense_issues = _technical_gate_defense_issues(validation, plan, project_dir)
    if defense_issues:
        for issue in defense_issues:
            value = issue.to_dict()
            value["category"] = value.pop("code")
            value["suggested_fix"] = value.pop("suggestion")
            value["retryable"] = False
            validation.static_errors.append(value)
            if issue.component:
                validation.missing_components.append(issue.component)
        validation.missing_components = sorted(set(validation.missing_components))
        validation.failed_checks.append("technical-validation-gate")
        validation.suggested_fix = "; ".join(
            dict.fromkeys(issue.suggestion for issue in defense_issues if issue.suggestion)
        )
        gate = CommandResult(
            command="technical validation gate",
            ok=False,
            output=_command_output(None, "", validation.suggested_fix, False),
            working_directory=project_dir,
            exit_code=None,
            stderr=validation.suggested_fix,
            category="BUILD",
            required=True,
            source="ValidationPlan defense in depth",
            status="FAILED",
            error_category=defense_issues[0].code,
            command_id="technical-validation-gate",
        )
        if journal is not None:
            check = _new_check(
                "technical-validation-gate",
                "technical validation gate",
                project_dir,
                "BUILD",
                "ValidationPlan defense in depth",
            )
            journal.transition("VALIDATING")
            journal.command_started(check)
            journal.command_completed(check.check_id, gate)
        return [gate], skipped, False, ""

    abort_remaining = False
    setup_ids = {item.check_id for item in validation.setup_commands}
    for check in validation.setup_commands + validation.validation_commands:
        if journal is not None:
            journal.transition("SETTING_UP" if check.check_id in setup_ids else "VALIDATING")
            journal.command_started(check)
        if abort_remaining:
            reason = "Check nao executado porque um comando required anterior excedeu o timeout."
            result = _result_for_unexecuted_check(check, "SKIPPED", reason)
            result.error_category = "COMMAND_TIMEOUT"
            validation.skipped_required_checks.append(check.check_id)
            skipped.append(SkippedCommand(command=check.command, reason=reason))
            _apply_result_to_check(validation, check, result)
            executed.append(result)
            if journal is not None:
                journal.command_completed(check.check_id, result)
            continue
        if check.status == "SKIPPED":
            reason = check.reason or "Required check skipped."
            result = _result_for_unexecuted_check(check, "SKIPPED", reason)
            skipped.append(SkippedCommand(command=check.command, reason=reason))
            validation.skipped_commands.append({"check_id": check.check_id, "command": check.command, "reason": reason})
            if check.required:
                validation.skipped_required_checks.append(check.check_id)
            _apply_result_to_check(validation, check, result)
            executed.append(result)
            if journal is not None:
                journal.command_completed(check.check_id, result)
            continue
        safe, reason = _command_is_project_safe(check.command)
        if not safe:
            result = _result_for_unexecuted_check(check, "BLOCKED", reason)
            validation.blocked_commands.append({"check_id": check.check_id, "command": check.command, "reason": reason})
            skipped.append(SkippedCommand(command=check.command, reason=reason))
            _apply_result_to_check(validation, check, result)
            executed.append(result)
            if journal is not None:
                journal.command_completed(check.check_id, result)
            continue
        result = await _run_project_command(
            check.command,
            project_dir,
            project_dir,
            timeout=check.timeout,
            command_id=check.check_id,
            category=check.category,
            required=check.required,
            journal=journal,
        )
        result.category = check.category
        result.required = check.required
        result.source = check.source
        _apply_result_to_check(validation, check, result)
        executed.append(result)
        if journal is not None:
            journal.command_completed(check.check_id, result)
        if result.timed_out and check.required:
            abort_remaining = True

    for check in validation.entrypoint_checks:
        if journal is not None:
            journal.transition("WAITING_HEALTHCHECK")
            journal.command_started(check)
        if abort_remaining:
            result = _result_for_unexecuted_check(
                check,
                "SKIPPED",
                "Healthcheck nao executado devido a timeout required anterior.",
            )
            result.error_category = "COMMAND_TIMEOUT"
        if check.status == "SKIPPED":
            result = _result_for_unexecuted_check(check, "SKIPPED", check.reason)
            validation.skipped_required_checks.append(check.check_id)
        elif not abort_remaining:
            result = await _run_backend_healthcheck(check, project_dir, plan.preview_strategy, journal)
        _apply_result_to_check(validation, check, result)
        executed.append(result)
        if journal is not None:
            journal.command_completed(check.check_id, result)
        if result.timed_out and check.required:
            abort_remaining = True

    preview_started = False
    preview_url = ""
    started_preview_processes: list[tuple[str, subprocess.Popen]] = []
    for check in validation.preview_checks:
        if journal is not None:
            journal.transition("STARTING_PREVIEW")
            journal.command_started(check)
        if abort_remaining:
            reason = "Preview nao iniciado devido a timeout required anterior."
            result = _result_for_unexecuted_check(check, "SKIPPED", reason)
            result.error_category = "COMMAND_TIMEOUT"
            validation.skipped_required_checks.append(check.check_id)
        elif not allow_preview or "frontend" not in validation.materialized_components:
            reason = "Preview indisponivel ou componente frontend nao materializado."
            result = _result_for_unexecuted_check(check, "SKIPPED", reason)
            validation.skipped_required_checks.append(check.check_id)
        else:
            artifact_dir = str(
                plan.preview_strategy.get("artifact_dir")
                or plan.preview_strategy.get("directory")
                or ""
            ).strip()
            serve_directory = project_dir
            if artifact_dir:
                safe_artifact_dir = _safe_relative_file_path(artifact_dir)
                serve_directory = _assert_project_child(
                    os.path.relpath(project_dir, ag_tools.resolve_workspace_path(".")).replace(os.sep, "/"),
                    safe_artifact_dir,
                )
            process_count = len(_preview_processes)
            preview_started, preview_url = start_static_preview(project_dir, serve_directory)
            preview_process = None
            if preview_started and len(_preview_processes) > process_count:
                preview_process = _preview_processes[-1]
                started_preview_processes.append((check.check_id, preview_process))
                if journal is not None:
                    journal.process_started(
                        check.check_id,
                        preview_process.pid,
                        "PREVIEW_START",
                        process_group=str(preview_process.pid),
                    )
            result = CommandResult(
                command="static preview",
                ok=preview_started,
                output=_command_output(0 if preview_started else 1, preview_url, "", False),
                working_directory=project_dir,
                exit_code=0 if preview_started else 1,
                stdout=preview_url,
                category="PREVIEW",
                required=check.required,
                source=check.source,
                status="PASSED" if preview_started else "FAILED",
                command_id=check.check_id,
                process_id=preview_process.pid if preview_process is not None else None,
            )
        _apply_result_to_check(validation, check, result)
        executed.append(result)
        if journal is not None:
            journal.command_completed(check.check_id, result)

    passed_categories = {
        item["category"] for item in validation.technical_evidence
    }
    if "frontend" in validation.materialized_components and "PREVIEW" in passed_categories:
        validation.validated_components.append("frontend")
    if "backend" in validation.materialized_components and "HEALTHCHECK" in passed_categories:
        validation.validated_components.append("backend")
    if "tests" in validation.materialized_components and "TEST" in passed_categories:
        validation.validated_components.append("tests")
    if "persistence" in validation.materialized_components and {"TEST", "HEALTHCHECK"}.issubset(passed_categories):
        validation.validated_components.append("persistence")
    if "preview" in validation.materialized_components and "PREVIEW" in passed_categories:
        validation.validated_components.append("preview")
    validation.validated_components = sorted(set(validation.validated_components))
    for component in validation.validated_components:
        validation.technical_evidence.append({
            "check_id": f"component-{component}",
            "category": "COMPONENT_COVERAGE",
            "component": component,
            "command": "component coverage gate",
            "working_directory": project_dir,
            "exit_code": 0,
            "source": "ValidationPlan success policy",
        })
    uncovered = sorted(set(validation.required_components) - set(validation.validated_components))
    validation.missing_components = sorted(set(validation.missing_components + uncovered))

    required_checks = (
        validation.setup_commands + validation.validation_commands
        + validation.entrypoint_checks + validation.preview_checks
    )
    validation.success = (
        bool(required_checks)
        and all(not check.required or check.status == "PASSED" for check in required_checks)
        and not validation.missing_components
        and not validation.missing_dependencies
        and not validation.blocked_commands
        and not validation.skipped_required_checks
    )
    if not validation.success:
        validation.suggested_fix = (
            "Corrigir checks required, dependencias e cobertura de componentes antes de nova execucao."
        )
        if not any(not result.ok for result in executed):
            gate = CommandResult(
                command="technical validation gate",
                ok=False,
                output=_command_output(None, "", validation.suggested_fix, False),
                working_directory=project_dir,
                exit_code=None,
                stderr=validation.suggested_fix,
                category="BUILD",
                required=True,
                source="ValidationPlan success policy",
                status="FAILED",
            )
            executed.append(gate)
            validation.failed_checks.append("technical-validation-gate")
        for command_id, process in started_preview_processes:
            termination_confirmed = None
            if process.poll() is None:
                termination_confirmed = await _terminate_owned_process_tree(process)
            if journal is not None:
                journal.process_finished(
                    command_id,
                    process.pid,
                    termination_confirmed=termination_confirmed,
                )
            if process in _preview_processes:
                _preview_processes.remove(process)
    return executed, skipped, preview_started if validation.success else False, preview_url if validation.success else ""


def _streaming_sha256(path: str | os.PathLike[str]) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _planning_failure_result(
    error: ProjectBuilderPlanningError,
    journal: ProjectBuildJournal,
    creation_intent: ProjectCreationIntent,
) -> ProjectBuildResult:
    diagnostics = deepcopy(error.diagnostics)
    final_validation = diagnostics.get("final_validation") or {}
    errors = _planning_errors_from_diagnostics(diagnostics, error.category)
    parsed_name = ""
    response = str(final_validation.get("response") or "")
    if response:
        try:
            response_data = extract_json_object(response)
            parsed_plan = response_data.get("corrected_plan") or response_data
            parsed_name = str(parsed_plan.get("project_name") or "").strip()
        except Exception:
            parsed_name = ""
    static_analysis = deepcopy(final_validation.get("static_analysis") or {})
    if not static_analysis and error.category == "PLAN_CORRECTION_FAILED":
        static_analysis = next((
            deepcopy(item.get("static_analysis") or {})
            for item in diagnostics.get("validation_history") or []
            if item.get("static_analysis")
        ), {})
    missing_components = sorted({
        str(item.get("component") or "") for item in errors
        if str(item.get("component") or "")
    })
    return ProjectBuildResult(
        project_name=parsed_name,
        project_dir="",
        project_rel_dir="",
        files_created=[],
        commands_executed=[],
        commands_skipped=[],
        preview_started=False,
        obsidian_used=False,
        technical_success=False,
        missing_components=missing_components,
        failed_checks=[str(item.get("category") or error.category) for item in errors],
        suggested_fix="; ".join(dict.fromkeys(
            str(item.get("suggested_fix") or "") for item in errors
            if str(item.get("suggested_fix") or "")
        )),
        creation_intent=asdict(creation_intent),
        planning_diagnostics=diagnostics,
        build_run_id=journal.run_id,
        progress_path=journal.relative_path,
        progress_state=journal.snapshot(),
        status="VALIDATION_FAILED",
        error_category=error.category,
        validation_errors=errors,
        pre_validation=static_analysis,
        completion_reason=error.category,
    )


async def _build_project_impl(
    prompt: str,
    plan_requester: PlanRequester | None = None,
    projects_root_rel: str = PROJECT_ROOT_REL,
    start_preview: bool = True,
    on_file: FileCallback | None = None,
    on_log: LogCallback | None = None,
    *,
    flight_recorder: Any | None = None,
    project_id: str = "",
    mission_id: str = "",
    execution_id: str = "",
) -> ProjectBuildResult:
    creation_intent = detect_project_creation_intent(prompt)
    if not creation_intent.is_creation_request:
        raise ProjectBuilderError("Pedido nao parece ser criacao de projeto.")

    journal = ProjectBuildJournal()
    recorder = flight_recorder
    if recorder is None:
        recorder = NoOpFlightRecorder()
    journal.attach_flight_recorder(recorder)
    if hasattr(recorder, "set_context"):
        recorder.set_context(
            project_id=project_id,
            mission_id=mission_id,
            execution_id=execution_id,
            build_run_id=journal.run_id,
        )
    recorder.event(
        "build_project_entered",
        phase="EXECUTION",
        metadata={"prompt_bytes": len(prompt.encode("utf-8")), "project_id": project_id},
    )
    selected_requester = plan_requester or OllamaPlanRequester(
        heartbeat=journal.heartbeat,
        flight_recorder=recorder,
    )
    try:
        with recorder.span("planning", phase="PLANNING"):
            plan = await get_valid_project_plan(prompt, selected_requester, recorder)
    except ProjectBuilderPlanningError as exc:
        journal.record_planning_failure(exc)
        if exc.category in {"PLAN_SEMANTIC_INVALID", "PLAN_CORRECTION_FAILED"}:
            return _planning_failure_result(exc, journal, creation_intent)
        raise
    except Exception as exc:
        category = getattr(exc, "category", "VALIDATION_PLAN_INVALID")
        journal.record_errors([_validation_static_error(
            category,
            str(exc)[:1000],
            phase="PLANNING",
            suggested_fix="Corrige o plano ou a disponibilidade do provider antes de repetir.",
            retryable=category in PLAN_RETRYABLE_CATEGORIES,
        )])
        raise
    recorder.event("configuration_resolved", phase="PREPARATION", metadata={
        "projects_root": projects_root_rel,
        "start_preview": start_preview,
        "requester": type(selected_requester).__name__,
    })
    project_rel_dir = unique_project_rel_dir(plan.project_name, projects_root_rel)
    project_dir = ag_tools.resolve_workspace_path(project_rel_dir)
    with recorder.span("project_context_loaded", phase="PREPARATION", metadata={"project_dir": project_dir}):
        validation, _ = _materialize_validation_plan(prompt, plan, project_dir)
    journal.record_plan(plan, validation, project_rel_dir)
    journal.transition("MATERIALIZING", completed_step="plan_validated")
    os.makedirs(project_dir, exist_ok=False)
    if on_log:
        on_log(f"[ProjectBuilder] Projeto: {project_rel_dir}\n")

    files_created: list[str] = []
    materialized_files: list[dict[str, Any]] = []
    with recorder.span("materialization", phase="MATERIALIZATION"):
        for file_item in plan.files:
            safe_path = _safe_relative_file_path(file_item.path)
            abs_path = _assert_project_child(project_rel_dir, safe_path)
            recorder.event("file_write_started", phase="MATERIALIZATION", metadata={
                "relative_path": safe_path,
                "operation": "create",
                "size_bytes": len(file_item.content.encode("utf-8")),
                "sha256": hashlib.sha256(file_item.content.encode("utf-8")).hexdigest(),
            })
            os.makedirs(os.path.dirname(abs_path), exist_ok=True)
            Path(abs_path).write_text(file_item.content, encoding="utf-8")
            rel_path = f"{project_rel_dir}/{safe_path}".replace("\\", "/")
            files_created.append(rel_path)
            materialized_files.append({
                "relative_path": safe_path,
                "size_bytes": os.path.getsize(abs_path),
                "sha256": _streaming_sha256(abs_path),
                "created_at": _utc_timestamp(),
            })
            recorder.event("file_write_completed", phase="MATERIALIZATION", status="COMPLETED", metadata=materialized_files[-1])
            if on_file:
                on_file(rel_path, file_item.content)
    journal.record_artifacts(materialized_files)

    with recorder.span("pre_validation", phase="PRE_VALIDATION"):
        pre_validation = prevalidate_validation_plan(validation, plan, project_dir)
    if not pre_validation.valid:
        validation.static_errors = list(pre_validation.errors)
        validation.failed_checks = list(dict.fromkeys(
            error.get("command_id") or error["category"] for error in pre_validation.errors
        ))
        validation.suggested_fix = "; ".join(pre_validation.suggested_fixes) or (
            "Corrigir os erros estaticos do ValidationPlan antes de executar comandos."
        )
        journal.record_prevalidation(pre_validation, validation)
        error_category = (
            str(pre_validation.errors[0].get("category") or "VALIDATION_PLAN_INVALID")
            if pre_validation.errors else "VALIDATION_PLAN_INVALID"
        )
        return ProjectBuildResult(
            project_name=plan.project_name,
            project_dir=project_dir,
            project_rel_dir=project_rel_dir,
            files_created=files_created,
            commands_executed=[],
            commands_skipped=[],
            preview_started=False,
            obsidian_used=False,
            validation_plan=asdict(validation),
            technical_success=False,
            missing_components=list(validation.missing_components),
            failed_checks=list(validation.failed_checks),
            blocked_checks=[item["check_id"] for item in validation.blocked_commands],
            skipped_required_checks=list(validation.skipped_required_checks),
            suggested_fix=validation.suggested_fix,
            creation_intent=asdict(creation_intent),
            planning_diagnostics=dict(plan.planning_diagnostics),
            build_run_id=journal.run_id,
            progress_path=journal.relative_path,
            progress_state=journal.snapshot(),
            status="VALIDATION_FAILED",
            error_category=error_category,
            validation_errors=list(pre_validation.errors),
            pre_validation=pre_validation.to_dict(),
            completion_reason="PRE_VALIDATION_FAILED",
        )

    journal.record_prevalidation(pre_validation, validation)

    recorder.event("component_validation", phase="VALIDATION", status="RUNNING")
    recorder.event("entrypoint_validation", phase="VALIDATION", status="RUNNING")
    recorder.event("preview_contract_validation", phase="VALIDATION", status="RUNNING")
    _, project_context = _project_context_entrypoints(project_dir)
    executed, skipped, preview_started, preview_url = await _execute_validation_plan(
        validation,
        plan,
        project_dir,
        allow_preview=start_preview,
        journal=journal,
    )
    recorder.event("component_validation", phase="VALIDATION", status="COMPLETED", metadata={
        "missing_components": validation.missing_components,
    })
    recorder.event("entrypoint_validation", phase="VALIDATION", status="COMPLETED", metadata={
        "failed_checks": validation.failed_checks,
    })
    recorder.event("preview_contract_validation", phase="VALIDATION", status="COMPLETED", metadata={
        "preview_started": preview_started,
    })
    for result in executed:
        result.output = result.output[:4000]
        result.stdout = result.stdout[:4000]
        result.stderr = result.stderr[:4000]
    if project_context is not None:
        validation.technical_evidence.append({
            "check_id": "project-context",
            "category": "PROJECT_CONTEXT",
            "component": "project",
            "command": "index_project",
            "working_directory": project_dir,
            "exit_code": 0,
            "source": "ProjectContextService",
            "project_id": project_context.get("project_id"),
            "entrypoints": project_context.get("entrypoints") or [],
        })
    journal.record_validation_snapshot(validation)
    runtime_errors: list[dict[str, Any]] = []
    if validation.success:
        journal.transition("TECHNICALLY_VALIDATED", completed_step="all_required_checks_passed")
    else:
        runtime_errors = [
            _validation_static_error(
                item.error_category or "VALIDATION_PLAN_INVALID",
                item.stderr or f"O comando {item.command} falhou.",
                command_id=item.command_id,
                phase="VALIDATING",
                suggested_fix="Corrige o comando ou o artefacto indicado antes de repetir.",
                retryable=item.timed_out,
            )
            for item in executed if not item.ok
        ]
        journal.record_errors(runtime_errors or [_validation_static_error(
            "VALIDATION_PLAN_INVALID",
            validation.suggested_fix,
            suggested_fix=validation.suggested_fix,
        )])

    return ProjectBuildResult(
        project_name=plan.project_name,
        project_dir=project_dir,
        project_rel_dir=project_rel_dir,
        files_created=files_created,
        commands_executed=executed,
        commands_skipped=skipped,
        preview_url=preview_url,
        preview_started=preview_started,
        obsidian_used=False,
        validation_plan=asdict(validation),
        technical_success=validation.success,
        missing_components=list(validation.missing_components),
        failed_checks=list(validation.failed_checks),
        blocked_checks=[item["check_id"] for item in validation.blocked_commands],
        skipped_required_checks=list(validation.skipped_required_checks),
        suggested_fix=validation.suggested_fix,
        creation_intent=asdict(creation_intent),
        planning_diagnostics=dict(plan.planning_diagnostics),
        build_run_id=journal.run_id,
        progress_path=journal.relative_path,
        progress_state=journal.snapshot(),
        status="SUCCEEDED" if validation.success else "VALIDATION_FAILED",
        error_category=(
            str(runtime_errors[0].get("category") or "VALIDATION_PLAN_INVALID")
            if runtime_errors else ""
        ),
        validation_errors=runtime_errors,
        pre_validation=pre_validation.to_dict(),
        completion_reason=("TECHNICALLY_VALIDATED" if validation.success else "VALIDATION_FAILED"),
    )


async def build_project(
    prompt: str,
    plan_requester: PlanRequester | None = None,
    projects_root_rel: str = PROJECT_ROOT_REL,
    start_preview: bool = True,
    on_file: FileCallback | None = None,
    on_log: LogCallback | None = None,
    *,
    flight_recorder: Any | None = None,
    project_id: str = "",
    mission_id: str = "",
    execution_id: str = "",
    finalize_flight_recorder: bool = True,
) -> ProjectBuildResult:
    """Run the existing builder with optional persistent observability."""
    enabled = _project_builder_setting("PROJECT_BUILDER_FLIGHT_RECORDER_ENABLED", "1").lower() not in {
        "0", "false", "no", "off",
    }
    recorder = flight_recorder
    if recorder is None:
        recorder = (
            ProjectBuilderFlightRecorder(
                recorder_directory(ag_tools.resolve_workspace_path(".")),
                project_id=project_id,
                mission_id=mission_id,
                execution_id=execution_id,
                diagnostics_enabled=(
                    _project_builder_setting("PROJECT_BUILDER_FLIGHT_RECORDER_DIAGNOSTICS", "0").lower()
                    in {"1", "true", "yes", "on"}
                ),
            )
            if enabled else NoOpFlightRecorder()
        )
    result: ProjectBuildResult | None = None
    try:
        result = await _build_project_impl(
            prompt,
            plan_requester=plan_requester,
            projects_root_rel=projects_root_rel,
            start_preview=start_preview,
            on_file=on_file,
            on_log=on_log,
            flight_recorder=recorder,
            project_id=project_id,
            mission_id=mission_id,
            execution_id=execution_id,
        )
        recorder.event(
            "build_completed",
            phase="EXECUTION",
            status="COMPLETED" if result.technical_success else "FAILED",
            metadata={
                "status": result.status,
                "technical_success": result.technical_success,
                "project_rel_dir": result.project_rel_dir,
                "files_created": len(result.files_created),
            },
        )
        result.flight_recorder_path = str(getattr(recorder, "directory", ""))
        return result
    except asyncio.CancelledError as exc:
        recorder.event("build_interrupted", phase="EXECUTION", status="INTERRUPTED", error=exc)
        raise
    except BaseException as exc:
        recorder.event("build_failed", phase="EXECUTION", status="FAILED", error=exc)
        raise
    finally:
        final_status = result.status if result is not None else "FAILED"
        final_state = {
            "status": final_status,
            "technical_success": bool(result and result.technical_success),
            "build_run_id": result.build_run_id if result is not None else "",
            "project_rel_dir": result.project_rel_dir if result is not None else "",
            "files_created": result.files_created if result is not None else [],
        }
        if finalize_flight_recorder:
            recorder.close(
                status="SUCCEEDED" if result is not None and result.technical_success else final_status,
                final_state=final_state,
            )
