"""
JARVIS OS — Phase 45: Safe Schema Inference Engine
Infers OpenAPI/JSON-compatible schemas from runtime payload samples with strict statistical guarantees:
- Missing vs Null distinction.
- Required only with 100% sample presence over sufficient observations (>= 3); otherwise Optional.
- Finite values marked as ENUM_CANDIDATE, not definitive enums.
- Error status codes (4xx, 5xx) mapped to observed error schemas.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from agents.runtime_discovery.models import (
    ContractProposal,
    InferredSchema,
    ProposalStatus,
    RuntimeObservation,
)


class SchemaInferenceEngine:
    """Statistical, conservative schema inference engine."""

    MIN_SAMPLES_FOR_REQUIRED = 3
    MAX_DISTINCT_FOR_ENUM_CANDIDATE = 6

    @classmethod
    def infer_primitive_type(cls, val: Any) -> str:
        """Maps Python runtime primitive value to JSON Schema type."""
        if val is None:
            return "null"
        if isinstance(val, bool):
            return "boolean"
        if isinstance(val, int):
            return "integer"
        if isinstance(val, float):
            return "float"
        if isinstance(val, str):
            return "string"
        if isinstance(val, list):
            return "array"
        if isinstance(val, dict):
            return "object"
        return "any"

    @classmethod
    def infer_payload_schema(
        cls,
        schema_name: str,
        payloads: list[Any],
    ) -> InferredSchema:
        """Alias for infer_schema_from_payloads taking schema_name first."""
        return cls.infer_schema_from_payloads(payloads=payloads, schema_name=schema_name)

    @classmethod
    def infer_schema_from_payloads(
        cls,
        payloads: list[Any],
        min_samples_for_required: int = MIN_SAMPLES_FOR_REQUIRED,
        schema_name: str = "InferredSchema",
    ) -> InferredSchema:
        """Infers schema structure, required fields, nullability, and enum candidates from multiple payload samples."""
        if not payloads:
            return InferredSchema(schema_name=schema_name)

        sample_count = len(payloads)
        dict_payloads = [p for p in payloads if isinstance(p, dict)]
        if not dict_payloads:
            root_type = cls.infer_primitive_type(payloads[0]) if payloads else "any"
            return InferredSchema(
                schema_name=schema_name,
                properties={"_root": {"type": root_type}},
                required_fields=["_root"],
                sample_count=sample_count,
            )

        field_presence_count: dict[str, int] = {}
        field_types: dict[str, set[str]] = {}
        field_values: dict[str, set[str]] = {}
        nullable_fields: set[str] = set()

        for p in dict_payloads:
            for k, v in p.items():
                field_presence_count[k] = field_presence_count.get(k, 0) + 1
                t = cls.infer_primitive_type(v)
                if k not in field_types:
                    field_types[k] = set()
                field_types[k].add(t)

                if v is None:
                    nullable_fields.add(k)
                elif isinstance(v, (str, int, bool)):
                    if k not in field_values:
                        field_values[k] = set()
                    if len(field_values[k]) <= cls.MAX_DISTINCT_FOR_ENUM_CANDIDATE:
                        field_values[k].add(str(v))

        properties: dict[str, Any] = {}
        fields: dict[str, Any] = {}
        required_fields: list[str] = []
        enum_candidates: dict[str, list[str]] = {}

        for k, pres_cnt in field_presence_count.items():
            types_set = field_types.get(k, {"any"})
            types_without_null = types_set - {"null"}

            chosen_type = "string"
            if len(types_without_null) == 1:
                chosen_type = next(iter(types_without_null))
            elif "float" in types_without_null and "integer" in types_without_null:
                chosen_type = "float"
            elif len(types_without_null) > 1:
                chosen_type = "any"
            elif types_set == {"null"}:
                chosen_type = "null"

            is_nullable = k in nullable_fields
            presence_ratio = round(pres_cnt / sample_count, 4)
            is_required = (pres_cnt == sample_count and sample_count >= min_samples_for_required)

            if is_required:
                required_fields.append(k)

            # Enum candidate rule
            is_enum = False
            enum_vals: list[str] = []
            if chosen_type == "string" and sample_count >= 3:
                vals = field_values.get(k, set())
                if 2 <= len(vals) <= cls.MAX_DISTINCT_FOR_ENUM_CANDIDATE:
                    is_enum = True
                    enum_vals = sorted(list(vals))
                    enum_candidates[k] = enum_vals

            prop_def: dict[str, Any] = {
                "type": chosen_type,
                "presence_ratio": presence_ratio,
                "is_required": is_required,
                "is_nullable": is_nullable,
                "is_enum": is_enum,
                "is_enum_candidate": is_enum,
            }
            if is_nullable:
                prop_def["nullable"] = True
            if is_enum:
                prop_def["enum_candidate"] = enum_vals
                prop_def["enum_values"] = enum_vals

            properties[k] = prop_def
            fields[k] = prop_def

        return InferredSchema(
            schema_name=schema_name,
            properties=properties,
            fields=fields,
            required_fields=sorted(required_fields),
            nullable_fields=sorted(list(nullable_fields)),
            enum_candidates=enum_candidates,
            sample_count=sample_count,
        )

    def infer_response_schema(
        self,
        observations: list[Union[RuntimeObservation, dict[str, Any]]],
        schema_name: Optional[str] = None,
    ) -> InferredSchema:
        """Infers the response schema from a list of RuntimeObservation objects or raw response payloads."""
        if not observations:
            return InferredSchema(schema_name=schema_name or "AnonymousResponse")

        first = observations[0]
        detected_name = schema_name
        if not detected_name:
            if isinstance(first, RuntimeObservation):
                route_parts = [p for p in first.route.split("/") if p and not p.startswith("{")]
                if route_parts:
                    base = route_parts[-1].rstrip("s").capitalize()
                    detected_name = f"{base}Response" if not first.route.endswith("/me") else "UserResponse"
                else:
                    detected_name = "ResponseSchema"
            else:
                detected_name = "UserResponse"

        payloads: list[Any] = []
        for obs in observations:
            if isinstance(obs, RuntimeObservation):
                body = obs.response_payload if obs.response_payload is not None else obs.response_body
                if body is not None:
                    payloads.append(body)
            elif isinstance(obs, dict):
                payloads.append(obs)
            else:
                payloads.append(obs)

        return self.infer_schema_from_payloads(payloads, schema_name=detected_name or "ResponseSchema")

    def infer_error_contracts(
        self,
        observations: list[RuntimeObservation],
    ) -> list[dict[str, Any]]:
        """Extracts and aggregates observed 4xx/5xx error contracts."""
        obs_by_status: dict[int, list[Any]] = {}
        for obs in observations:
            if obs.status_code >= 400:
                st = obs.status_code
                if st not in obs_by_status:
                    obs_by_status[st] = []
                body = obs.response_payload if obs.response_payload is not None else obs.response_body
                if body is not None:
                    obs_by_status[st].append(body)

        result: list[dict[str, Any]] = []
        for status_code, err_payloads in sorted(obs_by_status.items()):
            shape = err_payloads[0] if err_payloads else {"detail": f"HTTP {status_code}"}
            result.append({
                "status_code": status_code,
                "sample_count": len(err_payloads),
                "error_shape": shape,
            })
        return result

    @classmethod
    def infer_from_observations(
        cls,
        observations: list[RuntimeObservation],
    ) -> tuple[InferredSchema, InferredSchema, dict[int, dict[str, Any]]]:
        """Infers request schema, response schema (2xx), and error contracts (4xx, 5xx) from observations."""
        req_payloads = [obs.request_payload for obs in observations if obs.request_payload is not None]
        res_success_payloads = [
            (obs.response_payload if obs.response_payload is not None else obs.response_body)
            for obs in observations
            if 200 <= obs.status_code < 300 and (obs.response_payload is not None or obs.response_body is not None)
        ]

        req_schema = cls.infer_schema_from_payloads(req_payloads)
        res_schema = cls.infer_schema_from_payloads(res_success_payloads)

        error_contracts: dict[int, dict[str, Any]] = {}
        error_observations = [obs for obs in observations if obs.status_code >= 400]
        obs_by_status: dict[int, list[Any]] = {}

        for err_obs in error_observations:
            st = err_obs.status_code
            if st not in obs_by_status:
                obs_by_status[st] = []
            body = err_obs.response_payload if err_obs.response_payload is not None else err_obs.response_body
            if body is not None:
                obs_by_status[st].append(body)

        for status_code, err_payloads in obs_by_status.items():
            err_schema = cls.infer_schema_from_payloads(err_payloads, min_samples_for_required=1)
            error_contracts[status_code] = {
                "status_code": status_code,
                "sample_count": len(err_payloads),
                "error_shape": err_payloads[0] if err_payloads else {},
                "schema": err_schema.to_dict(),
            }

        return req_schema, res_schema, error_contracts

    @classmethod
    def calculate_confidence(
        cls,
        sample_count: int,
        schema: Optional[InferredSchema] = None,
        has_variations: bool = False,
    ) -> float:
        """Calculates deterministic confidence score c in [0, 1] based on empirical sample size and stability."""
        if sample_count == 0:
            return 0.0

        if sample_count == 1:
            base = 0.40
        elif sample_count == 2:
            base = 0.60
        elif sample_count < 5:
            base = 0.75
        elif sample_count < 10:
            base = 0.88
        else:
            base = 0.95

        penalty = 0.0
        if schema:
            polymorphic_count = sum(
                1 for p in schema.properties.values() if isinstance(p, dict) and p.get("type") == "any"
            )
            penalty += min(0.25, polymorphic_count * 0.05)

        if has_variations:
            penalty += 0.15

        conf = max(0.10, min(0.99, base - penalty))
        return round(conf, 4)

    def create_contract_proposal(
        self,
        route: str,
        method: str,
        source: Any,
        observations: list[RuntimeObservation],
        inferred_response_schema: InferredSchema,
        inferred_request_schema: Optional[InferredSchema] = None,
    ) -> ContractProposal:
        """Synthesizes a ContractProposal from observations and inferred schemas."""
        sample_count = len(observations)
        confidence = self.calculate_confidence(sample_count, inferred_response_schema)
        errors = self.infer_error_contracts(observations)

        proposal_id = f"prop_{uuid.uuid4().hex[:8]}"

        return ContractProposal(
            proposal_id=proposal_id,
            source=source,
            route=route,
            method=method.upper(),
            observed_request_schema=inferred_request_schema.to_dict() if inferred_request_schema else {},
            observed_response_schema=inferred_response_schema.to_dict(),
            observed_errors=errors,
            proposed_contract={"route": route, "method": method.upper()},
            evidence_refs=[obs.observation_id for obs in observations],
            sample_count=sample_count,
            confidence=confidence,
            assumptions=["Observed traffic reflects stable endpoint behavior."],
            uncertainties=["Schema polymorphism may emerge with diverse inputs."] if sample_count < 5 else [],
            status=ProposalStatus.PROPOSED,
            contract_version="1.0.0-proposed",
            parent_version="UNVERSIONED_OBSERVED",
        )

    def update_proposal_incrementally(
        self,
        proposal: ContractProposal,
        new_observations: list[RuntimeObservation],
    ) -> ContractProposal:
        """Incrementally appends observations to proposal and refines fields without rebuilding all history."""
        proposal.sample_count += len(new_observations)
        for obs in new_observations:
            if obs.observation_id not in proposal.evidence_refs:
                proposal.evidence_refs.append(obs.observation_id)

        # Merge response payload fields
        existing_schema_dict = proposal.observed_response_schema
        fields = existing_schema_dict.get("fields", {})

        for obs in new_observations:
            body = obs.response_payload if obs.response_payload is not None else obs.response_body
            if isinstance(body, dict):
                for k, v in body.items():
                    if k not in fields:
                        fields[k] = {
                            "type": self.infer_primitive_type(v),
                            "is_required": False,
                            "is_nullable": v is None,
                            "presence_ratio": round(1 / proposal.sample_count, 4),
                        }
                    else:
                        if v is None:
                            fields[k]["is_nullable"] = True

        existing_schema_dict["fields"] = fields
        existing_schema_dict["sample_count"] = proposal.sample_count
        proposal.confidence = self.calculate_confidence(proposal.sample_count)
        return proposal
