from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, field, fields, is_dataclass
from enum import Enum
from types import MappingProxyType
from typing import Any


DOCUMENT_ENGINE_VERSION = "document_intelligence_engine_v1"
EPOCH_TIMESTAMP = "1970-01-01T00:00:00+00:00"
SHA256_LENGTH = 64
# Architecture-map identifiers intentionally preserve endpoint paths, route
# parameters and dependency names. They are never used as filesystem paths.
SAFE_ID_PATTERN = re.compile(r"^[^\x00-\x1f][^\x00-\x1f]{0,1023}$")


class EvidenceSourceKind(str, Enum):
    SOURCE_FILE = "SOURCE_FILE"
    ARCHITECTURE_MAP = "ARCHITECTURE_MAP"
    PROJECT_CONTEXT = "PROJECT_CONTEXT"
    SEMANTIC_CONTEXT = "SEMANTIC_CONTEXT"
    CAPABILITY_REGISTRY = "CAPABILITY_REGISTRY"
    MISSION_STATE = "MISSION_STATE"
    RUNTIME_INVENTORY = "RUNTIME_INVENTORY"
    BENCHMARK = "BENCHMARK"
    TELEMETRY = "TELEMETRY"


class EvidenceConfidence(str, Enum):
    CONFIRMED = "confirmed"
    PARTIAL = "partial"


class KnowledgeNodeKind(str, Enum):
    COMPONENT = "Component"
    CLASS = "Class"
    FUNCTION = "Function"
    MODULE = "Module"
    SERVICE = "Service"
    WORKFLOW = "Workflow"
    MISSION = "Mission"
    BENCHMARK = "Benchmark"
    CAPABILITY = "Capability"
    PROVIDER = "Provider"
    EXECUTOR = "Executor"
    TOOL = "Tool"
    ENDPOINT = "Endpoint"
    TEST = "Test"
    CONFIGURATION = "Configuration"


class ReviewSeverity(str, Enum):
    ERROR = "ERROR"
    WARNING = "WARNING"


class DocumentFormat(str, Enum):
    MARKDOWN = "markdown"
    HTML = "html"
    JSON = "json"
    DOCX = "docx"
    PDF = "pdf"


@dataclass(frozen=True)
class DocumentProject:
    project_id: str
    root_path: str
    project_name: str = ""
    architecture_map_path: str = "architecture-map.json"

    def __post_init__(self) -> None:
        _required(self.project_id, "DocumentProject.project_id")
        _required(self.root_path, "DocumentProject.root_path")
        _required(
            self.architecture_map_path,
            "DocumentProject.architecture_map_path",
        )
        object.__setattr__(
            self,
            "project_name",
            str(self.project_name or self.project_id).strip(),
        )


@dataclass(frozen=True)
class EvidenceSource:
    source_id: str
    kind: EvidenceSourceKind
    location: str
    content_sha256: str
    observed_at: str = EPOCH_TIMESTAMP
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _safe_id(self.source_id, "EvidenceSource.source_id")
        _required(self.location, "EvidenceSource.location")
        _validate_sha256(
            self.content_sha256,
            "EvidenceSource.content_sha256",
        )
        object.__setattr__(self, "metadata", freeze_mapping(self.metadata))


@dataclass(frozen=True)
class Evidence:
    evidence_id: str
    claim: str
    source_id: str
    file_path: str
    symbol: str
    line: int
    content_sha256: str
    confidence: EvidenceConfidence = EvidenceConfidence.CONFIRMED

    def __post_init__(self) -> None:
        _safe_id(self.evidence_id, "Evidence.evidence_id")
        _required(self.claim, "Evidence.claim")
        _safe_id(self.source_id, "Evidence.source_id")
        _required(self.file_path, "Evidence.file_path")
        if self.line < 1:
            raise ValueError("Evidence.line must be positive.")
        _validate_sha256(self.content_sha256, "Evidence.content_sha256")


