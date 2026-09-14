"""
JARVIS OS — Phase 47: Polymorphic Schema Semantics & Contract Compatibility
Core Models, Enums, Serialization, and Invariant Definitions.

Key Principles:
- Single Schema != Union Schema != Discriminated Union != Unknown Polymorphic Response.
- Variant != Contract unless formally validated.
- Explicit discriminators are prioritized over inferred structural discriminators.
- Ambiguous or overlapping variants without clear separation are classified as UNCERTAIN.
- A field can be required in Variant A, optional in Variant B, and forbidden in Variant C.
"""

from __future__ import annotations

import copy
from dataclasses import asdict, dataclass, field, field as dc_field
import enum
import hashlib
import json
import time
from typing import Any, Dict, List, Optional, Set, Tuple


class PolymorphicSchemaKind(str, enum.Enum):
    SINGLE_SCHEMA = "SINGLE_SCHEMA"
    UNION_SCHEMA = "UNION_SCHEMA"
    DISCRIMINATED_UNION = "DISCRIMINATED_UNION"
    UNKNOWN_POLYMORPHIC_RESPONSE = "UNKNOWN_POLYMORPHIC_RESPONSE"


class VariantStatus(str, enum.Enum):
    DETERMINISTIC = "DETERMINISTIC"
    INFERRED = "INFERRED"
    PROPOSED = "PROPOSED"
    VALIDATED = "VALIDATED"
    UNCERTAIN = "UNCERTAIN"


class DiscriminatorLocation(str, enum.Enum):
    BODY = "BODY"
    HEADER = "HEADER"
    QUERY = "QUERY"
    PATH = "PATH"
    NONE = "NONE"


class DiscriminatorType(str, enum.Enum):
    STRING_LITERAL = "STRING_LITERAL"
    STRING_ENUM = "STRING_ENUM"
    ENUM = "ENUM"
    FIELD_PRESENCE = "FIELD_PRESENCE"
    INFERRED_STRUCTURAL = "INFERRED_STRUCTURAL"
    STATUS_CODE = "STATUS_CODE"
    CONTENT_TYPE = "CONTENT_TYPE"
    NONE = "NONE"


class VariantDiffType(str, enum.Enum):
    VARIANT_ADDED = "VARIANT_ADDED"
    VARIANT_REMOVED = "VARIANT_REMOVED"
    VARIANT_MODIFIED = "VARIANT_MODIFIED"
    DISCRIMINATOR_ADDED = "DISCRIMINATOR_ADDED"
    DISCRIMINATOR_REMOVED = "DISCRIMINATOR_REMOVED"
    DISCRIMINATOR_CHANGED = "DISCRIMINATOR_CHANGED"
    COMMON_FIELD_CHANGED = "COMMON_FIELD_CHANGED"
    VARIANT_FIELD_CHANGED = "VARIANT_FIELD_CHANGED"
    VARIANT_REQUIREDNESS_CHANGED = "VARIANT_REQUIREDNESS_CHANGED"
    UNKNOWN_VARIATION = "UNKNOWN_VARIATION"


class CompatibilityVerdict(str, enum.Enum):
    COMPATIBLE = "COMPATIBLE"
    NON_BREAKING = "NON_BREAKING"
    POTENTIALLY_COMPATIBLE = "POTENTIALLY_COMPATIBLE"
    POTENTIALLY_BREAKING = "POTENTIALLY_BREAKING"
    INCOMPATIBLE = "INCOMPATIBLE"
    BREAKING = "BREAKING"
    UNCERTAIN = "UNCERTAIN"


class ConsumerVariantStance(str, enum.Enum):
    ALREADY_TOLERATES = "ALREADY_TOLERATES"
    EXPLICITLY_REJECTS = "EXPLICITLY_REJECTS"
    IGNORES = "IGNORES"
    UNCERTAIN = "UNCERTAIN"


