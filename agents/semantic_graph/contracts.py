"""
JARVIS OS — Phase 44: Contract Registry & Schema Compatibility Engine

Provides formal contract management and cross-language schema translation.
Detects SCHEMA_CONFLICT (e.g. string expected by frontend vs object returned by backend)
and enforces contract versioning (COMPATIBLE, INCOMPATIBLE, REQUIRES_REVALIDATION).
Never declares equivalence merely because names match.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import enum
from typing import Any, Dict, List, Optional, Set, Tuple

from agents.semantic_graph.models import (
    ApiSemanticContract,
    ConfidenceClass,
    ConflictType,
    ContractVersionStatus,
    ValidationStatus,
)


# Canonical primitive type mappings across languages
TYPE_CANONICAL_MAP: dict[str, str] = {
    # TypeScript
    "string": "STRING",
    "number": "NUMBER",
    "boolean": "BOOLEAN",
    "array": "ARRAY",
    "object": "OBJECT",
    "null": "NULL",
    "undefined": "NULL",
    "void": "NULL",
    "any": "ANY",
    "unknown": "ANY",
    # Python
    "str": "STRING",
    "int": "NUMBER",
    "float": "NUMBER",
    "bool": "BOOLEAN",
    "list": "ARRAY",
    "dict": "OBJECT",
    "none": "NULL",
    "nonetype": "NULL",
    # JSON Schema / OpenAPI
    "integer": "NUMBER",
}


@dataclass
class SchemaFieldDiff:
    field_name: str
    frontend_type: str
    backend_type: str
    conflict_type: ConflictType
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "field_name": self.field_name,
            "frontend_type": self.frontend_type,
            "backend_type": self.backend_type,
            "conflict_type": self.conflict_type.value if isinstance(self.conflict_type, ConflictType) else str(self.conflict_type),
            "message": self.message,
        }


@dataclass
class SchemaCompatibilityReport:
    contract_id: str
    status: ValidationStatus
    version_status: ContractVersionStatus
    conflicts: list[SchemaFieldDiff] = field(default_factory=list)
    confidence: ConfidenceClass = ConfidenceClass.CONTRACTUAL
    details: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_id": self.contract_id,
            "status": self.status.value if isinstance(self.status, ValidationStatus) else str(self.status),
            "version_status": self.version_status.value if isinstance(self.version_status, ContractVersionStatus) else str(self.version_status),
            "conflicts": [c.to_dict() for c in self.conflicts],
            "confidence": self.confidence.value if isinstance(self.confidence, ConfidenceClass) else str(self.confidence),
            "details": self.details,
        }


class ContractRegistry:
    """Central authoritative registry of API Semantic Contracts and schema compatibility validators."""

    def __init__(self) -> None:
        self._contracts: dict[str, ApiSemanticContract] = {}
        self._route_index: dict[str, list[str]] = {}  # "GET /users" -> [contract_id, ...]
        self._proposals: dict[str, Any] = {}

    def register_contract(self, contract: ApiSemanticContract) -> None:
        """Registers or updates an ApiSemanticContract."""
        self._contracts[contract.contract_id] = contract
        key = f"{contract.method.upper()} {contract.route.strip()}"
        if key not in self._route_index:
            self._route_index[key] = []
        if contract.contract_id not in self._route_index[key]:
            self._route_index[key].append(contract.contract_id)

    def get_contract(self, contract_id: str) -> Optional[ApiSemanticContract]:
        return self._contracts.get(contract_id)

    def register_proposal(self, proposal: Any) -> None:
        """Stores an inferred ContractProposal with provenance."""
        self._proposals[proposal.proposal_id] = proposal

    def get_proposal(self, proposal_id: str) -> Optional[Any]:
        return self._proposals.get(proposal_id)

    def list_proposals(self) -> list[Any]:
        return list(self._proposals.values())

    def promote_proposal(
        self,
        proposal_id: str,
        verified_version: str = "v1-validated",
        operator_id: str = "human_operator",
        notes: str = "",
    ) -> Optional[ApiSemanticContract]:
        """Promotes a ContractProposal to a formal verified ApiSemanticContract."""
        proposal = self._proposals.get(proposal_id)
        if not proposal:
            return None
        contract = proposal.proposed_contract
        if contract:
            contract.version = verified_version
            self.register_contract(contract)
            proposal.status = "VALIDATED"
            proposal.reviewer = operator_id
            proposal.reviewer_notes = notes
        return contract

    def find_by_route(self, method: str, route: str, version: Optional[str] = None) -> list[ApiSemanticContract]:
        key = f"{method.upper()} {route.strip()}"
        c_ids = self._route_index.get(key, [])
        contracts = [self._contracts[cid] for cid in c_ids if cid in self._contracts]
        if version:
            contracts = [c for c in contracts if c.version == version]
        return contracts

    def list_contracts(self) -> list[ApiSemanticContract]:
        return list(self._contracts.values())

    @staticmethod
    def normalize_type_str(raw_type: str) -> str:
        """Normalizes a type string from TS, Python, or OpenAPI to canonical representation."""
        clean = (raw_type or "").strip().lower()
        if clean.startswith("list[") or clean.startswith("array<"):
            return "ARRAY"
        if clean.startswith("dict[") or clean.startswith("record<"):
            return "OBJECT"
        if clean.startswith("optional["):
            inner = clean[9:-1].strip()
            return TYPE_CANONICAL_MAP.get(inner, "ANY")
        return TYPE_CANONICAL_MAP.get(clean, clean.upper() if clean else "ANY")

    def check_compatibility(
        self,
        frontend_schema: dict[str, Any],
        backend_schema: dict[str, Any],
        contract_id: str = "custom",
    ) -> SchemaCompatibilityReport:
        """Compares frontend expected schema against backend produced schema for structural compatibility.
        
        Detects type mismatches, missing required fields, and structural deviations.
        """
        if not frontend_schema or not backend_schema:
            return SchemaCompatibilityReport(
                contract_id=contract_id,
                status=ValidationStatus.UNCERTAIN,
                version_status=ContractVersionStatus.REQUIRES_REVALIDATION,
                conflicts=[],
                confidence=ConfidenceClass.UNCERTAIN,
                details="Missing frontend or backend schema definition: marked UNCERTAIN",
            )

        conflicts: list[SchemaFieldDiff] = []

        fe_props: dict[str, Any] = frontend_schema.get("properties", {})
        be_props: dict[str, Any] = backend_schema.get("properties", {})

        # If properties not explicitly keyed, treat schema dict directly as field -> type mapping
        if not fe_props and any(isinstance(v, (str, dict)) for v in frontend_schema.values()):
            fe_props = frontend_schema
        if not be_props and any(isinstance(v, (str, dict)) for v in backend_schema.values()):
            be_props = backend_schema

        fe_required: set[str] = set(frontend_schema.get("required", []))
        be_required: set[str] = set(backend_schema.get("required", []))

        # Check all fields expected by frontend
        for field_name, fe_def in fe_props.items():
            if field_name in ("required", "properties", "type", "$schema"):
                continue

            fe_type_raw = fe_def if isinstance(fe_def, str) else fe_def.get("type", "any")
            fe_type_canon = self.normalize_type_str(str(fe_type_raw))

            if field_name not in be_props:
                # Backend does not provide a field expected by frontend
                is_req = field_name in fe_required
                conflicts.append(
                    SchemaFieldDiff(
                        field_name=field_name,
                        frontend_type=fe_type_canon,
                        backend_type="MISSING",
                        conflict_type=ConflictType.SCHEMA_CONFLICT,
                        message=f"Frontend expects field '{field_name}' ({fe_type_canon}) but backend schema does not provide it."
                        + (" (CRITICAL: Required field)" if is_req else " (Optional field)"),
                    )
                )
                continue

            be_def = be_props[field_name]
            be_type_raw = be_def if isinstance(be_def, str) else be_def.get("type", "any")
            be_type_canon = self.normalize_type_str(str(be_type_raw))

            # Compare canonical types
            if fe_type_canon != "ANY" and be_type_canon != "ANY" and fe_type_canon != be_type_canon:
                conflicts.append(
                    SchemaFieldDiff(
                        field_name=field_name,
                        frontend_type=fe_type_canon,
                        backend_type=be_type_canon,
                        conflict_type=ConflictType.SCHEMA_CONFLICT,
                        message=f"Schema conflict on '{field_name}': frontend expects {fe_type_canon}, but backend produces {be_type_canon}.",
                    )
                )

        if conflicts:
            return SchemaCompatibilityReport(
                contract_id=contract_id,
                status=ValidationStatus.INVALID,
                version_status=ContractVersionStatus.INCOMPATIBLE,
                conflicts=conflicts,
                confidence=ConfidenceClass.CONTRACTUAL,
                details=f"Detected {len(conflicts)} schema conflict(s) between frontend and backend contracts.",
            )

        return SchemaCompatibilityReport(
            contract_id=contract_id,
            status=ValidationStatus.VALID,
            version_status=ContractVersionStatus.COMPATIBLE,
            conflicts=[],
            confidence=ConfidenceClass.CONTRACTUAL,
            details="Frontend and backend schemas are 100% compatible under formal contract.",
        )

    def check_version_compatibility(
        self,
        v1_contract: ApiSemanticContract,
        v2_contract: ApiSemanticContract,
    ) -> tuple[ContractVersionStatus, list[str]]:
        """Evaluates evolution from v1 to v2 for backward compatibility."""
        reasons: list[str] = []

        if v1_contract.route != v2_contract.route:
            reasons.append(f"Route changed from '{v1_contract.route}' to '{v2_contract.route}'")
            return ContractVersionStatus.INCOMPATIBLE, reasons

        if v1_contract.method.upper() != v2_contract.method.upper():
            reasons.append(f"HTTP method changed from '{v1_contract.method}' to '{v2_contract.method}'")
            return ContractVersionStatus.INCOMPATIBLE, reasons

        # Compare responses
        report = self.check_compatibility(v1_contract.response_schema, v2_contract.response_schema, v2_contract.contract_id)
        if report.conflicts:
            for c in report.conflicts:
                reasons.append(c.message)
            return ContractVersionStatus.INCOMPATIBLE, reasons

        # Check if v2 added new fields (non-breaking, requires revalidation)
        v1_keys = set(v1_contract.response_schema.get("properties", v1_contract.response_schema).keys())
        v2_keys = set(v2_contract.response_schema.get("properties", v2_contract.response_schema).keys())
        new_keys = v2_keys - v1_keys
        if new_keys:
            reasons.append(f"New optional fields added in v2: {', '.join(sorted(new_keys))}")
            return ContractVersionStatus.REQUIRES_REVALIDATION, reasons

        return ContractVersionStatus.COMPATIBLE, ["Fully backward compatible"]