@dataclass(frozen=True)
class FactEntity:
    entity_id: str
    kind: KnowledgeNodeKind
    name: str
    path: str
    symbol: str
    evidence_ids: tuple[str, ...]
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _safe_id(self.entity_id, "FactEntity.entity_id")
        _required(self.name, "FactEntity.name")
        _required(self.path, "FactEntity.path")
        object.__setattr__(
            self,
            "evidence_ids",
            tuple(sorted(set(str(item) for item in self.evidence_ids))),
        )
        if not self.evidence_ids:
            raise ValueError("FactEntity requires evidence_ids.")
        object.__setattr__(self, "attributes", freeze_mapping(self.attributes))


@dataclass(frozen=True)
class FactRelationship:
    relationship_id: str
    source_id: str
    target_id: str
    relation_type: str
    evidence_ids: tuple[str, ...]
    confidence: EvidenceConfidence = EvidenceConfidence.CONFIRMED

    def __post_init__(self) -> None:
        _safe_id(self.relationship_id, "FactRelationship.relationship_id")
        _safe_id(self.source_id, "FactRelationship.source_id")
        _safe_id(self.target_id, "FactRelationship.target_id")
        _required(self.relation_type, "FactRelationship.relation_type")
        object.__setattr__(
            self,
            "evidence_ids",
            tuple(sorted(set(str(item) for item in self.evidence_ids))),
        )
        if not self.evidence_ids:
            raise ValueError("FactRelationship requires evidence_ids.")


@dataclass(frozen=True)
class EvidenceGraph:
    sources: tuple[EvidenceSource, ...]
    evidence: tuple[Evidence, ...]
    content_sha256: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "sources",
            tuple(sorted(self.sources, key=lambda item: item.source_id)),
        )
        object.__setattr__(
            self,
            "evidence",
            tuple(sorted(self.evidence, key=lambda item: item.evidence_id)),
        )
        _validate_sha256(
            self.content_sha256,
            "EvidenceGraph.content_sha256",
        )
        if self.computed_content_sha256() != self.content_sha256:
            raise ValueError("EvidenceGraph content hash does not match.")

    def payload_without_content_hash(self) -> dict[str, Any]:
        payload = to_jsonable(self)
        payload.pop("content_sha256", None)
        return payload

    def computed_content_sha256(self) -> str:
        return sha256_json(self.payload_without_content_hash())

    @classmethod
    def create(
        cls,
        sources: tuple[EvidenceSource, ...],
        evidence: tuple[Evidence, ...],
    ) -> "EvidenceGraph":
        ordered_sources = tuple(
            sorted(sources, key=lambda item: item.source_id)
        )
        ordered_evidence = tuple(
            sorted(evidence, key=lambda item: item.evidence_id)
        )
        payload = {
            "sources": ordered_sources,
            "evidence": ordered_evidence,
        }
        return cls(
            sources=ordered_sources,
            evidence=ordered_evidence,
            content_sha256=sha256_json(payload),
        )


@dataclass(frozen=True)
class KnowledgeNode:
    node_id: str
    kind: KnowledgeNodeKind
    name: str
    path: str
    symbol: str
    evidence_ids: tuple[str, ...]
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _safe_id(self.node_id, "KnowledgeNode.node_id")
        _required(self.name, "KnowledgeNode.name")
        _required(self.path, "KnowledgeNode.path")
        object.__setattr__(
            self,
            "evidence_ids",
            tuple(sorted(set(str(item) for item in self.evidence_ids))),
        )
        if not self.evidence_ids:
            raise ValueError("KnowledgeNode requires evidence_ids.")
        object.__setattr__(self, "attributes", freeze_mapping(self.attributes))


@dataclass(frozen=True)
class KnowledgeRelation:
    relation_id: str
    source_id: str
    target_id: str
    relation_type: str
    evidence_ids: tuple[str, ...]
    confidence: EvidenceConfidence = EvidenceConfidence.CONFIRMED

    def __post_init__(self) -> None:
        _safe_id(self.relation_id, "KnowledgeRelation.relation_id")
        _safe_id(self.source_id, "KnowledgeRelation.source_id")
        _safe_id(self.target_id, "KnowledgeRelation.target_id")
        _required(self.relation_type, "KnowledgeRelation.relation_type")
        object.__setattr__(
            self,
            "evidence_ids",
            tuple(sorted(set(str(item) for item in self.evidence_ids))),
        )
        if not self.evidence_ids:
            raise ValueError("KnowledgeRelation requires evidence_ids.")


