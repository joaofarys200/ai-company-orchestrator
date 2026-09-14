"""
JARVIS OS — Phase 47: Polymorphic Schema Diff & Drift Engine
Computes granular diffs across polymorphic variants, discriminators, common fields,
and requiredness, synthesizing PolymorphicDriftReport for continuous governance.
"""

from __future__ import annotations

import copy
import time
import uuid
from typing import Any, Dict, List, Optional, Set, Tuple

from agents.polymorphic_schema.models import (
    PolymorphicDriftReport,
    PolymorphicSchema,
    SchemaVariant,
    VariantDiff,
    VariantDiffType,
)


class PolymorphicDiffEngine:
    """Computes structural diffs between baseline and observed polymorphic schemas."""

    @classmethod
    def diff_schemas(
        cls,
        baseline_schema: PolymorphicSchema,
        observed_schema: PolymorphicSchema,
        is_request: bool = False,
    ) -> List[VariantDiff]:
        """Calculates all atomic diffs between baseline and observed polymorphic schemas."""
        return cls.compute_diff(baseline_schema, observed_schema, is_request)

    @classmethod
    def generate_drift_report(
        cls,
        baseline_schema: PolymorphicSchema,
        observed_payloads: List[Dict[str, Any]],
        is_request: bool = False,
    ) -> PolymorphicDriftReport:
        """Infers observed schema from runtime payloads and creates a PolymorphicDriftReport."""
        from agents.polymorphic_schema.detector import PolymorphicDetector
        obs_schema = PolymorphicDetector.detect_polymorphism(
            route=baseline_schema.route or "/events",
            method=baseline_schema.method or "POST",
            observations=observed_payloads,
            schema_id=f"{baseline_schema.schema_id}_observed",
            contract_id=baseline_schema.contract_id,
        )
        report = cls.generate_polymorphic_drift_report(
            contract_id=baseline_schema.contract_id,
            baseline_schema=baseline_schema,
            observed_schema=obs_schema,
            is_request=is_request,
        )
        report.has_drift = len(report.diffs) > 0
        report.is_polymorphic_variation = any(
            d.diff_type in (VariantDiffType.VARIANT_ADDED, VariantDiffType.VARIANT_REMOVED, VariantDiffType.VARIANT_MODIFIED)
            for d in report.diffs
        ) or bool(obs_schema and obs_schema.variants)
        report.drift_classification = "POLYMORPHIC_VARIANTS" if report.is_polymorphic_variation else "SCHEMA_DRIFT"
        return report

    @classmethod
    def compute_diff(
        cls,
        baseline_schema: PolymorphicSchema,
        observed_schema: PolymorphicSchema,
        is_request: bool = False,
    ) -> List[VariantDiff]:
        """Calculates all atomic diffs between baseline and observed polymorphic schemas."""
        diffs: List[VariantDiff] = []

        base_variants = {v.variant_id: v for v in baseline_schema.variants}
        obs_variants = {v.variant_id: v for v in observed_schema.variants}

        # 1. Discriminator diffs
        cls._diff_discriminator(baseline_schema, observed_schema, diffs)

        # 2. Common fields diffs
        cls._diff_common_fields(baseline_schema, observed_schema, diffs, is_request)

        # 3. Removed variants
        removed = set(base_variants.keys()) - set(obs_variants.keys())
        for r_id in sorted(removed):
            diffs.append(
                VariantDiff(
                    diff_type=VariantDiffType.VARIANT_REMOVED,
                    variant_id=r_id,
                    field_path=f"variants.{r_id}",
                    classification="BREAKING",
                    old_value=r_id,
                    new_value=None,
                    description=f"Variant '{r_id}' missing in observed runtime traffic",
                    is_breaking=True,
                )
            )

        # 4. Added variants
        added = set(obs_variants.keys()) - set(base_variants.keys())
        for a_id in sorted(added):
            obs_v = obs_variants[a_id]
            diffs.append(
                VariantDiff(
                    diff_type=VariantDiffType.VARIANT_ADDED,
                    variant_id=a_id,
                    field_path=f"variants.{a_id}",
                    classification="NON_BREAKING" if is_request else "POTENTIALLY_BREAKING",
                    old_value=None,
                    new_value=a_id,
                    description=f"New variant '{a_id}' observed in runtime traffic",
                    is_breaking=False,
                )
            )

        # 5. Modified variants (pairwise)
        common_v_ids = set(base_variants.keys()).intersection(set(obs_variants.keys()))
        for v_id in sorted(common_v_ids):
            base_v = base_variants[v_id]
            obs_v = obs_variants[v_id]
            cls._diff_single_variant(base_v, obs_v, diffs, is_request)

        return diffs

    @classmethod
    def _diff_discriminator(
        cls,
        base_s: PolymorphicSchema,
        obs_s: PolymorphicSchema,
        diffs: List[VariantDiff],
    ) -> None:
        bd = base_s.discriminator
        od = obs_s.discriminator

        if bd and not od:
            diffs.append(
                VariantDiff(
                    diff_type=VariantDiffType.DISCRIMINATOR_REMOVED,
                    variant_id="global",
                    field_path="discriminator",
                    classification="BREAKING",
                    old_value=bd.field,
                    new_value=None,
                    description=f"Discriminator '{bd.field}' missing in observed traffic",
                    is_breaking=True,
                )
            )
        elif not bd and od:
            diffs.append(
                VariantDiff(
                    diff_type=VariantDiffType.DISCRIMINATOR_ADDED,
                    variant_id="global",
                    field_path="discriminator",
                    classification="POTENTIALLY_BREAKING",
                    old_value=None,
                    new_value=od.field,
                    description=f"Discriminator '{od.field}' detected in observed traffic",
                    is_breaking=False,
                )
            )
        elif bd and od and bd.field != od.field:
            diffs.append(
                VariantDiff(
                    diff_type=VariantDiffType.DISCRIMINATOR_CHANGED,
                    variant_id="global",
                    field_path="discriminator.field",
                    classification="BREAKING",
                    old_value=bd.field,
                    new_value=od.field,
                    description=f"Discriminator field changed from '{bd.field}' to '{od.field}'",
                    is_breaking=True,
                )
            )

    @classmethod
    def _diff_common_fields(
        cls,
        base_s: PolymorphicSchema,
        obs_s: PolymorphicSchema,
        diffs: List[VariantDiff],
        is_request: bool,
    ) -> None:
        base_common = set(base_s.common_fields)
        obs_common = set(obs_s.common_fields)

        removed_common = base_common - obs_common
        for rc in sorted(removed_common):
            diffs.append(
                VariantDiff(
                    diff_type=VariantDiffType.COMMON_FIELD_CHANGED,
                    variant_id="global",
                    field_path=f"common_fields.{rc}",
                    classification="BREAKING" if not is_request else "NON_BREAKING",
                    old_value=rc,
                    new_value=None,
                    description=f"Common field '{rc}' no longer present across all variants",
                    is_breaking=not is_request,
                )
            )

    @classmethod
    def _diff_single_variant(
        cls,
        base_v: SchemaVariant,
        obs_v: SchemaVariant,
        diffs: List[VariantDiff],
        is_request: bool,
    ) -> None:
        b_props = base_v.schema.get("properties", base_v.schema)
        o_props = obs_v.schema.get("properties", obs_v.schema)

        # Removed field from variant
        removed = set(b_props.keys()) - set(o_props.keys())
        for rf in sorted(removed):
            diffs.append(
                VariantDiff(
                    diff_type=VariantDiffType.VARIANT_FIELD_CHANGED,
                    variant_id=base_v.variant_id,
                    field_path=f"variants.{base_v.variant_id}.{rf}",
                    classification="BREAKING" if not is_request else "NON_BREAKING",
                    old_value=rf,
                    new_value=None,
                    description=f"Field '{rf}' missing from variant '{base_v.variant_id}'",
                    is_breaking=not is_request,
                )
            )

        # Added field to variant
        added = set(o_props.keys()) - set(b_props.keys())
        for af in sorted(added):
            diffs.append(
                VariantDiff(
                    diff_type=VariantDiffType.VARIANT_FIELD_CHANGED,
                    variant_id=base_v.variant_id,
                    field_path=f"variants.{base_v.variant_id}.{af}",
                    classification="NON_BREAKING",
                    old_value=None,
                    new_value=af,
                    description=f"New field '{af}' observed in variant '{base_v.variant_id}'",
                    is_breaking=False,
                )
            )

        # Requiredness changed
        b_req = set(base_v.required_fields)
        o_req = set(obs_v.required_fields)
        newly_req = o_req - b_req
        for nr in sorted(newly_req):
            diffs.append(
                VariantDiff(
                    diff_type=VariantDiffType.VARIANT_REQUIREDNESS_CHANGED,
                    variant_id=base_v.variant_id,
                    field_path=f"variants.{base_v.variant_id}.{nr}.required",
                    classification="BREAKING" if is_request else "NON_BREAKING",
                    old_value=False,
                    new_value=True,
                    description=f"Field '{nr}' in variant '{base_v.variant_id}' became required",
                    is_breaking=is_request,
                )
            )

    @classmethod
    def generate_polymorphic_drift_report(
        cls,
        contract_id: str,
        baseline_schema: PolymorphicSchema,
        observed_schema: PolymorphicSchema,
        is_request: bool = False,
    ) -> PolymorphicDriftReport:
        """Generates a comprehensive drift report for Phase 46 Continuous Governance integration."""
        diffs = cls.compute_diff(baseline_schema, observed_schema, is_request)

        has_breaking = any(d.is_breaking for d in diffs)
        has_potential = any(d.classification == "POTENTIALLY_BREAKING" for d in diffs)

        if has_breaking:
            classification = "BREAKING"
            action = "REQUEST_HUMAN"
        elif has_potential:
            classification = "POTENTIALLY_BREAKING"
            action = "REQUEST_VALIDATION"
        elif diffs:
            classification = "NON_BREAKING"
            action = "MONITOR"
        else:
            classification = "NON_BREAKING"
            action = "MONITOR"

        base_vars = set(v.variant_id for v in baseline_schema.variants)
        obs_vars = set(v.variant_id for v in observed_schema.variants)

        new_vars = sorted(list(obs_vars - base_vars))
        rem_vars = sorted(list(base_vars - obs_vars))

        return PolymorphicDriftReport(
            drift_id=f"poly_drift_{uuid.uuid4().hex[:8]}",
            contract_id=contract_id,
            baseline_version=baseline_schema.version,
            observed_version=f"{baseline_schema.version}-observed",
            diffs=diffs,
            classification=classification,
            new_variants=new_vars,
            removed_variants=rem_vars,
            recommended_action=action,
            confidence=0.95 if observed_schema.status.value != "UNCERTAIN" else 0.50,
            timestamp=time.time(),
            notes=f"Detected {len(diffs)} polymorphic structural difference(s).",
        )