@dataclass
class DiscriminatorDefinition:
    """Represents the property used to distinguish union variants."""

    field: str = ""
    location: DiscriminatorLocation = DiscriminatorLocation.BODY
    discriminator_type: DiscriminatorType = DiscriminatorType.STRING_LITERAL
    observed_values: List[Any] = dc_field(default_factory=list)
    mapping: Dict[str, str] = dc_field(default_factory=dict)  # discriminator_value -> variant_id
    confidence: float = 1.0
    is_inferred: bool = False
    is_explicit: bool = True
    type: Optional[DiscriminatorType] = None
    evidence_refs: List[str] = dc_field(default_factory=list)

    def __post_init__(self) -> None:
        if self.type is not None:
            self.discriminator_type = self.type
        else:
            self.type = self.discriminator_type

    def to_dict(self) -> Dict[str, Any]:
        return {
            "field": self.field,
            "location": self.location.value if hasattr(self.location, "value") else str(self.location),
            "discriminator_type": self.discriminator_type.value if hasattr(self.discriminator_type, "value") else str(self.discriminator_type),
            "observed_values": [str(v) for v in self.observed_values],
            "mapping": dict(self.mapping),
            "confidence": round(self.confidence, 4),
            "is_inferred": self.is_inferred,
            "evidence_refs": list(self.evidence_refs),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> DiscriminatorDefinition:
        loc = DiscriminatorLocation(data.get("location", "BODY")) if data.get("location") in DiscriminatorLocation._value2member_map_ else DiscriminatorLocation.BODY
        dt = DiscriminatorType(data.get("discriminator_type", "STRING_LITERAL")) if data.get("discriminator_type") in DiscriminatorType._value2member_map_ else DiscriminatorType.STRING_LITERAL
        return cls(
            field=str(data.get("field", "")),
            location=loc,
            discriminator_type=dt,
            observed_values=list(data.get("observed_values", [])),
            mapping=dict(data.get("mapping", {})),
            confidence=float(data.get("confidence", 1.0)),
            is_inferred=bool(data.get("is_inferred", False)),
            evidence_refs=list(data.get("evidence_refs", [])),
        )


@dataclass
class SchemaVariant:
    """Represents a discrete structural variant within a polymorphic union schema."""

    variant_id: str
    label: str
    schema: Dict[str, Any] = field(default_factory=dict)  # properties of this variant
    required_fields: List[str] = field(default_factory=list)
    optional_fields: List[str] = field(default_factory=list)
    forbidden_fields: List[str] = field(default_factory=list)  # fields that must not be present in this variant
    nullable_fields: List[str] = field(default_factory=list)
    discriminator_value: Optional[Any] = None
    evidence_refs: List[str] = field(default_factory=list)
    observed_count: int = 0
    confidence: float = 1.0
    status: VariantStatus = VariantStatus.DETERMINISTIC
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "variant_id": self.variant_id,
            "label": self.label,
            "schema": copy.deepcopy(self.schema),
            "required_fields": list(self.required_fields),
            "optional_fields": list(self.optional_fields),
            "forbidden_fields": list(self.forbidden_fields),
            "nullable_fields": list(self.nullable_fields),
            "discriminator_value": self.discriminator_value,
            "evidence_refs": list(self.evidence_refs),
            "observed_count": self.observed_count,
            "confidence": round(self.confidence, 4),
            "status": self.status.value if hasattr(self.status, "value") else str(self.status),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SchemaVariant:
        st = VariantStatus(data.get("status", "DETERMINISTIC")) if data.get("status") in VariantStatus._value2member_map_ else VariantStatus.DETERMINISTIC
        return cls(
            variant_id=str(data["variant_id"]),
            label=str(data.get("label", data["variant_id"])),
            schema=dict(data.get("schema", {})),
            required_fields=list(data.get("required_fields", [])),
            forbidden_fields=list(data.get("forbidden_fields", [])),
            discriminator_value=data.get("discriminator_value"),
            evidence_refs=list(data.get("evidence_refs", [])),
            observed_count=int(data.get("observed_count", 0)),
            confidence=float(data.get("confidence", 1.0)),
            status=st,
            metadata=dict(data.get("metadata", {})),
        )


@dataclass
class ErrorVariant:
    """Represents an expected error response variant tied to a specific HTTP status code."""

    status_code: int = 400
    error_type: str = "error"
    error_code: str = ""
    schema: Dict[str, Any] = field(default_factory=dict)
    required_fields: List[str] = field(default_factory=list)
    description: str = ""
    evidence_refs: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status_code": self.status_code,
            "error_type": self.error_type,
            "schema": copy.deepcopy(self.schema),
            "description": self.description,
            "evidence_refs": list(self.evidence_refs),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ErrorVariant:
        return cls(
            status_code=int(data.get("status_code", 400)),
            error_type=str(data.get("error_type", "error")),
            schema=dict(data.get("schema", {})),
            description=str(data.get("description", "")),
            evidence_refs=list(data.get("evidence_refs", [])),
        )


@dataclass
class PolymorphicSchema:
    """Formal representation of a contract containing union or discriminated variants."""

    schema_id: str
    contract_id: str = ""
    route: str = ""
    method: str = "GET"
    kind: PolymorphicSchemaKind = PolymorphicSchemaKind.UNION_SCHEMA
    variants: List[SchemaVariant] = field(default_factory=list)
    discriminator: Optional[DiscriminatorDefinition] = None
    discriminator_location: DiscriminatorLocation = DiscriminatorLocation.NONE
    discriminator_type: DiscriminatorType = DiscriminatorType.NONE
    common_fields: List[str] = field(default_factory=list)
    variant_fields: Any = field(default_factory=list)  # variant_id -> field_names OR list of all variant field names
    variant_required_fields: Dict[str, List[str]] = field(default_factory=dict)  # variant_id -> req_fields
    variant_constraints: Dict[str, Any] = field(default_factory=dict)
    error_variants: List[ErrorVariant] = field(default_factory=list)
    source: str = "RUNTIME_OBSERVATION"
    version: str = "1.0.0"
    status: VariantStatus = VariantStatus.DETERMINISTIC
    schema_hash: str = ""
    created_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.schema_hash:
            self.schema_hash = self.compute_hash()
        if self.discriminator:
            self.discriminator_location = self.discriminator.location
            self.discriminator_type = self.discriminator.discriminator_type

    def compute_hash(self) -> str:
        """Computes deterministic SHA-256 hash of all variants, common fields, and discriminator."""
        payload = {
            "schema_id": self.schema_id,
            "contract_id": self.contract_id,
            "kind": self.kind.value if hasattr(self.kind, "value") else str(self.kind),
            "common_fields": sorted(self.common_fields),
            "discriminator": self.discriminator.to_dict() if self.discriminator else None,
            "variants": [
                {
                    "variant_id": v.variant_id,
                    "discriminator_value": str(v.discriminator_value),
                    "required_fields": sorted(v.required_fields),
                    "forbidden_fields": sorted(v.forbidden_fields),
                    "schema": v.schema,
                }
                for v in sorted(self.variants, key=lambda x: x.variant_id)
            ],
            "error_variants": [
                {"status_code": ev.status_code, "error_type": ev.error_type}
                for ev in sorted(self.error_variants, key=lambda x: x.status_code)
            ],
        }
        encoded = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def get_variant(self, variant_id: str) -> Optional[SchemaVariant]:
        for v in self.variants:
            if v.variant_id == variant_id:
                return v
        return None

    def get_variant_by_id(self, variant_id: str) -> Optional[SchemaVariant]:
        return self.get_variant(variant_id)

    def get_variant_by_discriminator(self, disc_val: Any) -> Optional[SchemaVariant]:
        if disc_val is None:
            return None
        target_str = str(disc_val)
        for v in self.variants:
            if v.discriminator_value is not None and str(v.discriminator_value) == target_str:
                return v
        if self.discriminator and target_str in self.discriminator.mapping:
            v_id = self.discriminator.mapping[target_str]
            return self.get_variant(v_id)
        return None

    def resolve_variant_for_payload(self, payload: Dict[str, Any]) -> Tuple[Optional[SchemaVariant], float]:
        """Matches an incoming payload to a variant using discriminator or structural score."""
        if not isinstance(payload, dict):
            return None, 0.0

        # 1. Match by explicit discriminator
        if self.discriminator and self.discriminator.field:
            disc_val = payload.get(self.discriminator.field)
            if disc_val is not None:
                str_val = str(disc_val)
                target_variant_id = self.discriminator.mapping.get(str_val)
                if target_variant_id:
                    variant = self.get_variant(target_variant_id)
                    if variant:
                        return variant, 1.0

        # 2. Match by forbidden and required fields (structural signature)
        best_variant: Optional[SchemaVariant] = None
        best_score = -1.0

        payload_keys = set(payload.keys())

        for variant in self.variants:
            req_set = set(variant.required_fields)
            forbid_set = set(variant.forbidden_fields)

            # If payload has forbidden fields, this variant is disqualified
            if forbid_set.intersection(payload_keys):
                continue

            # Check coverage of required fields
            req_matched = len(req_set.intersection(payload_keys))
            total_req = len(req_set) if req_set else 1
            req_ratio = req_matched / total_req

            # Bonus for matching variant properties
            variant_props = set(variant.schema.get("properties", variant.schema).keys())
            matched_props = len(variant_props.intersection(payload_keys))
            total_props = len(variant_props) if variant_props else 1
            prop_ratio = matched_props / total_props

            composite_score = (req_ratio * 0.7) + (prop_ratio * 0.3)
            if composite_score > best_score:
                best_score = composite_score
                best_variant = variant

        if best_variant and best_score >= 0.75:
            return best_variant, best_score

        return None, best_score

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "contract_id": self.contract_id,
            "kind": self.kind.value if hasattr(self.kind, "value") else str(self.kind),
            "variants": [v.to_dict() for v in self.variants],
            "discriminator": self.discriminator.to_dict() if self.discriminator else None,
            "discriminator_location": self.discriminator_location.value if hasattr(self.discriminator_location, "value") else str(self.discriminator_location),
            "discriminator_type": self.discriminator_type.value if hasattr(self.discriminator_type, "value") else str(self.discriminator_type),
            "common_fields": list(self.common_fields),
            "variant_fields": copy.deepcopy(self.variant_fields),
            "variant_required_fields": copy.deepcopy(self.variant_required_fields),
            "variant_constraints": copy.deepcopy(self.variant_constraints),
            "error_variants": [ev.to_dict() for ev in self.error_variants],
            "source": self.source,
            "version": self.version,
            "status": self.status.value if hasattr(self.status, "value") else str(self.status),
            "schema_hash": self.schema_hash,
            "created_at": self.created_at,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> PolymorphicSchema:
        kd = PolymorphicSchemaKind(data.get("kind", "UNION_SCHEMA")) if data.get("kind") in PolymorphicSchemaKind._value2member_map_ else PolymorphicSchemaKind.UNION_SCHEMA
        st = VariantStatus(data.get("status", "DETERMINISTIC")) if data.get("status") in VariantStatus._value2member_map_ else VariantStatus.DETERMINISTIC
        loc = DiscriminatorLocation(data.get("discriminator_location", "NONE")) if data.get("discriminator_location") in DiscriminatorLocation._value2member_map_ else DiscriminatorLocation.NONE
        dt = DiscriminatorType(data.get("discriminator_type", "NONE")) if data.get("discriminator_type") in DiscriminatorType._value2member_map_ else DiscriminatorType.NONE
        
        disc = DiscriminatorDefinition.from_dict(data["discriminator"]) if data.get("discriminator") else None
        variants = [SchemaVariant.from_dict(v) for v in data.get("variants", [])]
        error_variants = [ErrorVariant.from_dict(ev) for ev in data.get("error_variants", [])]

        return cls(
            schema_id=str(data["schema_id"]),
            contract_id=str(data.get("contract_id", "")),
            kind=kd,
            variants=variants,
            discriminator=disc,
            discriminator_location=loc,
            discriminator_type=dt,
            common_fields=list(data.get("common_fields", [])),
            variant_fields=dict(data.get("variant_fields", {})),
            variant_required_fields=dict(data.get("variant_required_fields", {})),
            variant_constraints=dict(data.get("variant_constraints", {})),
            error_variants=error_variants,
            source=str(data.get("source", "RUNTIME_OBSERVATION")),
            version=str(data.get("version", "1.0.0")),
            status=st,
            schema_hash=str(data.get("schema_hash", "")),
            created_at=float(data.get("created_at", time.time())),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass
class VariantDiff:
    """Represents an atomic structural change in a polymorphic schema."""

    diff_type: VariantDiffType
    variant_id: str
    field_path: str
    classification: str  # NON_BREAKING, POTENTIALLY_BREAKING, BREAKING, UNCERTAIN
    old_value: Any = None
    new_value: Any = None
    description: str = ""
    is_breaking: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "diff_type": self.diff_type.value if hasattr(self.diff_type, "value") else str(self.diff_type),
            "variant_id": self.variant_id,
            "field_path": self.field_path,
            "classification": self.classification,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "description": self.description,
            "is_breaking": self.is_breaking,
        }


@dataclass
class SchemaCompatibilityMatrix:
    """Documents pairwise and overall version compatibility between polymorphic schemas."""

    old_schema_id: str
    new_schema_id: str
    overall_compatibility: CompatibilityVerdict
    variant_comparisons: List[Dict[str, Any]] = field(default_factory=list)
    breaking_reasons: List[str] = field(default_factory=list)
    confidence: float = 1.0

    @property
    def overall_verdict(self) -> CompatibilityVerdict:
        return self.overall_compatibility

    @property
    def pairwise_results(self) -> List[Dict[str, Any]]:
        return self.variant_comparisons

    def to_dict(self) -> Dict[str, Any]:
        return {
            "old_schema_id": self.old_schema_id,
            "new_schema_id": self.new_schema_id,
            "overall_compatibility": self.overall_compatibility.value if hasattr(self.overall_compatibility, "value") else str(self.overall_compatibility),
            "variant_comparisons": list(self.variant_comparisons),
            "breaking_reasons": list(self.breaking_reasons),
            "confidence": round(self.confidence, 4),
        }


@dataclass
class ConsumerVariantImpact:
    """Documents how an individual downstream consumer handles a specific polymorphic variant."""

    consumer_id: str
    consumer_type: str
    variant_id: str
    stance: ConsumerVariantStance
    explanation: str
    evidence_refs: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "consumer_id": self.consumer_id,
            "consumer_type": self.consumer_type,
            "variant_id": self.variant_id,
            "stance": self.stance.value if hasattr(self.stance, "value") else str(self.stance),
            "explanation": self.explanation,
            "evidence_refs": list(self.evidence_refs),
        }