@dataclass(frozen=True)
class KnowledgeGraph:
    nodes: tuple[KnowledgeNode, ...]
    relations: tuple[KnowledgeRelation, ...]
    content_sha256: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "nodes",
            tuple(sorted(self.nodes, key=lambda item: item.node_id)),
        )
        object.__setattr__(
            self,
            "relations",
            tuple(sorted(self.relations, key=lambda item: item.relation_id)),
        )
        _validate_sha256(
            self.content_sha256,
            "KnowledgeGraph.content_sha256",
        )
        if self.computed_content_sha256() != self.content_sha256:
            raise ValueError("KnowledgeGraph content hash does not match.")

    def payload_without_content_hash(self) -> dict[str, Any]:
        payload = to_jsonable(self)
        payload.pop("content_sha256", None)
        return payload

    def computed_content_sha256(self) -> str:
        return sha256_json(self.payload_without_content_hash())

    @classmethod
    def create(
        cls,
        nodes: tuple[KnowledgeNode, ...],
        relations: tuple[KnowledgeRelation, ...],
    ) -> "KnowledgeGraph":
        ordered_nodes = tuple(sorted(nodes, key=lambda item: item.node_id))
        ordered_relations = tuple(
            sorted(relations, key=lambda item: item.relation_id)
        )
        payload = {
            "nodes": ordered_nodes,
            "relations": ordered_relations,
        }
        return cls(
            nodes=ordered_nodes,
            relations=ordered_relations,
            content_sha256=sha256_json(payload),
        )


@dataclass(frozen=True)
class DocumentFacts:
    project: DocumentProject
    evidence_graph: EvidenceGraph
    entities: tuple[FactEntity, ...]
    relationships: tuple[FactRelationship, ...]
    source_counts: Mapping[str, int]
    collection_issues: tuple[str, ...] = ()
    content_sha256: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "entities",
            tuple(sorted(self.entities, key=lambda item: item.entity_id)),
        )
        object.__setattr__(
            self,
            "relationships",
            tuple(
                sorted(
                    self.relationships,
                    key=lambda item: item.relationship_id,
                )
            ),
        )
        object.__setattr__(
            self,
            "source_counts",
            freeze_mapping(self.source_counts),
        )
        object.__setattr__(
            self,
            "collection_issues",
            tuple(sorted(set(str(item) for item in self.collection_issues))),
        )
        _validate_sha256(
            self.content_sha256,
            "DocumentFacts.content_sha256",
        )
        if self.computed_content_sha256() != self.content_sha256:
            raise ValueError("DocumentFacts content hash does not match.")

    def payload_without_content_hash(self) -> dict[str, Any]:
        payload = to_jsonable(self)
        payload.pop("content_sha256", None)
        return payload

    def computed_content_sha256(self) -> str:
        return sha256_json(self.payload_without_content_hash())

    @classmethod
    def create(
        cls,
        *,
        project: DocumentProject,
        evidence_graph: EvidenceGraph,
        entities: tuple[FactEntity, ...],
        relationships: tuple[FactRelationship, ...],
        source_counts: Mapping[str, int],
        collection_issues: tuple[str, ...] = (),
    ) -> "DocumentFacts":
        ordered_entities = tuple(
            sorted(entities, key=lambda item: item.entity_id)
        )
        ordered_relationships = tuple(
            sorted(relationships, key=lambda item: item.relationship_id)
        )
        normalized_source_counts = freeze_mapping(source_counts)
        normalized_issues = tuple(
            sorted(set(str(item) for item in collection_issues))
        )
        payload = {
            "project": project,
            "evidence_graph": evidence_graph,
            "entities": ordered_entities,
            "relationships": ordered_relationships,
            "source_counts": normalized_source_counts,
            "collection_issues": normalized_issues,
        }
        return cls(
            project=project,
            evidence_graph=evidence_graph,
            entities=ordered_entities,
            relationships=ordered_relationships,
            source_counts=normalized_source_counts,
            collection_issues=normalized_issues,
            content_sha256=sha256_json(payload),
        )


