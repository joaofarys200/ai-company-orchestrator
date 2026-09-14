"""
JARVIS OS — Phase 45: Contract Diff Engine
Detects structural discrepancies between formal contracts and observed runtime schemas,
and categorizes changes into NON_BREAKING, POTENTIALLY_BREAKING, and BREAKING.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from agents.runtime_discovery.models import (
    ContractDiff,
    DiffSeverity,
    FieldDifference,
    FieldDiffType,
    InferredSchema,
)


class ContractDiffEngine:
    """Computes fine-grained differences and breakage severity between schemas and contracts."""

    @classmethod
    def compare_schemas(
        cls,
        base_schema: Union[InferredSchema, dict[str, Any]],
        target_schema: Union[InferredSchema, dict[str, Any]],
        route: str = "/",
        method: str = "GET",
        is_request: bool = False,
    ) -> ContractDiff:
        """Compares base (formal contract) against target (inferred runtime schema)."""
        base_dict = base_schema.to_dict() if hasattr(base_schema, "to_dict") else dict(base_schema)
        target_dict = target_schema.to_dict() if hasattr(target_schema, "to_dict") else dict(target_schema)

        base_props = base_dict.get("fields") or base_dict.get("properties") or base_dict
        target_props = target_dict.get("fields") or target_dict.get("properties") or target_dict

        base_required = set(base_dict.get("required_fields", base_dict.get("required", [])))
        target_required = set(target_dict.get("required_fields", target_dict.get("required", [])))

        base_nullable = set(base_dict.get("nullable_fields", []))
        target_nullable = set(target_dict.get("nullable_fields", []))

        # Check per-field flags in properties
        for k, v in base_props.items():
            if isinstance(v, dict):
                if v.get("is_required") or v.get("required"):
                    base_required.add(k)
                if v.get("is_nullable") or v.get("nullable"):
                    base_nullable.add(k)

        for k, v in target_props.items():
            if isinstance(v, dict):
                if v.get("is_required") or v.get("required"):
                    target_required.add(k)
                if v.get("is_nullable") or v.get("nullable"):
                    target_nullable.add(k)

        changes: list[FieldDifference] = []
        all_keys = sorted(list(set(base_props.keys()).union(set(target_props.keys()))))

        for k in all_keys:
            if k in ("required", "properties", "fields", "type", "$schema", "required_fields", "nullable_fields", "enum_candidates", "sample_count", "schema_name", "error_contracts"):
                continue

            in_base = k in base_props
            in_target = k in target_props

            # 1. Added Field
            if not in_base and in_target:
                tgt_type = target_props[k].get("type", "any") if isinstance(target_props[k], dict) else str(target_props[k])
                is_req = k in target_required
                if is_request and is_req:
                    sev = DiffSeverity.BREAKING
                    msg = f"New required field '{k}' ({tgt_type}) added to request payload."
                else:
                    sev = DiffSeverity.NON_BREAKING
                    msg = f"New optional field '{k}' ({tgt_type}) observed in payload."

                changes.append(
                    FieldDifference(
                        field_path=k,
                        diff_type=FieldDiffType.ADDED_FIELD,
                        old_value=None,
                        new_value=tgt_type,
                        severity=sev,
                        message=msg,
                        description=msg,
                    )
                )
                continue

            # 2. Removed Field
            if in_base and not in_target:
                base_type = base_props[k].get("type", "any") if isinstance(base_props[k], dict) else str(base_props[k])
                was_req = k in base_required
                sev = DiffSeverity.BREAKING if was_req else DiffSeverity.POTENTIALLY_BREAKING
                changes.append(
                    FieldDifference(
                        field_path=k,
                        diff_type=FieldDiffType.REMOVED_FIELD,
                        old_value=base_type,
                        new_value=None,
                        severity=sev,
                        message=f"Field '{k}' was defined in formal contract but missing in observed runtime samples.",
                        description=f"Field '{k}' missing from latest schema.",
                    )
                )
                continue

            # 3. Type Changed
            base_def = base_props[k]
            target_def = target_props[k]
            b_type = (base_def.get("type") if isinstance(base_def, dict) else str(base_def)).lower()
            t_type = (target_def.get("type") if isinstance(target_def, dict) else str(target_def)).lower()

            if b_type != "any" and t_type != "any" and b_type != t_type:
                changes.append(
                    FieldDifference(
                        field_path=k,
                        diff_type=FieldDiffType.TYPE_CHANGED,
                        old_value=b_type,
                        new_value=t_type,
                        severity=DiffSeverity.BREAKING,
                        message=f"Field '{k}' type altered from {b_type.upper()} to {t_type.upper()}.",
                        description=f"Type changed from {b_type} to {t_type}.",
                    )
                )

            # 4. Nullability Changed
            was_null = k in base_nullable or (isinstance(base_def, dict) and (base_def.get("nullable", False) or base_def.get("is_nullable", False)))
            is_null = k in target_nullable or (isinstance(target_def, dict) and (target_def.get("nullable", False) or target_def.get("is_nullable", False)))
            if not was_null and is_null:
                changes.append(
                    FieldDifference(
                        field_path=k,
                        diff_type=FieldDiffType.NULLABILITY_CHANGED,
                        old_value=False,
                        new_value=True,
                        severity=DiffSeverity.POTENTIALLY_BREAKING,
                        message=f"Field '{k}' was previously non-nullable, now observed containing null values.",
                        description=f"Field '{k}' became nullable.",
                    )
                )

            # 5. Required Changed
            was_req = k in base_required
            now_req = k in target_required
            if was_req != now_req:
                sev = DiffSeverity.BREAKING if (is_request and now_req) else DiffSeverity.POTENTIALLY_BREAKING
                changes.append(
                    FieldDifference(
                        field_path=k,
                        diff_type=FieldDiffType.REQUIRED_CHANGED,
                        old_value=was_req,
                        new_value=now_req,
                        severity=sev,
                        message=f"Field '{k}' requiredness changed from {was_req} to {now_req}.",
                        description=f"Field '{k}' requiredness changed.",
                    )
                )

        has_breaking = any(c.severity == DiffSeverity.BREAKING for c in changes)
        has_potentially = any(c.severity == DiffSeverity.POTENTIALLY_BREAKING for c in changes)

        if has_breaking:
            overall_sev = DiffSeverity.BREAKING
        elif has_potentially:
            overall_sev = DiffSeverity.POTENTIALLY_BREAKING
        else:
            overall_sev = DiffSeverity.NON_BREAKING

        return ContractDiff(
            diff_id=f"diff_{uuid.uuid4().hex[:8]}",
            route=route,
            method=method,
            changes=changes,
            differences=changes,
            severity=overall_sev,
            is_breaking=has_breaking,
            summary=f"Compared schemas: {len(changes)} differences detected ({overall_sev.value}).",
        )
