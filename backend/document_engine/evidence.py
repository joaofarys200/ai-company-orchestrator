from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import is_dataclass
from pathlib import Path
from typing import Any

from backend.document_engine.contracts import (
    DocumentFacts,
    DocumentProject,
    Evidence,
    EvidenceConfidence,
    EvidenceGraph,
    EvidenceSource,
    EvidenceSourceKind,
    FactEntity,
    FactRelationship,
    GeneratedDocument,
    KnowledgeGraph,
    KnowledgeNode,
    KnowledgeNodeKind,
    KnowledgeRelation,
    canonical_json,
    sha256_json,
    stable_id,
    to_jsonable,
)


HASH_CHUNK_BYTES = 1024 * 1024
ARCHITECTURE_ENTITY_BUCKETS = (
    "systems",
    "layers",
    "components",
    "contracts",
    "endpoints",
    "websockets",
    "tools",
    "agents",
    "providers",
    "datastores",
    "workflows",
    "state_machines",
    "external_dependencies",
    "tests",
    "benchmarks",
    "diagnostics",
)

TYPE_TO_NODE_KIND = {
    "agent": KnowledgeNodeKind.COMPONENT,
    "api_endpoint": KnowledgeNodeKind.ENDPOINT,
    "benchmark": KnowledgeNodeKind.BENCHMARK,
    "class": KnowledgeNodeKind.CLASS,
    "component": KnowledgeNodeKind.COMPONENT,
    "configuration": KnowledgeNodeKind.CONFIGURATION,
    "contract": KnowledgeNodeKind.CONFIGURATION,
    "data_contract": KnowledgeNodeKind.CONFIGURATION,
    "datastore": KnowledgeNodeKind.SERVICE,
    "diagnostic": KnowledgeNodeKind.BENCHMARK,
    "endpoint": KnowledgeNodeKind.ENDPOINT,
    "executor": KnowledgeNodeKind.EXECUTOR,
    "external_dependency": KnowledgeNodeKind.SERVICE,
    "function": KnowledgeNodeKind.FUNCTION,
    "layer": KnowledgeNodeKind.CONFIGURATION,
    "mission": KnowledgeNodeKind.MISSION,
    "module": KnowledgeNodeKind.MODULE,
    "provider": KnowledgeNodeKind.PROVIDER,
    "script": KnowledgeNodeKind.BENCHMARK,
    "service": KnowledgeNodeKind.SERVICE,
    "state_machine": KnowledgeNodeKind.WORKFLOW,
    "system": KnowledgeNodeKind.COMPONENT,
    "test": KnowledgeNodeKind.TEST,
    "test_suite": KnowledgeNodeKind.TEST,
    "tool": KnowledgeNodeKind.TOOL,
    "websocket": KnowledgeNodeKind.SERVICE,
    "workflow": KnowledgeNodeKind.WORKFLOW,
}


class FactCollectionError(ValueError):
    """Raised when a factual source cannot be collected safely."""


