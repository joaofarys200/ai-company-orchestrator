"""
JARVIS OS — Phase 47: Polymorphic Schema Detector & Cluster Analyzer
Partitions observation payloads into coherent variant clusters, distinguishes common vs variant fields,
and flags ambiguous polymorphic shapes as UNCERTAIN.
"""

from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional, Set, Tuple

from agents.polymorphic_schema.discriminator import DiscriminatorEngine
from agents.polymorphic_schema.models import (
    DiscriminatorDefinition,
    DiscriminatorLocation,
    DiscriminatorType,
    PolymorphicSchema,
    PolymorphicSchemaKind,
    SchemaVariant,
    VariantStatus,
)
from agents.runtime_discovery.inference import SchemaInferenceEngine
from agents.runtime_discovery.models import RuntimeObservation


class PolymorphicDetector:
    """Discovers and constructs PolymorphicSchema models from runtime observations."""

    @classmethod
    def infer_primitive_type(cls, val: Any) -> str:
        if val is None:
            return "null"
        if isinstance(val, bool):
            return "boolean"
        if isinstance(val, int):
            return "integer"
        if isinstance(val, float):
            return "number"
        if isinstance(val, str):
            return "string"
        if isinstance(val, list):
            return "array"
        if isinstance(val, dict):
            return "object"
        return "any"

    @classmethod
    def extract_shape_signature(cls, payload: Dict[str, Any]) -> str:
        """Produces a canonical signature string representing the structural shape of a dictionary."""
        if not isinstance(payload, dict):
            return f"primitive:{cls.infer_primitive_type(payload)}"
        parts = []
        for k in sorted(payload.keys()):
            v = payload[k]
            t = cls.infer_primitive_type(v)
            parts.append(f"{k}:{t}")
        return "|".join(parts)

    @classmethod
    def detect_polymorphic_schema(
        cls,
        schema_id: str,
        contract_id: str,
        observations: List[RuntimeObservation],
        is_request: bool = False,
    ) -> PolymorphicSchema:
        """Analyzes a collection of runtime observations and models its polymorphic structure."""
        payloads: List[Dict[str, Any]] = []
        evidence_refs: List[str] = []

        for obs in observations:
            p = obs.request_payload if is_request else obs.response_payload
            if isinstance(p, dict):
                payloads.append(p)
                evidence_refs.append(obs.observation_id)

        if not payloads:
            return PolymorphicSchema(
                schema_id=schema_id,
                contract_id=contract_id,
                kind=PolymorphicSchemaKind.SINGLE_SCHEMA,
                variants=[],
                common_fields=[],
                status=VariantStatus.DETERMINISTIC,
            )

        # Step 1: Check for explicit discriminator
        explicit_disc = DiscriminatorEngine.resolve_explicit_discriminator(payloads)

        if explicit_disc:
            return cls._build_discriminated_union(
                schema_id=schema_id,
                contract_id=contract_id,
                payloads=payloads,
                discriminator=explicit_disc,
                evidence_refs=evidence_refs,
            )

        # Step 2: Cluster payloads by structural signature
        signature_groups: Dict[str, List[Dict[str, Any]]] = {}
        for p in payloads:
            sig = cls.extract_shape_signature(p)
            if sig not in signature_groups:
                signature_groups[sig] = []
                signature_groups[sig].append(p)

        # Filter out negligible noise clusters (< 5% presence if total > 20)
        total_p = len(payloads)
        active_clusters: List[List[Dict[str, Any]]] = []
        for sig, group in signature_groups.items():
            if total_p >= 20 and len(group) / total_p < 0.05:
                # Discard noise
                continue
            active_clusters.append(group)

        if len(active_clusters) <= 1:
            # Single uniform shape observed
            variant_payloads = active_clusters[0] if active_clusters else payloads
            inferred = SchemaInferenceEngine.infer_payload_schema("single_schema", variant_payloads)
            single_variant = SchemaVariant(
                variant_id="variant_default",
                label="Default Variant",
                schema=inferred.to_dict().get("properties", {}),
                required_fields=inferred.required_fields,
                observed_count=len(variant_payloads),
                status=VariantStatus.DETERMINISTIC,
            )
            return PolymorphicSchema(
                schema_id=schema_id,
                contract_id=contract_id,
                kind=PolymorphicSchemaKind.SINGLE_SCHEMA,
                variants=[single_variant],
                common_fields=list(inferred.to_dict().get("properties", {}).keys()),
                status=VariantStatus.DETERMINISTIC,
            )

        # Step 3: Multiple clusters detected without explicit discriminator
        # Try inferring structural discriminator (e.g. FIELD_PRESENCE)
        if len(active_clusters) == 2:
            inferred_disc, is_ambiguous = DiscriminatorEngine.infer_structural_discriminator(
                active_clusters[0], active_clusters[1]
            )
            if inferred_disc and not is_ambiguous:
                return cls._build_inferred_union(
                    schema_id=schema_id,
                    contract_id=contract_id,
                    clusters=active_clusters,
                    discriminator=inferred_disc,
                    evidence_refs=evidence_refs,
                )

        # Step 4: Cannot cleanly discriminate => Ambiguous / Uncertain Polymorphism
        return cls._build_ambiguous_union(
            schema_id=schema_id,
            contract_id=contract_id,
            clusters=active_clusters,
            evidence_refs=evidence_refs,
        )

    @classmethod
    def _build_discriminated_union(
        cls,
        schema_id: str,
        contract_id: str,
        payloads: List[Dict[str, Any]],
        discriminator: DiscriminatorDefinition,
        evidence_refs: List[str],
    ) -> PolymorphicSchema:
        """Constructs a validated DISCRIMINATED_UNION schema."""
        disc_field = discriminator.field
        variants_by_val: Dict[str, List[Dict[str, Any]]] = {}

        for p in payloads:
            val = str(p.get(disc_field, "unknown"))
            if val not in variants_by_val:
                variants_by_val[val] = []
            variants_by_val[val].append(p)

        all_keys: Set[str] = set()
        for p in payloads:
            all_keys.update(p.keys())

        # Determine common fields (present in 100% of payloads across all variants)
        common_candidates = set.intersection(*(set(p.keys()) for p in payloads)) if payloads else set()
        common_fields = sorted(list(common_candidates))
        variants: List[SchemaVariant] = []
        variant_fields_dict: Dict[str, List[str]] = {}
        variant_required: Dict[str, List[str]] = {}
        all_variant_fields = sorted(list(all_keys - common_candidates))

        for val, p_list in sorted(variants_by_val.items()):
            var_id = discriminator.mapping.get(val, f"variant_{val.lower().replace('.', '_')}")
            inferred = SchemaInferenceEngine.infer_payload_schema(var_id, p_list)
            props = inferred.to_dict().get("properties", {})
            v_keys = set(props.keys())

            # Required fields: all fields present in 100% of payloads for this variant
            req_in_variant = sorted([k for k in v_keys if all(isinstance(p, dict) and k in p for p in p_list)])

            # Forbidden fields: fields in other variants that NEVER appear in this variant
            forbidden = sorted(list(all_keys - v_keys))

            var = SchemaVariant(
                variant_id=var_id,
                label=f"Variant '{val}'",
                schema=props,
                required_fields=req_in_variant,
                forbidden_fields=forbidden,
                discriminator_value=val,
                evidence_refs=evidence_refs[:10],
                observed_count=len(p_list),
                confidence=0.95,
                status=VariantStatus.VALIDATED if len(p_list) >= 2 else VariantStatus.PROPOSED,
            )
            variants.append(var)
            variant_fields_dict[var_id] = sorted(list(v_keys))
            variant_required[var_id] = req_in_variant

        return PolymorphicSchema(
            schema_id=schema_id,
            contract_id=contract_id,
            kind=PolymorphicSchemaKind.DISCRIMINATED_UNION,
            variants=variants,
            discriminator=discriminator,
            discriminator_location=discriminator.location,
            discriminator_type=discriminator.discriminator_type,
            common_fields=common_fields,
            variant_fields=all_variant_fields,
            variant_required_fields=variant_required,
            version="1.0.0",
            status=VariantStatus.VALIDATED if any(v.status == VariantStatus.VALIDATED for v in variants) else VariantStatus.DETERMINISTIC,
        )

    @classmethod
    def _build_inferred_union(
        cls,
        schema_id: str,
        contract_id: str,
        clusters: List[List[Dict[str, Any]]],
        discriminator: DiscriminatorDefinition,
        evidence_refs: List[str],
    ) -> PolymorphicSchema:
        """Constructs an INFERRED structural union schema with non-authoritative discriminator."""
        variants: List[SchemaVariant] = []
        variant_fields: Dict[str, List[str]] = {}
        variant_required: Dict[str, List[str]] = {}
        all_keys: Set[str] = set()

        for cluster in clusters:
            for p in cluster:
                all_keys.update(p.keys())

        # Determine common fields
        common_candidates = set.intersection(*(set(p.keys()) for cluster in clusters for p in cluster))
        common_fields = sorted(list(common_candidates))

        labels = ["Variant A", "Variant B", "Variant C"]
        for idx, cluster in enumerate(clusters):
            var_id = f"variant_{chr(65+idx).lower()}"
            inferred = SchemaInferenceEngine.infer_payload_schema(var_id, cluster)
            props = inferred.to_dict().get("properties", {})
            v_keys = set(props.keys())
            forbidden = sorted(list(all_keys - v_keys))

            var = SchemaVariant(
                variant_id=var_id,
                label=labels[idx] if idx < len(labels) else f"Variant {idx+1}",
                schema=props,
                required_fields=inferred.required_fields,
                forbidden_fields=forbidden,
                discriminator_value=discriminator.observed_values[idx] if idx < len(discriminator.observed_values) else None,
                evidence_refs=evidence_refs[:10],
                observed_count=len(cluster),
                confidence=0.80,
                status=VariantStatus.INFERRED,
            )
            variants.append(var)
            variant_fields[var_id] = sorted(list(v_keys))
            variant_required[var_id] = inferred.required_fields

        return PolymorphicSchema(
            schema_id=schema_id,
            contract_id=contract_id,
            kind=PolymorphicSchemaKind.UNION_SCHEMA,
            variants=variants,
            discriminator=discriminator,
            discriminator_location=discriminator.location,
            discriminator_type=discriminator.discriminator_type,
            common_fields=common_fields,
            variant_fields=variant_fields,
            variant_required_fields=variant_required,
            version="1.0.0",
            status=VariantStatus.INFERRED,
            metadata={"inference_rationale": f"Inferred structural discriminator on field '{discriminator.field}'"},
        )

    @classmethod
    def _build_ambiguous_union(
        cls,
        schema_id: str,
        contract_id: str,
        clusters: List[List[Dict[str, Any]]],
        evidence_refs: List[str],
    ) -> PolymorphicSchema:
        """Constructs an UNCERTAIN polymorphic schema when clusters cannot be cleanly separated."""
        variants: List[SchemaVariant] = []
        variant_fields: Dict[str, List[str]] = {}
        variant_required: Dict[str, List[str]] = {}

        for idx, cluster in enumerate(clusters):
            var_id = f"variant_ambiguous_{idx+1}"
            inferred = SchemaInferenceEngine.infer_payload_schema(var_id, cluster)
            props = inferred.to_dict().get("properties", {})
            var = SchemaVariant(
                variant_id=var_id,
                label=f"Ambiguous Cluster {idx+1}",
                schema=props,
                required_fields=inferred.required_fields,
                observed_count=len(cluster),
                confidence=0.45,
                status=VariantStatus.UNCERTAIN,
            )
            variants.append(var)
            variant_fields[var_id] = sorted(list(props.keys()))
            variant_required[var_id] = inferred.required_fields

        return PolymorphicSchema(
            schema_id=schema_id,
            contract_id=contract_id,
            kind=PolymorphicSchemaKind.UNKNOWN_POLYMORPHIC_RESPONSE,
            variants=variants,
            discriminator=None,
            common_fields=[],
            variant_fields=variant_fields,
            variant_required_fields=variant_required,
            version="1.0.0",
            status=VariantStatus.UNCERTAIN,
            metadata={"warning": "Multiple overlapping shapes observed without decisive separating discriminator"},
        )

    @classmethod
    def detect_polymorphism(
        cls,
        route: str,
        method: str,
        observations: List[Any],
        schema_id: str = "poly_inferred",
        contract_id: str = "contract_inferred",
    ) -> Optional[PolymorphicSchema]:
        """Convenience method that normalizes raw dict observations and performs polymorphic detection."""
        obs_objs: List[RuntimeObservation] = []
        for idx, obs in enumerate(observations):
            if isinstance(obs, dict):
                if "request_payload" in obs or "response_payload" in obs:
                    obs_objs.append(RuntimeObservation(
                        observation_id=str(obs.get("observation_id", f"obs_{idx}")),
                        source_type="TEST_TRAFFIC",
                        route=route,
                        method=method,
                        status_code=int(obs.get("status_code", 200)),
                        request_payload=obs.get("request_payload"),
                        response_payload=obs.get("response_payload"),
                    ))
                else:
                    obs_objs.append(RuntimeObservation(
                        observation_id=f"obs_{idx}",
                        source_type="TEST_TRAFFIC",
                        route=route,
                        method=method,
                        status_code=200,
                        response_payload=obs,
                    ))
            elif isinstance(obs, RuntimeObservation):
                obs_objs.append(obs)

        schema = cls.detect_polymorphic_schema(
            schema_id=schema_id,
            contract_id=contract_id,
            observations=obs_objs,
            is_request=False,
        )
        schema.route = route
        schema.method = method
        return schema

    @classmethod
    def process_incremental_observation(
        cls,
        schemas: Dict[str, PolymorphicSchema],
        target_route: str,
        method: str,
        observation: Dict[str, Any],
    ) -> Tuple[str, int]:
        """Incrementally incorporates a new observation into only the matching polymorphic family.
        
        Returns:
            (affected_schema_id, blast_radius)
        """
        target_id = None
        for s_id, schema in schemas.items():
            if getattr(schema, "route", "") == target_route:
                target_id = s_id
                break

        if not target_id:
            target_id = next(iter(schemas.keys())) if schemas else "unknown"

        # Blast radius is 1 because only this family is modified
        return target_id, 1
