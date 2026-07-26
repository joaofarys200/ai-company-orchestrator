from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, field, fields, is_dataclass
from enum import Enum
from types import MappingProxyType
from typing import Any


SEMANTIC_CONTEXT_VERSION = "semantic_context_builder_v1"
SHA256_LENGTH = 64
EPOCH_TIMESTAMP = "1970-01-01T00:00:00+00:00"
SAFE_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,255}$")


class ContextSource(str, Enum):
    MISSION_STATE = "MISSION_STATE"
    WORKSPACE = "WORKSPACE"
    CAPABILITY_REGISTRY = "CAPABILITY_REGISTRY"
    TASK_PROFILE = "TASK_PROFILE"
    BENCHMARK_CONFIGURATION = "BENCHMARK_CONFIGURATION"


class ContextKind(str, Enum):
    MISSION = "MISSION"
    WORK_PACKAGE = "WORK_PACKAGE"
    DELIVERABLE = "DELIVERABLE"
    EVIDENCE = "EVIDENCE"
    ACCEPTANCE_CRITERION = "ACCEPTANCE_CRITERION"
    WORKSPACE_METADATA = "WORKSPACE_METADATA"
    SOURCE_FILE = "SOURCE_FILE"
    TEST_FILE = "TEST_FILE"
    CONFIGURATION = "CONFIGURATION"
    DOCUMENT = "DOCUMENT"
    CAPABILITY = "CAPABILITY"
    COMPATIBILITY = "COMPATIBILITY"
    TASK_PROFILE = "TASK_PROFILE"
    BENCHMARK_CONFIGURATION = "BENCHMARK_CONFIGURATION"


class ValidationSeverity(str, Enum):
    ERROR = "ERROR"
    WARNING = "WARNING"


@dataclass(frozen=True)
class WorkspaceFile:
    path: str
    size_bytes: int
    modified_ns: int
    category: str
    language: str = ""
    content_available: bool = False
    content_sha256: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "path", _relative_path(self.path))
        if self.size_bytes < 0 or self.modified_ns < 0:
            raise ValueError("WorkspaceFile sizes and timestamps cannot be negative.")
        if not str(self.category or "").strip():
            raise ValueError("WorkspaceFile.category is required.")
        if self.content_sha256:
            _validate_sha256(self.content_sha256, "WorkspaceFile.content_sha256")


@dataclass(frozen=True)
class MissionContext:
    project_id: str
    mission_id: str
    title: str
    objective: str
    description: str
    status: str
    current_phase: str
    progress: float
    work_packages: tuple[Mapping[str, Any], ...]
    deliverables: tuple[Mapping[str, Any], ...]
    evidence: tuple[Mapping[str, Any], ...]
    acceptance_criteria: tuple[Mapping[str, Any], ...]
    executions: tuple[Mapping[str, Any], ...]
    eligible_work_packages: tuple[str, ...]
    recent_events: tuple[Mapping[str, Any], ...]
    updated_at: str
    source_sha256: str

    def __post_init__(self) -> None:
        _required(self.project_id, "MissionContext.project_id")
        _required(self.mission_id, "MissionContext.mission_id")
        _required(self.objective, "MissionContext.objective")
        if not 0.0 <= float(self.progress) <= 100.0:
            raise ValueError("MissionContext.progress must be in [0, 100].")
        for name in (
            "work_packages",
            "deliverables",
            "evidence",
            "acceptance_criteria",
            "executions",
            "recent_events",
        ):
            object.__setattr__(
                self,
                name,
                tuple(freeze_mapping(item) for item in getattr(self, name)),
            )
        object.__setattr__(
            self,
            "eligible_work_packages",
            tuple(str(item) for item in self.eligible_work_packages),
        )
        _validate_sha256(self.source_sha256, "MissionContext.source_sha256")


