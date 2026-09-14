"""
JARVIS OS — Phase 49: Build-Time Contract Extraction & Dynamic Consumer Resolution
Canonical Models, Evidence States, Provenance, and Dynamic Pattern DTOs.

Core Principles:
1. STATIC != GENERATED != RUNTIME_OBSERVED != INFERRED != UNCERTAIN != VERIFIED
2. Strict Evidence Priority: VERIFIED > RUNTIME_OBSERVED > GENERATED > STATIC > INFERRED > UNCERTAIN
3. Invariant: Never do silent guessing! Unresolved dynamic keys remain UNCERTAIN (INDIRECT).
4. Full provenance preserved on every extracted endpoint, type, field, and resolution.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import enum
import hashlib
import json
import time
import uuid
from typing import Any, Dict, List, Optional, Set, Tuple


class EvidenceState(str, enum.Enum):
    """Hierarchical evidence states for contract elements and consumer linkages."""
    STATIC = "STATIC"                      # Extracted from hand-written static source code
    GENERATED = "GENERATED"                # Extracted from compiler/build artifacts (OpenAPI, TS types, DTOs)
    RUNTIME_OBSERVED = "RUNTIME_OBSERVED"  # Empirically observed from network telemetry and responses
    INFERRED = "INFERRED"                  # Derived through structural heuristics (confidence capped)
    UNCERTAIN = "UNCERTAIN"                # Ambiguous or unbounded dynamic access without conclusive proof
    VERIFIED = "VERIFIED"                  # Formally validated via test execution and browser QA sign-off

    @classmethod
    def priority_rank(cls, state: "EvidenceState") -> int:
        """Returns numerical priority rank (higher = stronger authoritative evidence)."""
        ranks = {
            cls.VERIFIED: 60,
            cls.RUNTIME_OBSERVED: 50,
            cls.GENERATED: 40,
            cls.STATIC: 30,
            cls.INFERRED: 20,
            cls.UNCERTAIN: 10,
        }
        return ranks.get(state, 0)

    def is_authoritative(self) -> bool:
        return self in (EvidenceState.VERIFIED, EvidenceState.RUNTIME_OBSERVED, EvidenceState.GENERATED)


class TypeKind(str, enum.Enum):
    SCALAR = "SCALAR"
    OBJECT = "OBJECT"
    UNION = "UNION"
    ENUM = "ENUM"
    ARRAY = "ARRAY"
    ANY = "ANY"


class SourceType(str, enum.Enum):
    GENERATED_OPENAPI = "GENERATED_OPENAPI"
    JSONSCHEMA = "JSONSCHEMA"
    GENERATED_TYPESCRIPT = "GENERATED_TYPESCRIPT"
    PYTHON_MODEL = "PYTHON_MODEL"
    EVENT_SCHEMA = "EVENT_SCHEMA"
    STATIC_CODE = "STATIC_CODE"
    RUNTIME = "RUNTIME"


class PatternType(str, enum.Enum):
    DYNAMIC_GETATTR = "DYNAMIC_GETATTR"        # Python getattr(obj, key)
    DYNAMIC_INDEX = "DYNAMIC_INDEX"            # JS/TS/Py obj[key]
    REGISTRY_LOOKUP = "REGISTRY_LOOKUP"        # registry[eventName]
    DISPATCH_TABLE = "DISPATCH_TABLE"          # handlers[type]
    METHOD_DISPATCH = "METHOD_DISPATCH"        # service[method](payload)
    ROUTE_SELECTION = "ROUTE_SELECTION"        # router.resolve(dynamicPath)
    CONFIG_DRIVEN = "CONFIG_DRIVEN"            # Consumers configured via JSON/YAML mapping
    REFLECTION_LIKE = "REFLECTION_LIKE"        # Metaprogramming / inspection


class ResolutionStatus(str, enum.Enum):
    RESOLVED = "RESOLVED"
    PARTIALLY_RESOLVED = "PARTIALLY_RESOLVED"
    UNCERTAIN = "UNCERTAIN"
    UNRESOLVED = "UNRESOLVED"
    CONFLICT = "CONFLICT"


class UncertaintyReason(str, enum.Enum):
    NO_REASON = "NO_REASON"
    DYNAMIC_KEY_NOT_RESOLVABLE = "DYNAMIC_KEY_NOT_RESOLVABLE"
    DYNAMIC_KEY_NOT_BOUNDED = "DYNAMIC_KEY_NOT_BOUNDED"
    MULTIPLE_AMBIGUOUS_CANDIDATES = "MULTIPLE_AMBIGUOUS_CANDIDATES"
    MISSING_CONTRACT_SCHEMA = "MISSING_CONTRACT_SCHEMA"
    OPAQUE_RUNTIME_EXPRESSION = "OPAQUE_RUNTIME_EXPRESSION"
    SECURITY_SENSITIVE_ACCESS = "SECURITY_SENSITIVE_ACCESS"


@dataclass
class ArtifactProvenance:
    """Immutable audit provenance for any extracted or resolved contract entity."""
    source_type: SourceType
    artifact_path: str
    json_pointer: str = ""
    content_hash: str = ""
    extracted_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_type": self.source_type.value,
            "artifact_path": self.artifact_path,
            "json_pointer": self.json_pointer,
            "content_hash": self.content_hash,
            "extracted_at": self.extracted_at,
        }


@dataclass
class ContractField:
    """Canonical model of a schema field."""
    field_name: str
    field_type: str
    required: bool = True
    nullable: bool = False
    default_value: Any = None
    description: str = ""
    provenance: Optional[ArtifactProvenance] = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        if self.provenance:
            d["provenance"] = self.provenance.to_dict()
        return d


@dataclass
class ContractVariant:
    """Canonical polymorphic variant model."""
    variant_id: str
    discriminator_value: str
    schema: dict[str, Any]
    required_fields: list[str] = field(default_factory=list)
    forbidden_fields: list[str] = field(default_factory=list)
    description: str = ""
    provenance: Optional[ArtifactProvenance] = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        if self.provenance:
            d["provenance"] = self.provenance.to_dict()
        return d


@dataclass
class ContractDiscriminator:
    """Canonical discriminator definition for polymorphic unions."""
    field: str
    location: str = "BODY"  # BODY, HEADER, QUERY
    mapping: dict[str, str] = field(default_factory=dict)
    discriminator_type: str = "STRING_ENUM"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ContractType:
    """Language-agnostic canonical type representation."""
    type_id: str
    name: str
    kind: TypeKind
    properties: dict[str, ContractField] = field(default_factory=dict)
    variants: list[ContractVariant] = field(default_factory=list)
    discriminator: Optional[ContractDiscriminator] = None
    enum_values: list[Any] = field(default_factory=list)
    language: str = "agnostic"
    provenance: Optional[ArtifactProvenance] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "type_id": self.type_id,
            "name": self.name,
            "kind": self.kind.value,
            "properties": {k: v.to_dict() for k, v in self.properties.items()},
            "variants": [v.to_dict() for v in self.variants],
            "discriminator": self.discriminator.to_dict() if self.discriminator else None,
            "enum_values": self.enum_values,
            "language": self.language,
            "provenance": self.provenance.to_dict() if self.provenance else None,
        }


@dataclass
class ContractAuth:
    """Authentication and authorization metadata on contracts."""
    requires_auth: bool = True
    auth_scheme: str = "Bearer"
    roles: list[str] = field(default_factory=list)
    scopes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ContractEndpoint:
    """Canonical representation of an API Endpoint."""
    endpoint_id: str
    path: str
    method: str
    request_schema: Optional[dict[str, Any]] = None
    response_schema: Optional[dict[str, Any]] = None
    parameters: list[dict[str, Any]] = field(default_factory=list)
    auth: ContractAuth = field(default_factory=ContractAuth)
    version: str = "1.0.0"
    provenance: Optional[ArtifactProvenance] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "endpoint_id": self.endpoint_id,
            "path": self.path,
            "method": self.method.upper(),
            "request_schema": self.request_schema,
            "response_schema": self.response_schema,
            "parameters": self.parameters,
            "auth": self.auth.to_dict(),
            "version": self.version,
            "provenance": self.provenance.to_dict() if self.provenance else None,
        }


@dataclass
class ContractEvent:
    """Canonical representation of an Event or Message Contract."""
    event_id: str
    topic_or_type: str
    discriminator_value: str
    payload_schema: dict[str, Any]
    version: str = "1.0.0"
    provenance: Optional[ArtifactProvenance] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "topic_or_type": self.topic_or_type,
            "discriminator_value": self.discriminator_value,
            "payload_schema": self.payload_schema,
            "version": self.version,
            "provenance": self.provenance.to_dict() if self.provenance else None,
        }


@dataclass
class ContractVersion:
    """Immutable version node for tracking contract evolution."""
    contract_id: str
    version: str
    content_hash: str
    status: str = "VALIDATED"
    source_type: SourceType = SourceType.GENERATED_OPENAPI
    parent_version: Optional[str] = None
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_id": self.contract_id,
            "version": self.version,
            "content_hash": self.content_hash,
            "status": self.status,
            "source_type": self.source_type.value,
            "parent_version": self.parent_version,
            "created_at": self.created_at,
        }


@dataclass
class DynamicConsumerPattern:
    """Detected pattern of dynamic access or reflection in source code."""
    pattern_id: str
    pattern_type: PatternType
    source_file: str
    line_number: int
    target_object_expr: str
    key_expression: str
    is_literal_or_bounded: bool = False
    bounded_literals: list[str] = field(default_factory=list)
    context_snippet: str = ""
    language: str = "TypeScript"

    def to_dict(self) -> dict[str, Any]:
        return {
            "pattern_id": self.pattern_id,
            "pattern_type": self.pattern_type.value,
            "source_file": self.source_file,
            "line_number": self.line_number,
            "target_object_expr": self.target_object_expr,
            "key_expression": self.key_expression,
            "is_literal_or_bounded": self.is_literal_or_bounded,
            "bounded_literals": self.bounded_literals,
            "context_snippet": self.context_snippet,
            "language": self.language,
        }


@dataclass
class DynamicConsumerResolution:
    """Formal audit record of resolving a dynamic consumer against build-time contracts."""
    resolution_id: str
    consumer_id: str
    consumer_name: str
    pattern: DynamicConsumerPattern
    resolved_contract_id: Optional[str] = None
    resolved_variant_ids: list[str] = field(default_factory=list)
    evidence_state: EvidenceState = EvidenceState.UNCERTAIN
    resolution_status: ResolutionStatus = ResolutionStatus.UNCERTAIN
    uncertainty_reason: UncertaintyReason = UncertaintyReason.NO_REASON
    candidate_contracts: list[str] = field(default_factory=list)
    impact_reason: str = ""
    required_action: str = ""
    pattern_matching: str = "CLOSED_EXHAUSTIVE"  # CLOSED_EXHAUSTIVE vs OPEN_WITH_FALLBACK
    provenance: Optional[ArtifactProvenance] = None
    resolved_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "resolution_id": self.resolution_id,
            "consumer_id": self.consumer_id,
            "consumer_name": self.consumer_name,
            "pattern": self.pattern.to_dict(),
            "resolved_contract_id": self.resolved_contract_id,
            "resolved_variant_ids": self.resolved_variant_ids,
            "evidence_state": self.evidence_state.value,
            "resolution_status": self.resolution_status.value,
            "uncertainty_reason": self.uncertainty_reason.value,
            "candidate_contracts": self.candidate_contracts,
            "impact_reason": self.impact_reason,
            "required_action": self.required_action,
            "pattern_matching": self.pattern_matching,
            "provenance": self.provenance.to_dict() if self.provenance else None,
            "resolved_at": self.resolved_at,
        }


@dataclass
class ExtractedContractBundle:
    """Unified bundle of build-extracted contracts, types, events, and dynamic resolutions."""
    bundle_id: str = field(default_factory=lambda: f"bundle_{uuid.uuid4().hex[:10]}")
    endpoints: dict[str, ContractEndpoint] = field(default_factory=dict)
    types: dict[str, ContractType] = field(default_factory=dict)
    events: dict[str, ContractEvent] = field(default_factory=dict)
    versions: dict[str, ContractVersion] = field(default_factory=dict)
    dynamic_resolutions: list[DynamicConsumerResolution] = field(default_factory=list)
    extracted_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "bundle_id": self.bundle_id,
            "endpoints": {k: v.to_dict() for k, v in self.endpoints.items()},
            "types": {k: v.to_dict() for k, v in self.types.items()},
            "events": {k: v.to_dict() for k, v in self.events.items()},
            "versions": {k: v.to_dict() for k, v in self.versions.items()},
            "dynamic_resolutions": [r.to_dict() for r in self.dynamic_resolutions],
            "extracted_at": self.extracted_at,
        }
