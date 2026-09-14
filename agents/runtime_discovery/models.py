"""
JARVIS OS — Phase 45: Runtime Contract Discovery & Safe Schema Inference
Core Models, Enums, Serialization, and Invariant Definitions.

Principles:
- Strict separation: OBSERVED RUNTIME FACT != INFERRED CONTRACT != VERIFIED CONTRACT.
- Inferred contracts are proposals until validated.
- Sensitive credentials must be redacted at observation time.
- Missing != Null.
- A field is REQUIRED only with 100% presence in sufficient samples; otherwise OPTIONAL.
- Finite observed values are ENUM_CANDIDATE, not definitive enums.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import enum
import time
import uuid
from typing import Any, Dict, List, Optional, Set

from agents.semantic_graph.models import ApiSemanticContract, ConfidenceClass


class ObservationSourceType(str, enum.Enum):
    BROWSER_NETWORK = "BROWSER_NETWORK"
    BROWSER_NETWORK_LOGS = "BROWSER_NETWORK_LOGS"
    BACKEND_MIDDLEWARE = "BACKEND_MIDDLEWARE"
    BACKEND_HTTP_MIDDLEWARE = "BACKEND_HTTP_MIDDLEWARE"
    PROXY = "PROXY"
    LOCAL_DEV_PROXY = "LOCAL_DEV_PROXY"
    TEST_TRAFFIC = "TEST_TRAFFIC"
    TRACE_FILE = "TRACE_FILE"
    EXPLICIT_TRACE_FILES = "EXPLICIT_TRACE_FILES"


class ProposalStatus(str, enum.Enum):
    OBSERVED = "OBSERVED"
    INFERRED = "INFERRED"
    PROPOSED = "PROPOSED"
    VALIDATED = "VALIDATED"
    REJECTED = "REJECTED"
    STALE = "STALE"


class FieldDiffType(str, enum.Enum):
    ADDED_FIELD = "ADDED_FIELD"
    REMOVED_FIELD = "REMOVED_FIELD"
    TYPE_CHANGED = "TYPE_CHANGED"
    NULLABILITY_CHANGED = "NULLABILITY_CHANGED"
    REQUIRED_CHANGED = "REQUIRED_CHANGED"
    STATUS_CHANGED = "STATUS_CHANGED"
    ROUTE_CHANGED = "ROUTE_CHANGED"


class DiffSeverity(str, enum.Enum):
    NON_BREAKING = "NON_BREAKING"
    POTENTIALLY_BREAKING = "POTENTIALLY_BREAKING"
    BREAKING = "BREAKING"


class ConsistencyVerdict(str, enum.Enum):
    MATCH = "MATCH"
    EXTENSION = "EXTENSION"
    BREAKING_CHANGE = "BREAKING_CHANGE"
    CONFLICT = "CONFLICT"
    UNCERTAIN = "UNCERTAIN"


class DiscoveryPolicyAction(str, enum.Enum):
    AUTO_OBSERVE = "AUTO_OBSERVE"
    PROPOSE_CONTRACT = "PROPOSE_CONTRACT"
    REQUEST_HUMAN = "REQUEST_HUMAN"
    BLOCK = "BLOCK"


@dataclass
class RuntimeObservation:
    """An individual recorded network or server exchange, sanitized and redacted."""

    observation_id: str
    source_type: Any
    method: str
    route: str
    status_code: int
    request_headers: dict[str, str] = field(default_factory=dict)
    request_payload: Any = None
    response_payload: Any = None
    request_body: Any = None
    response_body: Any = None
    content_type: str = "application/json"
    response_time_ms: float = 0.0
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.request_payload is None and self.request_body is not None:
            self.request_payload = self.request_body
        elif self.request_body is None and self.request_payload is not None:
            self.request_body = self.request_payload

        if self.response_payload is None and self.response_body is not None:
            self.response_payload = self.response_body
        elif self.response_body is None and self.response_payload is not None:
            self.response_body = self.response_payload

    @property
    def redacted_items_count(self) -> int:
        return int(self.metadata.get("redactions_applied", 0))

    def to_dict(self) -> dict[str, Any]:
        return {
            "observation_id": self.observation_id,
            "source_type": self.source_type.value if isinstance(self.source_type, ObservationSourceType) else str(self.source_type),
            "method": self.method,
            "route": self.route,
            "status_code": self.status_code,
            "request_headers": self.request_headers,
            "request_payload": self.request_payload,
            "response_payload": self.response_payload,
            "content_type": self.content_type,
            "response_time_ms": self.response_time_ms,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RuntimeObservation:
        st = data.get("source_type", "BROWSER_NETWORK")
        source_type = ObservationSourceType(st) if st in ObservationSourceType._value2member_map_ else ObservationSourceType.BROWSER_NETWORK
        return cls(
            observation_id=str(data.get("observation_id", str(uuid.uuid4()))),
            source_type=source_type,
            method=str(data.get("method", "GET")).upper(),
            route=str(data.get("route", "/")),
            status_code=int(data.get("status_code", 200)),
            request_headers=dict(data.get("request_headers", {})),
            request_payload=data.get("request_payload"),
            response_payload=data.get("response_payload"),
            content_type=str(data.get("content_type", "application/json")),
            response_time_ms=float(data.get("response_time_ms", 0.0)),
            timestamp=float(data.get("timestamp", time.time())),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass
class FieldDifference:
    field_path: str
    diff_type: FieldDiffType
    severity: DiffSeverity
    old_value: Any = None
    new_value: Any = None
    message: str = ""
    description: str = ""

    def __post_init__(self) -> None:
        if not self.description and self.message:
            self.description = self.message
        elif not self.message and self.description:
            self.message = self.description

    def to_dict(self) -> dict[str, Any]:
        return {
            "field_path": self.field_path,
            "diff_type": self.diff_type.value if isinstance(self.diff_type, FieldDiffType) else str(self.diff_type),
            "old_value": self.old_value,
            "new_value": self.new_value,
            "severity": self.severity.value if isinstance(self.severity, DiffSeverity) else str(self.severity),
            "message": self.message or self.description,
            "description": self.description or self.message,
        }


@dataclass
class ContractDiff:
    diff_id: str = ""
    route: str = "/"
    method: str = "GET"
    changes: list[FieldDifference] = field(default_factory=list)
    differences: list[FieldDifference] = field(default_factory=list)
    severity: DiffSeverity = DiffSeverity.NON_BREAKING
    is_breaking: bool = False
    summary: str = ""

    def __post_init__(self) -> None:
        if not self.diff_id:
            self.diff_id = f"diff_{uuid.uuid4().hex[:8]}"
        if self.differences and not self.changes:
            self.changes = list(self.differences)
        elif self.changes and not self.differences:
            self.differences = list(self.changes)
        if any(d.severity == DiffSeverity.BREAKING for d in self.changes):
            self.severity = DiffSeverity.BREAKING
            self.is_breaking = True
        elif any(d.severity == DiffSeverity.POTENTIALLY_BREAKING for d in self.changes):
            if self.severity != DiffSeverity.BREAKING:
                self.severity = DiffSeverity.POTENTIALLY_BREAKING

    def to_dict(self) -> dict[str, Any]:
        return {
            "diff_id": self.diff_id,
            "route": self.route,
            "method": self.method,
            "changes": [c.to_dict() for c in self.changes],
            "differences": [c.to_dict() for c in self.changes],
            "severity": self.severity.value if isinstance(self.severity, DiffSeverity) else str(self.severity),
            "is_breaking": self.is_breaking,
            "summary": self.summary,
        }


@dataclass
class InferredSchema:
    """Detailed structural representation of an inferred schema with metadata."""

    schema_name: str = "InferredSchema"
    properties: dict[str, Any] = field(default_factory=dict)
    fields: dict[str, Any] = field(default_factory=dict)
    required_fields: list[str] = field(default_factory=list)
    nullable_fields: list[str] = field(default_factory=list)
    enum_candidates: dict[str, list[str]] = field(default_factory=dict)
    sample_count: int = 0
    error_contracts: dict[int, dict[str, Any]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Synchronize properties and fields
        if self.fields and not self.properties:
            # Build properties from fields
            props = {}
            for k, f in self.fields.items():
                if isinstance(f, dict):
                    props[k] = {"type": f.get("type", "string")}
                    if f.get("is_required"):
                        if k not in self.required_fields:
                            self.required_fields.append(k)
                    if f.get("is_nullable"):
                        if k not in self.nullable_fields:
                            self.nullable_fields.append(k)
                    if f.get("is_enum") or f.get("is_enum_candidate"):
                        self.enum_candidates[k] = f.get("enum_values", [])
            self.properties = props
        elif self.properties and not self.fields:
            self._sync_fields_from_properties()

    def _sync_fields_from_properties(self) -> None:
        f = {}
        for k, v in self.properties.items():
            t = v.get("type", "any") if isinstance(v, dict) else str(v)
            is_req = k in self.required_fields
            is_null = k in self.nullable_fields or (isinstance(v, dict) and v.get("nullable", False))
            is_enum = k in self.enum_candidates or (isinstance(v, dict) and "enum_candidate" in v)
            enums = self.enum_candidates.get(k, v.get("enum_candidate", [])) if isinstance(v, dict) else []
            pres = v.get("presence_ratio", 1.0 if is_req else 0.5) if isinstance(v, dict) else 1.0
            f[k] = {
                "type": t,
                "is_required": is_req,
                "is_nullable": is_null,
                "presence_ratio": pres,
                "is_enum_candidate": is_enum,
                "is_enum": is_enum,
                "enum_values": enums,
            }
        self.fields = f

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_name": self.schema_name,
            "properties": self.properties,
            "fields": self.fields,
            "required_fields": list(self.required_fields),
            "nullable_fields": list(self.nullable_fields),
            "enum_candidates": self.enum_candidates,
            "sample_count": self.sample_count,
            "error_contracts": {str(k): v for k, v in self.error_contracts.items()},
        }


@dataclass
class ContractProposal:
    """A formal contract hypothesis synthesized from empirical runtime evidence."""

    proposal_id: str
    source: Any
    route: str
    method: str
    observed_request_schema: dict[str, Any] = field(default_factory=dict)
    observed_response_schema: dict[str, Any] = field(default_factory=dict)
    observed_errors: list[dict[str, Any]] = field(default_factory=list)
    proposed_contract: Any = None
    evidence_refs: list[str] = field(default_factory=list)
    sample_count: int = 0
    confidence: float = 0.0
    assumptions: list[str] = field(default_factory=list)
    uncertainties: list[str] = field(default_factory=list)
    status: ProposalStatus = ProposalStatus.PROPOSED
    contract_version: str = "v1-proposed"
    parent_version: str = "UNVERSIONED_OBSERVED"
    created_at: Any = field(default_factory=time.time)
    reviewed_at: Optional[float] = None
    reviewer: str = ""
    reviewer_notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "source": self.source.value if isinstance(self.source, ObservationSourceType) else str(self.source),
            "route": self.route,
            "method": self.method,
            "observed_request_schema": self.observed_request_schema,
            "observed_response_schema": self.observed_response_schema,
            "observed_errors": self.observed_errors,
            "proposed_contract": self.proposed_contract.to_dict() if hasattr(self.proposed_contract, "to_dict") else self.proposed_contract,
            "evidence_refs": list(self.evidence_refs),
            "sample_count": self.sample_count,
            "confidence": round(self.confidence, 4),
            "assumptions": list(self.assumptions),
            "uncertainties": list(self.uncertainties),
            "status": self.status.value if isinstance(self.status, ProposalStatus) else str(self.status),
            "contract_version": self.contract_version,
            "parent_version": self.parent_version,
            "created_at": self.created_at,
            "reviewed_at": self.reviewed_at,
            "reviewer": self.reviewer,
            "reviewer_notes": self.reviewer_notes,
        }