@dataclass(frozen=True)
class DocumentClaim:
    claim_id: str
    text: str
    evidence_ids: tuple[str, ...]
    subject_id: str = ""
    predicate: str = ""
    object_id: str = ""

    def __post_init__(self) -> None:
        _safe_id(self.claim_id, "DocumentClaim.claim_id")
        _required(self.text, "DocumentClaim.text")
        object.__setattr__(
            self,
            "evidence_ids",
            tuple(sorted(set(str(item) for item in self.evidence_ids))),
        )
        if not self.evidence_ids:
            raise ValueError("DocumentClaim requires evidence_ids.")


@dataclass(frozen=True)
class DocumentSection:
    section_id: str
    title: str
    claims: tuple[DocumentClaim, ...]
    related_node_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _safe_id(self.section_id, "DocumentSection.section_id")
        _required(self.title, "DocumentSection.title")
        object.__setattr__(self, "claims", tuple(self.claims))
        object.__setattr__(
            self,
            "related_node_ids",
            tuple(sorted(set(str(item) for item in self.related_node_ids))),
        )


@dataclass(frozen=True)
class DocumentTemplate:
    template_id: str
    display_name: str
    document_type: str
    section_ids: tuple[str, ...]
    node_kinds: tuple[KnowledgeNodeKind, ...] = ()
    relation_types: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _safe_id(self.template_id, "DocumentTemplate.template_id")
        _required(self.display_name, "DocumentTemplate.display_name")
        _required(self.document_type, "DocumentTemplate.document_type")
        if not self.section_ids:
            raise ValueError("DocumentTemplate requires section_ids.")
        object.__setattr__(self, "section_ids", tuple(self.section_ids))
        object.__setattr__(
            self,
            "node_kinds",
            tuple(sorted(set(self.node_kinds), key=lambda item: item.value)),
        )
        object.__setattr__(
            self,
            "relation_types",
            tuple(sorted(set(str(item) for item in self.relation_types))),
        )


@dataclass(frozen=True)
class DocumentDiagram:
    diagram_id: str
    title: str
    mermaid: str
    plantuml: str
    svg: str
    node_ids: tuple[str, ...]
    relation_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _safe_id(self.diagram_id, "DocumentDiagram.diagram_id")
        _required(self.title, "DocumentDiagram.title")
        object.__setattr__(
            self,
            "node_ids",
            tuple(sorted(set(str(item) for item in self.node_ids))),
        )
        object.__setattr__(
            self,
            "relation_ids",
            tuple(sorted(set(str(item) for item in self.relation_ids))),
        )


@dataclass(frozen=True)
class GeneratedDocument:
    document_id: str
    template_id: str
    document_type: str
    title: str
    snapshot_sha256: str
    sections: tuple[DocumentSection, ...]
    diagrams: tuple[DocumentDiagram, ...]
    content_sha256: str

    def __post_init__(self) -> None:
        _safe_id(self.document_id, "GeneratedDocument.document_id")
        _safe_id(self.template_id, "GeneratedDocument.template_id")
        _required(self.document_type, "GeneratedDocument.document_type")
        _required(self.title, "GeneratedDocument.title")
        _validate_sha256(
            self.snapshot_sha256,
            "GeneratedDocument.snapshot_sha256",
        )
        object.__setattr__(self, "sections", tuple(self.sections))
        object.__setattr__(self, "diagrams", tuple(self.diagrams))
        _validate_sha256(
            self.content_sha256,
            "GeneratedDocument.content_sha256",
        )
        if self.computed_content_sha256() != self.content_sha256:
            raise ValueError("GeneratedDocument content hash does not match.")

    def payload_without_content_hash(self) -> dict[str, Any]:
        payload = to_jsonable(self)
        payload.pop("content_sha256", None)
        return payload

    def computed_content_sha256(self) -> str:
        return sha256_json(self.payload_without_content_hash())

    @classmethod
    def create(
        cls,
        *,
        document_id: str,
        template_id: str,
        document_type: str,
        title: str,
        snapshot_sha256: str,
        sections: tuple[DocumentSection, ...],
        diagrams: tuple[DocumentDiagram, ...],
    ) -> "GeneratedDocument":
        ordered_diagrams = tuple(
            sorted(diagrams, key=lambda item: item.diagram_id)
        )
        payload = {
            "document_id": document_id,
            "template_id": template_id,
            "document_type": document_type,
            "title": title,
            "snapshot_sha256": snapshot_sha256,
            "sections": sections,
            "diagrams": ordered_diagrams,
        }
        return cls(
            document_id=document_id,
            template_id=template_id,
            document_type=document_type,
            title=title,
            snapshot_sha256=snapshot_sha256,
            sections=sections,
            diagrams=ordered_diagrams,
            content_sha256=sha256_json(payload),
        )


