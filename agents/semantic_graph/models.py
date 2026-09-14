"""
JARVIS OS — Phase 44: Cross-Language Semantic Graph & Task Translation
Core Models, Enums, Serialization, and Invariant Definitions.

Principles:
- Separation of Language Graph from Semantic Graph.
- Language-agnostic, formal, and verifiable representations.
- Contracts serve as formal bridges across heterogeneous ecosystems.
- No name-based translation without contractual or direct evidence.
- Explicit uncertainty (UNCERTAIN) rather than hallucination.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import enum
import hashlib
import json
import time
from typing import Any, Dict, List, Optional, Set


class SemanticNodeType(str, enum.Enum):
    REQUIREMENT = "REQUIREMENT"
    CONSTRAINT = "CONSTRAINT"
    ARCHITECTURE_COMPONENT = "ARCHITECTURE_COMPONENT"
    FRONTEND_COMPONENT = "FRONTEND_COMPONENT"
    BACKEND_SERVICE = "BACKEND_SERVICE"
    API_ENDPOINT = "API_ENDPOINT"
    API_CONTRACT = "API_CONTRACT"
    DATA_MODEL = "DATA_MODEL"
    PERSISTENCE_OPERATION = "PERSISTENCE_OPERATION"
    TASK = "TASK"
    TEST = "TEST"
    BROWSER_SCENARIO = "BROWSER_SCENARIO"
    AGENT = "AGENT"
    EVIDENCE = "EVIDENCE"


class SemanticRelationType(str, enum.Enum):
    IMPLEMENTS = "IMPLEMENTS"
    SERVES = "SERVES"
    CALLS = "CALLS"
    EXPOSES = "EXPOSES"
    CONSUMES = "CONSUMES"
    PERSISTS = "PERSISTS"
    VALIDATES = "VALIDATES"
    TESTS = "TESTS"
    REQUIRES = "REQUIRES"
    DEPENDS_ON = "DEPENDS_ON"
    GENERATES = "GENERATES"
    PROVES = "PROVES"
    REMEDIATES = "REMEDIATES"
    TRANSLATES_TO = "TRANSLATES_TO"


class ConfidenceClass(str, enum.Enum):
    CONTRACTUAL = "CONTRACTUAL"
    DIRECT = "DIRECT"
    INFERRED = "INFERRED"
    UNCERTAIN = "UNCERTAIN"


class ValidationStatus(str, enum.Enum):
    VALID = "VALID"
    INVALID = "INVALID"
    UNCERTAIN = "UNCERTAIN"


class ContractVersionStatus(str, enum.Enum):
    COMPATIBLE = "COMPATIBLE"
    INCOMPATIBLE = "INCOMPATIBLE"
    REQUIRES_REVALIDATION = "REQUIRES_REVALIDATION"


class ConflictType(str, enum.Enum):
    NONE = "NONE"
    SCHEMA_CONFLICT = "SCHEMA_CONFLICT"
    VERSION_MISMATCH = "VERSION_MISMATCH"
    ECOSYSTEM_MISMATCH = "ECOSYSTEM_MISMATCH"
    CONTRACT_MISSING = "CONTRACT_MISSING"
    CYCLE_DETECTED = "CYCLE_DETECTED"
    SECURITY_VIOLATION = "SECURITY_VIOLATION"


@dataclass
class SemanticNode:
    """Formal, verifiable language-agnostic representation of a software artifact or capability."""

    node_id: str
    node_type: SemanticNodeType = SemanticNodeType.ARCHITECTURE_COMPONENT
    language: str = "agnostic"  # e.g. typescript, python, sql, agnostic
    ecosystem: str = "agnostic"  # e.g. react, fastapi, postgres, jest, playwright
    package: str = ""
    module: str = ""
    symbol: str = ""
    semantic_role: str = ""
    source_ref: str = ""
    version: str = "1.0.0"
    metadata: dict[str, Any] = field(default_factory=dict)
    properties: dict[str, Any] = field(default_factory=dict)
    name: str = ""
    type: Any = None

    def __post_init__(self) -> None:
        if not self.name and self.symbol:
            self.name = self.symbol
        elif not self.symbol and self.name:
            self.symbol = self.name
        elif not self.name and not self.symbol:
            self.name = self.node_id
            self.symbol = self.node_id

        if self.type is not None and self.node_type == SemanticNodeType.ARCHITECTURE_COMPONENT and self.type != SemanticNodeType.ARCHITECTURE_COMPONENT:
            self.node_type = self.type if isinstance(self.type, SemanticNodeType) else SemanticNodeType(str(self.type))
        elif self.node_type is not None and self.type is None:
            self.type = self.node_type

        if self.properties and not self.metadata:
            self.metadata = dict(self.properties)
        elif self.metadata and not self.properties:
            self.properties = dict(self.metadata)

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "node_type": self.node_type.value if isinstance(self.node_type, SemanticNodeType) else str(self.node_type),
            "language": self.language,
            "ecosystem": self.ecosystem,
            "package": self.package,
            "module": self.module,
            "symbol": self.symbol,
            "semantic_role": self.semantic_role,
            "source_ref": self.source_ref,
            "version": self.version,
            "metadata": self.metadata,
            "properties": self.properties,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SemanticNode:
        nt = data.get("node_type", "ARCHITECTURE_COMPONENT")
        node_type = SemanticNodeType(nt) if nt in SemanticNodeType._value2member_map_ else SemanticNodeType.ARCHITECTURE_COMPONENT
        return cls(
            node_id=str(data["node_id"]),
            node_type=node_type,
            language=str(data.get("language", "agnostic")),
            ecosystem=str(data.get("ecosystem", "agnostic")),
            package=str(data.get("package", "")),
            module=str(data.get("module", "")),
            symbol=str(data.get("symbol", "")),
            semantic_role=str(data.get("semantic_role", "")),
            source_ref=str(data.get("source_ref", "")),
            version=str(data.get("version", "1.0.0")),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass
class SemanticEdge:
    """Formal directed relationship between two SemanticNodes."""

    edge_id: str
    source: str = ""
    target: str = ""
    relation_type: Any = "DEPENDS_ON"
    source_contract: str = ""
    target_contract: str = ""
    confidence_class: Any = "DIRECT"
    direction: str = "FORWARD"  # FORWARD, BIDIRECTIONAL
    evidence_refs: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    source_id: str = ""
    target_id: str = ""
    relation: str = ""
    confidence: str = ""

    def __post_init__(self) -> None:
        if not self.source and self.source_id:
            self.source = self.source_id
        elif not self.source_id and self.source:
            self.source_id = self.source

        if not self.target and self.target_id:
            self.target = self.target_id
        elif not self.target_id and self.target:
            self.target_id = self.target

        if not self.relation and self.relation_type:
            self.relation = str(self.relation_type.value if hasattr(self.relation_type, "value") else self.relation_type)
        elif not self.relation_type and self.relation:
            self.relation_type = self.relation

        if not self.confidence and self.confidence_class:
            self.confidence = str(self.confidence_class.value if hasattr(self.confidence_class, "value") else self.confidence_class)
        elif not self.confidence_class and self.confidence:
            self.confidence_class = self.confidence

    def to_dict(self) -> dict[str, Any]:
        return {
            "edge_id": self.edge_id,
            "source": self.source,
            "target": self.target,
            "relation_type": self.relation_type.value if hasattr(self.relation_type, "value") else str(self.relation_type),
            "source_contract": self.source_contract,
            "target_contract": self.target_contract,
            "confidence_class": self.confidence_class.value if hasattr(self.confidence_class, "value") else str(self.confidence_class),
            "direction": self.direction,
            "evidence_refs": list(self.evidence_refs),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SemanticEdge:
        rt = data.get("relation_type", "DEPENDS_ON")
        relation_type = SemanticRelationType(rt) if rt in SemanticRelationType._value2member_map_ else SemanticRelationType.DEPENDS_ON

        cc = data.get("confidence_class", "DIRECT")
        confidence_class = ConfidenceClass(cc) if cc in ConfidenceClass._value2member_map_ else ConfidenceClass.DIRECT

        return cls(
            edge_id=str(data["edge_id"]),
            source=str(data["source"]),
            target=str(data["target"]),
            relation_type=relation_type,
            source_contract=str(data.get("source_contract", "")),
            target_contract=str(data.get("target_contract", "")),
            confidence_class=confidence_class,
            direction=str(data.get("direction", "FORWARD")),
            evidence_refs=list(data.get("evidence_refs", [])),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass
class ApiSemanticContract:
    """Explicit bridge contract between producer (e.g. backend) and consumers (e.g. frontend)."""

    contract_id: str
    route: str
    method: str  # GET, POST, PUT, DELETE, PATCH, etc.
    request_schema: dict[str, Any] = field(default_factory=dict)
    response_schema: dict[str, Any] = field(default_factory=dict)
    auth_requirements: list[str] = field(default_factory=list)
    version: str = "v1"
    producer: str = ""  # Backend service or node_id
    status: str = "VALIDATED"
    is_breaking: bool = False
    consumers: list[str] = field(default_factory=list)  # Frontend components or node_ids
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ApiSemanticContract:
        return cls(
            contract_id=str(data["contract_id"]),
            route=str(data.get("route", "/")),
            method=str(data.get("method", "GET")).upper(),
            request_schema=dict(data.get("request_schema", {})),
            response_schema=dict(data.get("response_schema", {})),
            auth_requirements=list(data.get("auth_requirements", [])),
            version=str(data.get("version", "v1")),
            producer=str(data.get("producer", "")),
            consumers=list(data.get("consumers", [])),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass
class TranslatedTask:
    """A concrete domain-specific task derived from semantic graph traversal and task translation."""

    task_id: str
    source_task: str
    target_domain: str  # frontend, api, backend, persistence, testing, browser
    affected_nodes: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    translation_reason: str = ""
    evidence: list[str] = field(default_factory=list)
    confidence_class: ConfidenceClass = ConfidenceClass.CONTRACTUAL
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "source_task": self.source_task,
            "target_domain": self.target_domain,
            "affected_nodes": list(self.affected_nodes),
            "dependencies": list(self.dependencies),
            "translation_reason": self.translation_reason,
            "evidence": list(self.evidence),
            "confidence_class": self.confidence_class.value if isinstance(self.confidence_class, ConfidenceClass) else str(self.confidence_class),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TranslatedTask:
        cc = data.get("confidence_class", "CONTRACTUAL")
        confidence_class = ConfidenceClass(cc) if cc in ConfidenceClass._value2member_map_ else ConfidenceClass.CONTRACTUAL
        return cls(
            task_id=str(data["task_id"]),
            source_task=str(data.get("source_task", "")),
            target_domain=str(data.get("target_domain", "backend")),
            affected_nodes=list(data.get("affected_nodes", [])),
            dependencies=list(data.get("dependencies", [])),
            translation_reason=str(data.get("translation_reason", "")),
            evidence=list(data.get("evidence", [])),
            confidence_class=confidence_class,
            metadata=dict(data.get("metadata", {})),
        )


@dataclass
class SemanticGraphVersion:
    """Immutable version envelope for graph, contracts, and adapters."""

    graph_version: int = 1
    contract_version: str = "1.0.0"
    adapter_version: str = "1.0.0"
    node_count: int = 0
    edge_count: int = 0
    timestamp: float = field(default_factory=time.time)
    version_hash: str = ""

    def calculate_hash(self, content_repr: str) -> str:
        h = hashlib.sha256(f"{self.graph_version}:{self.contract_version}:{self.adapter_version}:{content_repr}".encode()).hexdigest()
        self.version_hash = h
        return h

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