@dataclass(frozen=True)
class WorkspaceContext:
    project_id: str
    root_path: str
    project_name: str
    stack: tuple[str, ...]
    frameworks: tuple[str, ...]
    package_managers: tuple[str, ...]
    entrypoints: tuple[str, ...]
    source_roots: tuple[str, ...]
    languages: tuple[str, ...]
    dependencies: tuple[str, ...]
    configurations: tuple[str, ...]
    tests: tuple[str, ...]
    latest_changes: tuple[str, ...]
    file_tree: tuple[WorkspaceFile, ...]
    relevant_files: tuple[WorkspaceFile, ...]
    files_considered: int
    files_rejected: int
    traversal_truncated: bool
    observed_at: str
    source_sha256: str

    def __post_init__(self) -> None:
        _required(self.project_id, "WorkspaceContext.project_id")
        _required(self.root_path, "WorkspaceContext.root_path")
        _required(self.project_name, "WorkspaceContext.project_name")
        for name in (
            "entrypoints",
            "source_roots",
            "configurations",
            "tests",
            "latest_changes",
        ):
            object.__setattr__(
                self,
                name,
                tuple(_relative_path(item) for item in getattr(self, name)),
            )
        for name in (
            "stack",
            "frameworks",
            "package_managers",
            "languages",
            "dependencies",
        ):
            object.__setattr__(
                self,
                name,
                tuple(str(item) for item in getattr(self, name)),
            )
        if self.files_considered < 0 or self.files_rejected < 0:
            raise ValueError("WorkspaceContext file counters cannot be negative.")
        object.__setattr__(self, "file_tree", tuple(self.file_tree))
        object.__setattr__(self, "relevant_files", tuple(self.relevant_files))
        _validate_sha256(self.source_sha256, "WorkspaceContext.source_sha256")


@dataclass(frozen=True)
class DocumentContext:
    documents: tuple[WorkspaceFile, ...]
    source_sha256: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "documents", tuple(self.documents))
        _validate_sha256(self.source_sha256, "DocumentContext.source_sha256")


@dataclass(frozen=True)
class DemonstratedCapability:
    capability_id: str
    status: str
    confidence: float
    last_verified: str
    evidence_references: tuple[str, ...]
    limitations: tuple[Mapping[str, Any], ...]
    configurations: tuple[Mapping[str, Any], ...]

    def __post_init__(self) -> None:
        _required(self.capability_id, "DemonstratedCapability.capability_id")
        if not 0.0 <= float(self.confidence) <= 1.0:
            raise ValueError("DemonstratedCapability.confidence must be in [0, 1].")
        object.__setattr__(
            self,
            "evidence_references",
            tuple(sorted(set(str(item) for item in self.evidence_references))),
        )
        object.__setattr__(
            self,
            "limitations",
            tuple(freeze_mapping(item) for item in self.limitations),
        )
        object.__setattr__(
            self,
            "configurations",
            tuple(freeze_mapping(item) for item in self.configurations),
        )


@dataclass(frozen=True)
class CompatibilityAssessment:
    target: str
    compatible: bool
    requirements: tuple[str, ...]
    failed_requirements: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "requirements",
            tuple(str(item) for item in self.requirements),
        )
        object.__setattr__(
            self,
            "failed_requirements",
            tuple(str(item) for item in self.failed_requirements),
        )


@dataclass(frozen=True)
class CapabilityContext:
    registry_version: str
    registry_snapshot_version: str
    model_name: str
    configuration_hash: str
    capabilities: tuple[DemonstratedCapability, ...]
    limitations: tuple[Mapping[str, Any], ...]
    compatibility: tuple[CompatibilityAssessment, ...]
    last_validation: str
    source_sha256: str

    def __post_init__(self) -> None:
        _required(self.registry_version, "CapabilityContext.registry_version")
        _required(
            self.registry_snapshot_version,
            "CapabilityContext.registry_snapshot_version",
        )
        _required(self.model_name, "CapabilityContext.model_name")
        if self.configuration_hash:
            _validate_sha256(
                self.configuration_hash,
                "CapabilityContext.configuration_hash",
            )
        object.__setattr__(
            self,
            "limitations",
            tuple(freeze_mapping(item) for item in self.limitations),
        )
        object.__setattr__(self, "capabilities", tuple(self.capabilities))
        object.__setattr__(self, "compatibility", tuple(self.compatibility))
        _validate_sha256(self.source_sha256, "CapabilityContext.source_sha256")