class EvidenceCollector:
    """Build factual contracts from static, public project artifacts only."""

    def __init__(self, *, hash_chunk_bytes: int = HASH_CHUNK_BYTES) -> None:
        if hash_chunk_bytes < 1:
            raise ValueError("hash_chunk_bytes must be positive.")
        self._hash_chunk_bytes = hash_chunk_bytes

    def collect(
        self,
        project: DocumentProject,
        *,
        public_artifacts: Mapping[EvidenceSourceKind, Any] | None = None,
    ) -> DocumentFacts:
        """Collect verified map facts and register supplied public snapshots.

        Extra snapshots are treated as source provenance only. They cannot create
        prose claims unless a future adapter can establish the same file, symbol,
        line and hash evidence required for architecture-map facts.
        """

        root = Path(project.root_path).resolve()
        if not root.is_dir():
            raise FactCollectionError(
                f"Document project root does not exist: {root}"
            )
        map_path = self._resolve_project_path(
            root,
            project.architecture_map_path,
        )
        if not map_path.is_file():
            raise FactCollectionError(
                f"Architecture map does not exist: {map_path}"
            )
        try:
            map_data = json.loads(map_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise FactCollectionError(
                f"Architecture map is unreadable: {map_path}"
            ) from exc
        if not isinstance(map_data, Mapping):
            raise FactCollectionError("Architecture map root must be an object.")

        source_cache: dict[str, EvidenceSource] = {}
        source_line_counts: dict[str, int] = {}
        source_hashes: dict[str, str] = {}
        map_relative = self._relative(root, map_path)
        map_hash, map_size, _ = self._hash_file(map_path)
        sources: list[EvidenceSource] = [
            EvidenceSource(
                source_id=f"architecture-map:{map_relative}",
                kind=EvidenceSourceKind.ARCHITECTURE_MAP,
                location=map_relative,
                content_sha256=map_hash,
                metadata={"size_bytes": map_size},
            )
        ]
        evidence: list[Evidence] = []
        entities: dict[str, FactEntity] = {}
        relationships: list[FactRelationship] = []
        issues: list[str] = []

        for bucket in ARCHITECTURE_ENTITY_BUCKETS:
            records = map_data.get(bucket, ())
            if not isinstance(records, list):
                issues.append(f"invalid_entity_bucket:{bucket}")
                continue
            for record in records:
                if not isinstance(record, Mapping):
                    issues.append(f"invalid_entity_record:{bucket}")
                    continue
                entity, new_evidence, source = self._entity_from_record(
                    root=root,
                    record=record,
                    source_cache=source_cache,
                    source_hashes=source_hashes,
                    source_line_counts=source_line_counts,
                )
                if entity is None:
                    record_id = str(record.get("id", "unknown"))
                    issues.append(
                        f"unverified_entity_omitted:{record_id}"
                    )
                    continue
                if entity.entity_id not in entities:
                    entities[entity.entity_id] = entity
                    evidence.extend(new_evidence)
                    if source is not None:
                        sources.append(source)

        evidence_ids = {item.evidence_id for item in evidence}
        for index, record in enumerate(map_data.get("relations", ())):
            if not isinstance(record, Mapping):
                issues.append("invalid_relationship_record")
                continue
            relation, new_evidence, source = self._relationship_from_record(
                root=root,
                record=record,
                index=index,
                known_entity_ids=set(entities),
                source_cache=source_cache,
                source_hashes=source_hashes,
                source_line_counts=source_line_counts,
            )
            if relation is None:
                source_id = str(record.get("source", "unknown"))
                target_id = str(record.get("target", "unknown"))
                issues.append(
                    "unverified_relationship_omitted:"
                    f"{source_id}->{target_id}"
                )
                continue
            if not set(relation.evidence_ids).issubset(evidence_ids):
                evidence.extend(new_evidence)
                evidence_ids.update(item.evidence_id for item in new_evidence)
            if source is not None:
                sources.append(source)
            relationships.append(relation)

        # Evidence can reference several source files for one map record. The
        # cache is the complete authoritative list, not merely the first source
        # encountered for each record.
        sources.extend(source_cache.values())
        sources.extend(
            self._public_artifact_sources(public_artifacts or {})
        )
        evidence_graph = EvidenceGraph.create(
            sources=tuple({item.source_id: item for item in sources}.values()),
            evidence=tuple({item.evidence_id: item for item in evidence}.values()),
        )
        return DocumentFacts.create(
            project=project,
            evidence_graph=evidence_graph,
            entities=tuple(entities.values()),
            relationships=tuple(relationships),
            source_counts=self._source_counts(evidence_graph),
            collection_issues=tuple(issues),
        )

    def _entity_from_record(
        self,
        *,
        root: Path,
        record: Mapping[str, Any],
        source_cache: dict[str, EvidenceSource],
        source_hashes: dict[str, str],
        source_line_counts: dict[str, int],
    ) -> tuple[FactEntity | None, list[Evidence], EvidenceSource | None]:
        entity_id = str(record.get("id", "")).strip()
        name = str(record.get("name", "")).strip()
        path = str(record.get("path", "")).replace("\\", "/").strip()
        if not entity_id or not name or not path:
            return None, [], None
        evidence, source = self._verified_evidence(
            root=root,
            record_id=entity_id,
            evidence_records=record.get("evidence", ()),
            default_symbol=name,
            source_cache=source_cache,
            source_hashes=source_hashes,
            source_line_counts=source_line_counts,
        )
        if not evidence:
            return None, [], source
        kind = TYPE_TO_NODE_KIND.get(
            str(record.get("type", record.get("category", "component"))).lower(),
            KnowledgeNodeKind.COMPONENT,
        )
        attributes = {
            key: record[key]
            for key in (
                "category",
                "criticality",
                "language",
                "layer",
                "runtime",
                "status",
                "subsystem",
                "type",
            )
            if key in record
        }
        return (
            FactEntity(
                entity_id=entity_id,
                kind=kind,
                name=name,
                path=path,
                symbol=name,
                evidence_ids=tuple(item.evidence_id for item in evidence),
                attributes=attributes,
            ),
            evidence,
            source,
        )

    def _relationship_from_record(
        self,
        *,
        root: Path,
        record: Mapping[str, Any],
        index: int,
        known_entity_ids: set[str],
        source_cache: dict[str, EvidenceSource],
        source_hashes: dict[str, str],
        source_line_counts: dict[str, int],
    ) -> tuple[FactRelationship | None, list[Evidence], EvidenceSource | None]:
        source_id = str(record.get("source", "")).strip()
        target_id = str(record.get("target", "")).strip()
        relation_type = str(record.get("type", "")).strip()
        if (
            not source_id
            or not target_id
            or not relation_type
            or source_id not in known_entity_ids
            or target_id not in known_entity_ids
        ):
            return None, [], None
        relation_key = stable_id(
            "relation",
            source_id,
            target_id,
            relation_type,
            str(index),
        )
        description = str(record.get("description", relation_type))
        evidence, source = self._verified_evidence(
            root=root,
            record_id=relation_key,
            evidence_records=record.get("evidence", ()),
            default_symbol="__relation__",
            default_claim=description,
            source_cache=source_cache,
            source_hashes=source_hashes,
            source_line_counts=source_line_counts,
        )
        if not evidence:
            return None, [], source
        return (
            FactRelationship(
                relationship_id=f"relation:{relation_key}",
                source_id=source_id,
                target_id=target_id,
                relation_type=relation_type,
                evidence_ids=tuple(item.evidence_id for item in evidence),
                confidence=self._confidence(record.get("confidence")),
            ),
            evidence,
            source,
        )

    def _verified_evidence(
        self,
        *,
        root: Path,
        record_id: str,
        evidence_records: Any,
        default_symbol: str,
        source_cache: dict[str, EvidenceSource],
        source_hashes: dict[str, str],
        source_line_counts: dict[str, int],
        default_claim: str = "",
    ) -> tuple[list[Evidence], EvidenceSource | None]:
        if not isinstance(evidence_records, list):
            return [], None
        verified: list[Evidence] = []
        first_source: EvidenceSource | None = None
        for index, evidence_record in enumerate(evidence_records):
            if not isinstance(evidence_record, Mapping):
                continue
            source_path = str(evidence_record.get("path", "")).strip()
            line = evidence_record.get("line")
            if not source_path or not isinstance(line, int) or line < 1:
                continue
            try:
                resolved = self._resolve_project_path(root, source_path)
            except FactCollectionError:
                continue
            if not resolved.is_file():
                continue
            relative_path = self._relative(root, resolved)
            if relative_path not in source_hashes:
                file_hash, size_bytes, line_count = self._hash_file(resolved)
                source_hashes[relative_path] = file_hash
                source_line_counts[relative_path] = line_count
                source_cache[relative_path] = EvidenceSource(
                    source_id=f"source:{relative_path}",
                    kind=EvidenceSourceKind.SOURCE_FILE,
                    location=relative_path,
                    content_sha256=file_hash,
                    metadata={"size_bytes": size_bytes},
                )
            if line > source_line_counts[relative_path]:
                continue
            source = source_cache[relative_path]
            if first_source is None:
                first_source = source
            claim = str(
                evidence_record.get("claim", default_claim or record_id)
            ).strip()
            if not claim:
                continue
            symbol = str(
                evidence_record.get("symbol", default_symbol)
            ).strip() or "__file__"
            confidence = self._confidence(evidence_record.get("confidence"))
            evidence_id = f"evidence:{stable_id(record_id, relative_path, str(line), claim, symbol)}"
            verified.append(
                Evidence(
                    evidence_id=evidence_id,
                    claim=claim,
                    source_id=source.source_id,
                    file_path=relative_path,
                    symbol=symbol,
                    line=line,
                    content_sha256=source.content_sha256,
                    confidence=confidence,
                )
            )
        return verified, first_source

    def _public_artifact_sources(
        self,
        artifacts: Mapping[EvidenceSourceKind, Any],
    ) -> list[EvidenceSource]:
        sources: list[EvidenceSource] = []
        for kind, artifact in sorted(
            artifacts.items(),
            key=lambda item: str(item[0]),
        ):
            if not isinstance(kind, EvidenceSourceKind):
                raise FactCollectionError(
                    "public_artifacts keys must be EvidenceSourceKind values."
                )
            if isinstance(artifact, GeneratedDocument):
                raise FactCollectionError(
                    "Previously generated documents are not factual sources."
                )
            if not isinstance(artifact, Mapping) and not is_dataclass(artifact):
                raise FactCollectionError(
                    "Public artifacts must be immutable contracts or mappings."
                )
            payload = to_jsonable(artifact)
            source_id = f"public:{kind.value.lower()}"
            sources.append(
                EvidenceSource(
                    source_id=source_id,
                    kind=kind,
                    location=f"public/{kind.value.lower()}.json",
                    content_sha256=sha256_json(payload),
                    metadata={"virtual": True},
                )
            )
        return sources

    def _hash_file(self, path: Path) -> tuple[str, int, int]:
        digest = hashlib.sha256()
        size_bytes = 0
        newline_count = 0
        has_content = False
        last_byte = b""
        with path.open("rb") as handle:
            while chunk := handle.read(self._hash_chunk_bytes):
                digest.update(chunk)
                size_bytes += len(chunk)
                newline_count += chunk.count(b"\n")
                has_content = True
                last_byte = chunk[-1:]
        line_count = 0
        if has_content:
            line_count = newline_count + (0 if last_byte == b"\n" else 1)
        return digest.hexdigest(), size_bytes, line_count

    @staticmethod
    def _confidence(value: Any) -> EvidenceConfidence:
        return (
            EvidenceConfidence.CONFIRMED
            if str(value or "confirmed").lower() == "confirmed"
            else EvidenceConfidence.PARTIAL
        )

    @staticmethod
    def _source_counts(graph: EvidenceGraph) -> Mapping[str, int]:
        counts: dict[str, int] = {}
        for source in graph.sources:
            counts[source.kind.value] = counts.get(source.kind.value, 0) + 1
        return counts

    @staticmethod
    def _resolve_project_path(root: Path, path: str) -> Path:
        candidate = Path(path)
        resolved = (
            candidate.resolve()
            if candidate.is_absolute()
            else (root / candidate).resolve()
        )
        try:
            resolved.relative_to(root)
        except ValueError as exc:
            raise FactCollectionError(
                f"Source escapes document project root: {path}"
            ) from exc
        return resolved

    @staticmethod
    def _relative(root: Path, path: Path) -> str:
        return path.relative_to(root).as_posix()


class KnowledgeGraphBuilder:
    """Derive a graph only from already verified factual contracts."""

    def build(self, facts: DocumentFacts) -> KnowledgeGraph:
        evidence_ids = {
            evidence.evidence_id
            for evidence in facts.evidence_graph.evidence
        }
        nodes = tuple(
            KnowledgeNode(
                node_id=entity.entity_id,
                kind=entity.kind,
                name=entity.name,
                path=entity.path,
                symbol=entity.symbol,
                evidence_ids=entity.evidence_ids,
                attributes=entity.attributes,
            )
            for entity in facts.entities
            if set(entity.evidence_ids).issubset(evidence_ids)
        )
        node_ids = {node.node_id for node in nodes}
        relations = tuple(
            KnowledgeRelation(
                relation_id=relationship.relationship_id,
                source_id=relationship.source_id,
                target_id=relationship.target_id,
                relation_type=relationship.relation_type,
                evidence_ids=relationship.evidence_ids,
                confidence=relationship.confidence,
            )
            for relationship in facts.relationships
            if (
                relationship.source_id in node_ids
                and relationship.target_id in node_ids
                and set(relationship.evidence_ids).issubset(evidence_ids)
            )
        )
        return KnowledgeGraph.create(nodes=nodes, relations=relations)


def serialize_public_artifact(value: Any) -> str:
    """Expose canonical serialization for source adapters and tests."""

    return canonical_json(to_jsonable(value))
