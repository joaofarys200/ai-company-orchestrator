"""
JARVIS OS — Phase 47: Polymorphic Schema Compatibility Engine
Evaluates backwards and forwards compatibility between polymorphic schema versions,
building variant-by-variant compatibility matrices and deterministic breakage classifications.
"""

from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional, Set, Tuple

from agents.polymorphic_schema.models import (
    CompatibilityVerdict,
    PolymorphicSchema,
    PolymorphicSchemaKind,
    SchemaCompatibilityMatrix,
    SchemaVariant,
)


class PolymorphicCompatibilityEngine:
    """Evaluates compatibility between two polymorphic schema specifications."""

    @classmethod
    def compute_matrix(
        cls,
        old_schema: PolymorphicSchema,
        new_schema: PolymorphicSchema,
        is_request: bool = False,
    ) -> SchemaCompatibilityMatrix:
        """Alias for evaluate_compatibility."""
        return cls.evaluate_compatibility(old_schema, new_schema, is_request)

    @classmethod
    def check_variant_compatibility(
        cls,
        old_variant: SchemaVariant,
        new_variant: SchemaVariant,
    ) -> Tuple[CompatibilityVerdict, List[str]]:
        """Pairwise structural comparison of two SchemaVariant instances."""
        # 1. Discriminator value mismatch
        if old_variant.discriminator_value is not None and new_variant.discriminator_value is not None:
            if str(old_variant.discriminator_value) != str(new_variant.discriminator_value):
                return CompatibilityVerdict.INCOMPATIBLE, [
                    f"Discriminator value mismatch: '{old_variant.discriminator_value}' != '{new_variant.discriminator_value}'"
                ]

        # 2. Check removed required fields
        old_req = set(old_variant.required_fields)
        new_req = set(new_variant.required_fields)
        removed_req = old_req - new_req
        if removed_req:
            return CompatibilityVerdict.BREAKING, [
                f"Required fields removed in variant: {sorted(removed_req)}"
            ]

        # 3. Check new forbidden fields that conflict with old required
        new_forbid = set(new_variant.forbidden_fields)
        if new_forbid.intersection(old_req):
            return CompatibilityVerdict.BREAKING, [
                f"Fields previously required now forbidden: {sorted(new_forbid.intersection(old_req))}"
            ]

        # 4. Added required fields (potentially breaking if caller doesn't provide them)
        added_req = new_req - old_req
        if added_req:
            return CompatibilityVerdict.POTENTIALLY_BREAKING, [
                f"New required fields added to variant: {sorted(added_req)}"
            ]

        return CompatibilityVerdict.COMPATIBLE, []

    @classmethod
    def evaluate_compatibility(
        cls,
        old_schema: PolymorphicSchema,
        new_schema: PolymorphicSchema,
        is_request: bool = False,
    ) -> SchemaCompatibilityMatrix:
        """Evaluates pairwise variant compatibility and overall version compatibility."""
        variant_comparisons: List[Dict[str, Any]] = []
        breaking_reasons: List[str] = []

        old_variants = {v.variant_id: v for v in old_schema.variants}
        new_variants = {v.variant_id: v for v in new_schema.variants}

        # 1. Check Discriminator Compatibility
        cls._evaluate_discriminator_compatibility(
            old_schema, new_schema, breaking_reasons, variant_comparisons
        )

        # 2. Check Common Fields Compatibility
        cls._evaluate_common_fields_compatibility(
            old_schema, new_schema, breaking_reasons, variant_comparisons, is_request
        )

        # 3. Check Removed Variants (Old variants missing in New)
        removed_variants = set(old_variants.keys()) - set(new_variants.keys())
        for r_id in sorted(removed_variants):
            reason = f"Variant '{r_id}' was removed in new schema version"
            breaking_reasons.append(reason)
            variant_comparisons.append({
                "comparison_type": "VARIANT_REMOVED",
                "variant_id": r_id,
                "verdict": CompatibilityVerdict.INCOMPATIBLE.value,
                "reason": reason,
                "is_breaking": True,
            })

        # 4. Check Added Variants (New variants not in Old)
        added_variants = set(new_variants.keys()) - set(old_variants.keys())
        for a_id in sorted(added_variants):
            if is_request:
                # Request variant added is generally non-breaking (server accepts more shapes)
                verdict = CompatibilityVerdict.COMPATIBLE
                reason = f"New request variant '{a_id}' added (backwards compatible)"
                is_brk = False
            else:
                # Response variant added is potentially breaking for intolerant consumers
                verdict = CompatibilityVerdict.POTENTIALLY_COMPATIBLE
                reason = f"New response variant '{a_id}' introduced into union"
                is_brk = False

            variant_comparisons.append({
                "comparison_type": "VARIANT_ADDED",
                "variant_id": a_id,
                "verdict": verdict.value,
                "reason": reason,
                "is_breaking": is_brk,
            })

        # 5. Check Preserved Variants (Pairwise comparison)
        common_var_ids = set(old_variants.keys()).intersection(set(new_variants.keys()))
        for v_id in sorted(common_var_ids):
            old_v = old_variants[v_id]
            new_v = new_variants[v_id]
            cls._compare_individual_variants(
                old_v, new_v, breaking_reasons, variant_comparisons, is_request
            )

        # 6. Synthesize Overall Verdict
        if any(c.get("is_breaking") for c in variant_comparisons):
            overall = CompatibilityVerdict.INCOMPATIBLE
        elif any(c.get("verdict") == CompatibilityVerdict.POTENTIALLY_COMPATIBLE.value for c in variant_comparisons):
            overall = CompatibilityVerdict.POTENTIALLY_COMPATIBLE
        elif old_schema.status.value == "UNCERTAIN" or new_schema.status.value == "UNCERTAIN":
            overall = CompatibilityVerdict.UNCERTAIN
        else:
            overall = CompatibilityVerdict.COMPATIBLE

        confidence = 0.95 if overall != CompatibilityVerdict.UNCERTAIN else 0.50

        return SchemaCompatibilityMatrix(
            old_schema_id=old_schema.schema_id,
            new_schema_id=new_schema.schema_id,
            overall_compatibility=overall,
            variant_comparisons=variant_comparisons,
            breaking_reasons=breaking_reasons,
            confidence=confidence,
        )

    @classmethod
    def _evaluate_discriminator_compatibility(
        cls,
        old_s: PolymorphicSchema,
        new_s: PolymorphicSchema,
        breaking_reasons: List[str],
        comparisons: List[Dict[str, Any]],
    ) -> None:
        old_d = old_s.discriminator
        new_d = new_s.discriminator

        if old_d and not new_d:
            reason = f"Discriminator '{old_d.field}' removed in new schema version"
            breaking_reasons.append(reason)
            comparisons.append({
                "comparison_type": "DISCRIMINATOR_REMOVED",
                "verdict": CompatibilityVerdict.INCOMPATIBLE.value,
                "reason": reason,
                "is_breaking": True,
            })
        elif old_d and new_d:
            if old_d.field != new_d.field:
                reason = f"Discriminator field changed from '{old_d.field}' to '{new_d.field}'"
                breaking_reasons.append(reason)
                comparisons.append({
                    "comparison_type": "DISCRIMINATOR_CHANGED",
                    "verdict": CompatibilityVerdict.INCOMPATIBLE.value,
                    "reason": reason,
                    "is_breaking": True,
                })
            elif old_d.location != new_d.location:
                reason = f"Discriminator location changed from '{old_d.location.value}' to '{new_d.location.value}'"
                breaking_reasons.append(reason)
                comparisons.append({
                    "comparison_type": "DISCRIMINATOR_CHANGED",
                    "verdict": CompatibilityVerdict.INCOMPATIBLE.value,
                    "reason": reason,
                    "is_breaking": True,
                })

    @classmethod
    def _evaluate_common_fields_compatibility(
        cls,
        old_s: PolymorphicSchema,
        new_s: PolymorphicSchema,
        breaking_reasons: List[str],
        comparisons: List[Dict[str, Any]],
        is_request: bool,
    ) -> None:
        removed_common = set(old_s.common_fields) - set(new_s.common_fields)
        for cf in sorted(removed_common):
            if not is_request:
                reason = f"Common response field '{cf}' removed across variants"
                breaking_reasons.append(reason)
                comparisons.append({
                    "comparison_type": "COMMON_FIELD_REMOVED",
                    "field": cf,
                    "verdict": CompatibilityVerdict.INCOMPATIBLE.value,
                    "reason": reason,
                    "is_breaking": True,
                })

    @classmethod
    def _compare_individual_variants(
        cls,
        old_v: SchemaVariant,
        new_v: SchemaVariant,
        breaking_reasons: List[str],
        comparisons: List[Dict[str, Any]],
        is_request: bool,
    ) -> None:
        old_props = old_v.schema.get("properties", old_v.schema)
        new_props = new_v.schema.get("properties", new_v.schema)

        old_req = set(old_v.required_fields)
        new_req = set(new_v.required_fields)

        is_var_breaking = False
        var_reasons: List[str] = []

        # 1. Removed field from variant
        removed_fields = set(old_props.keys()) - set(new_props.keys())
        for rf in sorted(removed_fields):
            if not is_request:
                is_var_breaking = True
                msg = f"Field '{rf}' removed from variant '{old_v.variant_id}'"
                var_reasons.append(msg)
                breaking_reasons.append(msg)

        # 2. Requiredness changed
        newly_required = new_req - old_req
        for nrf in sorted(newly_required):
            if is_request:
                is_var_breaking = True
                msg = f"Field '{nrf}' became newly required in request variant '{old_v.variant_id}'"
                var_reasons.append(msg)
                breaking_reasons.append(msg)

        # 3. Type changes on existing fields
        common_fields = set(old_props.keys()).intersection(set(new_props.keys()))
        for f_name in sorted(common_fields):
            o_def = old_props[f_name]
            n_def = new_props[f_name]
            o_type = o_def.get("type", "any") if isinstance(o_def, dict) else str(o_def)
            n_type = n_def.get("type", "any") if isinstance(n_def, dict) else str(n_def)

            if o_type != "any" and n_type != "any" and o_type != n_type:
                # Type incompatibility
                is_var_breaking = True
                msg = f"Type of '{f_name}' in variant '{old_v.variant_id}' changed from '{o_type}' to '{n_type}'"
                var_reasons.append(msg)
                breaking_reasons.append(msg)

        comparisons.append({
            "comparison_type": "VARIANT_PAIRWISE",
            "variant_id": old_v.variant_id,
            "verdict": CompatibilityVerdict.INCOMPATIBLE.value if is_var_breaking else CompatibilityVerdict.COMPATIBLE.value,
            "reasons": var_reasons,
            "is_breaking": is_var_breaking,
        })