@dataclass(frozen=True)
class ContextItem:
    item_id: str
    source: ContextSource
    kind: ContextKind
    title: str
    content: str = field(repr=False)
    source_path: str = ""
    references: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)
    observed_at: str = EPOCH_TIMESTAMP
    priority: int = 0
    content_sha256: str = ""

    def __post_init__(self) -> None:
        if not SAFE_ID_PATTERN.fullmatch(str(self.item_id or "")):
            raise ValueError("ContextItem.item_id has an invalid format.")
        _required(self.title, "ContextItem.title")
        object.__setattr__(self, "source", ContextSource(self.source))
        object.__setattr__(self, "kind", ContextKind(self.kind))
        if not isinstance(self.content, str):
            raise ValueError("ContextItem.content must be text.")
        if self.source_path:
            object.__setattr__(self, "source_path", _relative_path(self.source_path))
        object.__setattr__(
            self,
            "references",
            tuple(sorted(set(str(item) for item in self.references if str(item)))),
        )
        object.__setattr__(self, "metadata", freeze_mapping(self.metadata))
        if not -100 <= int(self.priority) <= 100:
            raise ValueError("ContextItem.priority must be in [-100, 100].")
        content_hash = self.content_sha256 or sha256_text(self.content)
        _validate_sha256(content_hash, "ContextItem.content_sha256")
        object.__setattr__(self, "content_sha256", content_hash)


@dataclass(frozen=True)
class RankingScore:
    item_id: str
    recency: float
    proximity: float
    relevance: float
    type_score: float
    priority: float
    task_profile: float
    mission: float
    total: float
    rank: int

    def __post_init__(self) -> None:
        for name in (
            "recency",
            "proximity",
            "relevance",
            "type_score",
            "priority",
            "task_profile",
            "mission",
            "total",
        ):
            value = float(getattr(self, name))
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"RankingScore.{name} must be in [0, 1].")
        if self.rank < 1:
            raise ValueError("RankingScore.rank must be positive.")


@dataclass(frozen=True)
class ContextRejection:
    item_id: str
    reason: str
    duplicate_of: str = ""


@dataclass(frozen=True)
class CompressionResult:
    selected_item_ids: tuple[str, ...]
    rejected: tuple[ContextRejection, ...]
    considered_items: int
    duplicate_items: int
    original_chars: int
    final_chars: int
    max_items: int
    max_chars: int

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "selected_item_ids",
            tuple(str(item) for item in self.selected_item_ids),
        )
        object.__setattr__(self, "rejected", tuple(self.rejected))
        values = (
            self.considered_items,
            self.duplicate_items,
            self.original_chars,
            self.final_chars,
            self.max_items,
            self.max_chars,
        )
        if any(value < 0 for value in values):
            raise ValueError("CompressionResult counters cannot be negative.")
        if self.final_chars > self.max_chars:
            raise ValueError("CompressionResult exceeds max_chars.")
        if len(self.selected_item_ids) > self.max_items:
            raise ValueError("CompressionResult exceeds max_items.")


@dataclass(frozen=True)
class BuilderConfiguration:
    workspace_root: str
    project_id: str
    mission_id: str
    model_name: str
    task_profile_name: str
    benchmark_configuration: Mapping[str, Any] = field(default_factory=dict)
    capability_configuration_hash: str = ""
    compatibility_targets: tuple[str, ...] = ()
    relevant_paths: tuple[str, ...] = ()
    max_workspace_files: int = 500
    max_workspace_depth: int = 8
    max_content_files: int = 32
    max_file_bytes: int = 256_000
    max_total_file_bytes: int = 1_500_000
    max_mission_records: int = 100
    max_items: int = 64
    max_chars: int = 120_000
    max_item_chars: int = 40_000

    def __post_init__(self) -> None:
        for name in (
            "workspace_root",
            "project_id",
            "mission_id",
            "model_name",
            "task_profile_name",
        ):
            _required(getattr(self, name), f"BuilderConfiguration.{name}")
        object.__setattr__(
            self,
            "benchmark_configuration",
            freeze_mapping(self.benchmark_configuration),
        )
        if self.capability_configuration_hash:
            _validate_sha256(
                self.capability_configuration_hash,
                "BuilderConfiguration.capability_configuration_hash",
            )
        object.__setattr__(
            self,
            "compatibility_targets",
            tuple(sorted(set(str(item) for item in self.compatibility_targets))),
        )
        object.__setattr__(
            self,
            "relevant_paths",
            tuple(sorted(set(_relative_path(item) for item in self.relevant_paths))),
        )
        for name in (
            "max_workspace_files",
            "max_workspace_depth",
            "max_content_files",
            "max_file_bytes",
            "max_total_file_bytes",
            "max_mission_records",
            "max_items",
            "max_chars",
            "max_item_chars",
        ):
            if int(getattr(self, name)) < 1:
                raise ValueError(f"BuilderConfiguration.{name} must be positive.")
        if self.max_item_chars > self.max_chars:
            raise ValueError("max_item_chars cannot exceed max_chars.")