@dataclass
class PolymorphicDriftReport:
    """Full drift analysis report for an endpoint with polymorphic semantics."""

    drift_id: str
    contract_id: str
    baseline_version: str
    observed_version: str
    diffs: List[VariantDiff] = field(default_factory=list)
    classification: str = "NON_BREAKING"
    has_drift: bool = True
    is_polymorphic_variation: bool = True
    drift_classification: str = "POLYMORPHIC_VARIANTS"
    new_variants: List[str] = field(default_factory=list)
    removed_variants: List[str] = field(default_factory=list)
    discriminator_drift: Optional[Dict[str, Any]] = None
    affected_consumers: List[ConsumerVariantImpact] = field(default_factory=list)
    recommended_action: str = "MONITOR"
    confidence: float = 1.0
    timestamp: float = field(default_factory=time.time)
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "drift_id": self.drift_id,
            "contract_id": self.contract_id,
            "baseline_version": self.baseline_version,
            "observed_version": self.observed_version,
            "diffs": [d.to_dict() for d in self.diffs],
            "classification": self.classification,
            "new_variants": list(self.new_variants),
            "removed_variants": list(self.removed_variants),
            "discriminator_drift": dict(self.discriminator_drift) if self.discriminator_drift else None,
            "affected_consumers": [c.to_dict() for c in self.affected_consumers],
            "recommended_action": self.recommended_action,
            "confidence": round(self.confidence, 4),
            "timestamp": self.timestamp,
            "notes": self.notes,
        }