@dataclass(frozen=True)
class ReviewIssue:
    code: str
    message: str
    severity: ReviewSeverity
    location: str

    def __post_init__(self) -> None:
        _required(self.code, "ReviewIssue.code")
        _required(self.message, "ReviewIssue.message")
        _required(self.location, "ReviewIssue.location")


@dataclass(frozen=True)
class DocumentReview:
    document_id: str
    approved: bool
    issues: tuple[ReviewIssue, ...]
    checked_evidence: int
    checked_claims: int

    def __post_init__(self) -> None:
        _safe_id(self.document_id, "DocumentReview.document_id")
        object.__setattr__(
            self,
            "issues",
            tuple(
                sorted(
                    self.issues,
                    key=lambda item: (
                        item.severity.value,
                        item.code,
                        item.location,
                    ),
                )
            ),
        )
        if self.checked_evidence < 0 or self.checked_claims < 0:
            raise ValueError("DocumentReview counters cannot be negative.")
        if self.approved and any(
            issue.severity is ReviewSeverity.ERROR
            for issue in self.issues
        ):
            raise ValueError("DocumentReview cannot approve errors.")


@dataclass(frozen=True)
class GenerationConfiguration:
    document_types: tuple[str, ...]
    formats: tuple[DocumentFormat, ...] = (
        DocumentFormat.MARKDOWN,
        DocumentFormat.HTML,
        DocumentFormat.JSON,
    )
    generated_at: str = EPOCH_TIMESTAMP
    include_diagrams: bool = True
    max_claims_per_section: int = 40
    mission_id: str = ""
    snapshot_sha256: str = ""

    def __post_init__(self) -> None:
        if not self.document_types:
            raise ValueError("GenerationConfiguration requires document_types.")
        object.__setattr__(
            self,
            "document_types",
            tuple(sorted(set(str(item) for item in self.document_types))),
        )
        object.__setattr__(
            self,
            "formats",
            tuple(sorted(set(self.formats), key=lambda item: item.value)),
        )
        if self.max_claims_per_section < 1:
            raise ValueError(
                "GenerationConfiguration.max_claims_per_section must be positive."
            )
        if self.snapshot_sha256:
            _validate_sha256(
                self.snapshot_sha256,
                "GenerationConfiguration.snapshot_sha256",
            )


@dataclass(frozen=True)
class DocumentSnapshot:
    engine_version: str
    project: DocumentProject
    facts: DocumentFacts
    evidence_graph: EvidenceGraph
    knowledge_graph: KnowledgeGraph
    generated_at: str
    content_sha256: str

    def __post_init__(self) -> None:
        _required(self.engine_version, "DocumentSnapshot.engine_version")
        _validate_sha256(
            self.content_sha256,
            "DocumentSnapshot.content_sha256",
        )
        if self.facts.evidence_graph.content_sha256 != self.evidence_graph.content_sha256:
            raise ValueError(
                "DocumentSnapshot facts and evidence graph diverge."
            )
        if self.computed_content_sha256() != self.content_sha256:
            raise ValueError("DocumentSnapshot content hash does not match.")

    def payload_without_content_hash(self) -> dict[str, Any]:
        payload = to_jsonable(self)
        payload.pop("content_sha256", None)
        return payload

    def computed_content_sha256(self) -> str:
        return sha256_json(self.payload_without_content_hash())

    @classmethod
    def create(
        cls,
        *,
        project: DocumentProject,
        facts: DocumentFacts,
        evidence_graph: EvidenceGraph,
        knowledge_graph: KnowledgeGraph,
        generated_at: str,
    ) -> "DocumentSnapshot":
        payload = {
            "engine_version": DOCUMENT_ENGINE_VERSION,
            "project": project,
            "facts": facts,
            "evidence_graph": evidence_graph,
            "knowledge_graph": knowledge_graph,
            "generated_at": generated_at,
        }
        return cls(
            engine_version=DOCUMENT_ENGINE_VERSION,
            project=project,
            facts=facts,
            evidence_graph=evidence_graph,
            knowledge_graph=knowledge_graph,
            generated_at=generated_at,
            content_sha256=sha256_json(payload),
        )