@dataclass(frozen=True)
class SemanticSnapshot:
    builder_version: str
    snapshot_version: str
    generated_at: str
    configuration: BuilderConfiguration
    mission: MissionContext
    workspace: WorkspaceContext
    capabilities: CapabilityContext
    documents: DocumentContext
    items: tuple[ContextItem, ...]
    ranking: tuple[RankingScore, ...]
    compression: CompressionResult
    source_hashes: Mapping[str, str]
    statistics: Mapping[str, Any]
    content_sha256: str

    def __post_init__(self) -> None:
        _required(self.builder_version, "SemanticSnapshot.builder_version")
        _required(self.snapshot_version, "SemanticSnapshot.snapshot_version")
        object.__setattr__(self, "source_hashes", freeze_mapping(self.source_hashes))
        object.__setattr__(self, "statistics", freeze_mapping(self.statistics))
        object.__setattr__(self, "items", tuple(self.items))
        object.__setattr__(self, "ranking", tuple(self.ranking))
        for source, value in self.source_hashes.items():
            _validate_sha256(value, f"SemanticSnapshot.source_hashes[{source}]")
        _validate_sha256(self.content_sha256, "SemanticSnapshot.content_sha256")

    def payload_without_content_hash(self) -> Mapping[str, Any]:
        payload = to_jsonable(self)
        payload.pop("content_sha256", None)
        return payload

    def computed_content_sha256(self) -> str:
        return sha256_json(self.payload_without_content_hash())


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    message: str
    severity: ValidationSeverity
    location: str


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    issues: tuple[ValidationIssue, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "issues", tuple(self.issues))


def freeze_mapping(value: Mapping[str, Any] | None) -> Mapping[str, Any]:
    source = value or {}
    return MappingProxyType({
        str(key): freeze_value(item)
        for key, item in sorted(source.items(), key=lambda pair: str(pair[0]))
    })


def freeze_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return freeze_mapping(value)
    if isinstance(value, (set, frozenset)):
        return tuple(
            sorted(
                (freeze_value(item) for item in value),
                key=canonical_json,
            )
        )
    if isinstance(value, (list, tuple)):
        return tuple(freeze_value(item) for item in value)
    return value


def to_jsonable(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value) and not isinstance(value, type):
        return {
            item.name: to_jsonable(getattr(value, item.name))
            for item in fields(value)
        }
    if isinstance(value, Mapping):
        return {
            str(key): to_jsonable(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (set, frozenset)):
        return sorted(
            (to_jsonable(item) for item in value),
            key=lambda item: json.dumps(
                item,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ),
        )
    if isinstance(value, (tuple, list)):
        return [to_jsonable(item) for item in value]
    return value


def canonical_json(value: Any) -> str:
    return json.dumps(
        to_jsonable(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _required(value: Any, field_name: str) -> None:
    if not str(value or "").strip():
        raise ValueError(f"{field_name} is required.")


def _validate_sha256(value: str, field_name: str) -> None:
    normalized = str(value or "").strip().lower()
    if (
        len(normalized) != SHA256_LENGTH
        or any(character not in "0123456789abcdef" for character in normalized)
    ):
        raise ValueError(f"{field_name} must be a hexadecimal SHA-256.")


def _relative_path(value: str) -> str:
    normalized = str(value or "").strip().replace("\\", "/")
    if not normalized:
        raise ValueError("Relative path cannot be empty.")
    if normalized == ".":
        return "."
    if normalized.startswith("/") or re.match(r"^[A-Za-z]:/", normalized):
        raise ValueError(f"Absolute path is not allowed: {normalized}")
    parts = tuple(part for part in normalized.split("/") if part not in {"", "."})
    if not parts or any(part == ".." for part in parts):
        raise ValueError(f"Unsafe relative path: {normalized}")
    return "/".join(parts)
