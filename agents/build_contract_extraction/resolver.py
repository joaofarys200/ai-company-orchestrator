"""
JARVIS OS — Phase 49: Dynamic Consumer Resolver
Binds dynamic patterns to canonical contracts using build-extracted types while strictly preserving UNCERTAIN without guessing.
"""

from __future__ import annotations

import uuid
from typing import Any, List, Optional, Tuple

from agents.build_contract_extraction.models import (
    ArtifactProvenance,
    DynamicConsumerPattern,
    DynamicConsumerResolution,
    EvidenceState,
    ExtractedContractBundle,
    PatternType,
    ResolutionStatus,
    UncertaintyReason,
)


class DynamicConsumerResolver:
    """
    Connects dynamic consumer access patterns to canonical contracts.
    Enforces the invariant: Never do silent guessing! Unbounded patterns remain UNCERTAIN (INDIRECT).
    """

    @classmethod
    def build_index(cls, bundle: ExtractedContractBundle) -> dict[str, Any]:
        """Builds an O(1) inverted index for literals to events, variants, and types."""
        literal_to_events: dict[str, list[tuple[str, Any]]] = {}
        for evt_id, evt in bundle.events.items():
            literal_to_events.setdefault(evt.topic_or_type, []).append((evt_id, evt))
            literal_to_events.setdefault(evt.discriminator_value, []).append((evt_id, evt))

        discriminator_to_variants: dict[str, list[tuple[str, Any]]] = {}
        literal_to_types: dict[str, list[tuple[str, Any]]] = {}
        for type_id, ctype in bundle.types.items():
            for var in ctype.variants:
                discriminator_to_variants.setdefault(var.discriminator_value, []).append((type_id, var))
            for prop in ctype.properties:
                literal_to_types.setdefault(prop, []).append((type_id, ctype))
            for enum_val in ctype.enum_values:
                literal_to_types.setdefault(str(enum_val), []).append((type_id, ctype))

        literal_to_endpoints: dict[str, list[tuple[str, Any]]] = {}
        for ep_id, ep in bundle.endpoints.items():
            literal_to_endpoints.setdefault(ep.path, []).append((ep_id, ep))
            literal_to_endpoints.setdefault(ep.endpoint_id, []).append((ep_id, ep))

        return {
            "events": literal_to_events,
            "variants": discriminator_to_variants,
            "types": literal_to_types,
            "endpoints": literal_to_endpoints,
        }

    @classmethod
    def resolve_pattern(
        cls,
        pattern: DynamicConsumerPattern,
        bundle: ExtractedContractBundle,
        consumer_name: Optional[str] = None,
        code_context: Optional[str] = None,
        index: Optional[dict[str, Any]] = None,
    ) -> DynamicConsumerResolution:
        """Resolves a single dynamic consumer pattern against the canonical contract bundle."""
        res_id = f"res_{uuid.uuid4().hex[:10]}"
        c_name = consumer_name or f"DynamicConsumer@{pattern.source_file}:{pattern.line_number}"
        c_id = f"consumer_{pattern.source_file.replace('/', '_').replace('.', '_')}_{pattern.line_number}"

        # Determine pattern matching style (closed vs open fallback)
        context = code_context or pattern.context_snippet
        has_default_fallback = (
            "default:" in context
            or "default :" in context
            or "case _:" in context
            or ".get(" in context
            or "??" in context
            or "||" in context
            or "fallback" in context.lower()
        )
        pattern_matching = "OPEN_WITH_FALLBACK" if has_default_fallback else "CLOSED_EXHAUSTIVE"

        # -------------------------------------------------------------
        # 1. Bounded Literal Matching (e.g. event unions, literal keys)
        # -------------------------------------------------------------
        if pattern.is_literal_or_bounded and pattern.bounded_literals:
            matched_contracts = []
            matched_variants = []
            matched_provenance: Optional[ArtifactProvenance] = None

            lookup_index = index or cls.build_index(bundle)

            for literal in pattern.bounded_literals:
                # Check events via index
                if literal in lookup_index["events"]:
                    for evt_id, evt in lookup_index["events"][literal]:
                        matched_contracts.append(evt_id)
                        matched_variants.append(literal)
                        if not matched_provenance and evt.provenance:
                            matched_provenance = evt.provenance

                # Check polymorphic variants across types via index
                if literal in lookup_index["variants"]:
                    for type_id, var in lookup_index["variants"][literal]:
                        matched_contracts.append(type_id)
                        matched_variants.append(var.variant_id)
                        if not matched_provenance and var.provenance:
                            matched_provenance = var.provenance

                # Check properties and enum values across types via index
                if literal in lookup_index["types"]:
                    for type_id, ctype in lookup_index["types"][literal]:
                        matched_contracts.append(type_id)
                        matched_variants.append(literal)
                        if not matched_provenance and ctype.provenance:
                            matched_provenance = ctype.provenance

                # Check endpoints via index
                if literal in lookup_index["endpoints"]:
                    for ep_id, ep in lookup_index["endpoints"][literal]:
                        matched_contracts.append(ep_id)
                        matched_variants.append(ep.path)
                        if not matched_provenance and ep.provenance:
                            matched_provenance = ep.provenance

            if matched_contracts:
                unique_contracts = list(dict.fromkeys(matched_contracts))
                primary_contract = unique_contracts[0]

                return DynamicConsumerResolution(
                    resolution_id=res_id,
                    consumer_id=c_id,
                    consumer_name=c_name,
                    pattern=pattern,
                    resolved_contract_id=primary_contract,
                    resolved_variant_ids=list(dict.fromkeys(matched_variants)),
                    evidence_state=EvidenceState.GENERATED,
                    resolution_status=ResolutionStatus.RESOLVED,
                    uncertainty_reason=UncertaintyReason.NO_REASON,
                    candidate_contracts=unique_contracts,
                    impact_reason=f"Dynamically accesses contract '{primary_contract}' bound by literals: {', '.join(pattern.bounded_literals)}",
                    required_action="Verify variant compatibility and payload structure" if pattern_matching == "CLOSED_EXHAUSTIVE" else "None",
                    pattern_matching=pattern_matching,
                    provenance=matched_provenance,
                )

        # -------------------------------------------------------------
        # 2. Heuristic Target Object Matching (e.g. userClient[action])
        # -------------------------------------------------------------
        target_obj = pattern.target_object_expr.lower()
        candidates: list[str] = []

        if len(bundle.endpoints) < 100:
            for ep_id, ep in bundle.endpoints.items():
                ep_clean = ep.path.replace("/", "_").strip("_").lower()
                if any(part in ep_clean for part in target_obj.split("_") if len(part) > 2):
                    candidates.append(ep_id)

        if len(bundle.events) < 100:
            for evt_id, evt in bundle.events.items():
                if any(part in evt.topic_or_type.lower() for part in target_obj.split("_") if len(part) > 2):
                    candidates.append(evt_id)

        # -------------------------------------------------------------
        # 3. Unbounded Dynamic Key -> PRESERVE UNCERTAIN (NO GUESSING!)
        # -------------------------------------------------------------
        if not pattern.is_literal_or_bounded:
            u_reason = (
                UncertaintyReason.DYNAMIC_KEY_NOT_BOUNDED
                if candidates
                else UncertaintyReason.DYNAMIC_KEY_NOT_RESOLVABLE
            )
            return DynamicConsumerResolution(
                resolution_id=res_id,
                consumer_id=c_id,
                consumer_name=c_name,
                pattern=pattern,
                resolved_contract_id=None,  # Invariant: Never select arbitrary first candidate!
                resolved_variant_ids=[],
                evidence_state=EvidenceState.UNCERTAIN,
                resolution_status=ResolutionStatus.UNCERTAIN,
                uncertainty_reason=u_reason,
                candidate_contracts=candidates,
                impact_reason=f"Unbounded dynamic key expression '{pattern.key_expression}' on object '{pattern.target_object_expr}' cannot be statically resolved without evidence.",
                required_action="Operator review or manual verification required.",
                pattern_matching=pattern_matching,
                provenance=None,
            )

        # Bounded but no contract matched
        return DynamicConsumerResolution(
            resolution_id=res_id,
            consumer_id=c_id,
            consumer_name=c_name,
            pattern=pattern,
            resolved_contract_id=None,
            resolved_variant_ids=[],
            evidence_state=EvidenceState.UNCERTAIN,
            resolution_status=ResolutionStatus.UNRESOLVED,
            uncertainty_reason=UncertaintyReason.MISSING_CONTRACT_SCHEMA,
            candidate_contracts=[],
            impact_reason=f"Literals {pattern.bounded_literals} have no matching contract schema in build artifacts.",
            required_action="Export or generate corresponding contract schema.",
            pattern_matching=pattern_matching,
            provenance=None,
        )

    @classmethod
    def resolve_multiple(
        cls,
        patterns: list[DynamicConsumerPattern],
        bundle: ExtractedContractBundle,
    ) -> list[DynamicConsumerResolution]:
        """Resolves a list of detected dynamic patterns using an inverted bundle index."""
        index = cls.build_index(bundle)
        resolutions = []
        for p in patterns:
            res = cls.resolve_pattern(p, bundle, index=index)
            resolutions.append(res)
        return resolutions