@dataclass(frozen=True)
class DocumentMetrics:
    duration_ms: float
    source_count: int
    evidence_count: int
    claim_count: int
    issue_count: int
    output_bytes: int

    def __post_init__(self) -> None:
        if self.duration_ms < 0:
            raise ValueError("DocumentMetrics.duration_ms cannot be negative.")
        if any(
            value < 0
            for value in (
                self.source_count,
                self.evidence_count,
                self.claim_count,
                self.issue_count,
                self.output_bytes,
            )
        ):
            raise ValueError("DocumentMetrics counters cannot be negative.")


@dataclass(frozen=True)
class DocumentTelemetry:
    event: str
    document_id: str
    document_type: str
    snapshot_sha256: str
    metrics: DocumentMetrics
    source_kinds: tuple[str, ...]
    approved: bool | None = None

    def __post_init__(self) -> None:
        _required(self.event, "DocumentTelemetry.event")
        _safe_id(self.document_id, "DocumentTelemetry.document_id")
        _required(self.document_type, "DocumentTelemetry.document_type")
        _validate_sha256(
            self.snapshot_sha256,
            "DocumentTelemetry.snapshot_sha256",
        )
        object.__setattr__(
            self,
            "source_kinds",
            tuple(sorted(set(str(item) for item in self.source_kinds))),
        )


@dataclass(frozen=True)
class ExportResult:
    document_id: str
    files: Mapping[str, str]
    file_hashes: Mapping[str, str]

    def __post_init__(self) -> None:
        _safe_id(self.document_id, "ExportResult.document_id")
        object.__setattr__(self, "files", freeze_mapping(self.files))
        object.__setattr__(
            self,
            "file_hashes",
            freeze_mapping(self.file_hashes),
        )
        if set(self.files) != set(self.file_hashes):
            raise ValueError("ExportResult files and hashes must match.")
        for value in self.file_hashes.values():
            _validate_sha256(value, "ExportResult.file_hashes")


def freeze_mapping(value: Mapping[Any, Any] | None) -> Mapping[str, Any]:
    return MappingProxyType({
        str(key): freeze_value(item)
        for key, item in sorted(
            (value or {}).items(),
            key=lambda pair: str(pair[0]),
        )
    })


def freeze_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return freeze_mapping(value)
    if isinstance(value, (tuple, list)):
        return tuple(freeze_value(item) for item in value)
    if isinstance(value, (set, frozenset)):
        return tuple(sorted((freeze_value(item) for item in value), key=canonical_json))
    return value


def to_jsonable(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return {
            item.name: to_jsonable(getattr(value, item.name))
            for item in fields(value)
        }
    if isinstance(value, Mapping):
        return {
            str(key): to_jsonable(item)
            for key, item in sorted(
                value.items(),
                key=lambda pair: str(pair[0]),
            )
        }
    if isinstance(value, (tuple, list)):
        return [to_jsonable(item) for item in value]
    if isinstance(value, (set, frozenset)):
        return sorted((to_jsonable(item) for item in value), key=canonical_json)
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


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def stable_id(*parts: str) -> str:
    text = "|".join(str(part) for part in parts)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:32]


def _required(value: Any, field_name: str) -> None:
    if not str(value or "").strip():
        raise ValueError(f"{field_name} is required.")


def _safe_id(value: str, field_name: str) -> None:
    if not SAFE_ID_PATTERN.fullmatch(str(value or "")):
        raise ValueError(f"{field_name} is invalid.")


def _validate_sha256(value: str, field_name: str) -> None:
    normalized = str(value or "").strip().lower()
    if (
        len(normalized) != SHA256_LENGTH
        or any(character not in "0123456789abcdef" for character in normalized)
    ):
        raise ValueError(f"{field_name} must be a SHA-256 hexadecimal value.")
