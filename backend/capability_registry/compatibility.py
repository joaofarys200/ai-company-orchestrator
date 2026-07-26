from __future__ import annotations

from collections.abc import Iterable, Mapping

from backend.capability_registry.contracts import (
    CapabilityCompatibility,
    CapabilityId,
    CapabilityRequirement,
    CompatibilityRule,
    CompatibilityTarget,
)
from backend.capability_registry.exceptions import (
    UnknownCompatibilityTargetError,
)


def default_compatibility_rules() -> tuple[CompatibilityRule, ...]:
    return (
        CompatibilityRule(
            target=CompatibilityTarget.RESEARCH_EXECUTOR,
            requirements=(
                CapabilityRequirement(CapabilityId.STRUCTURED_EXTRACTION),
                CapabilityRequirement(CapabilityId.REFERENCE_DISCIPLINE),
                CapabilityRequirement(CapabilityId.BOUNDED_CONTEXT_USE),
            ),
        ),
        CompatibilityRule(
            target=CompatibilityTarget.DOCUMENT_EXECUTOR,
            requirements=(
                CapabilityRequirement(CapabilityId.STRUCTURED_EXTRACTION),
                CapabilityRequirement(CapabilityId.INSTRUCTION_HIERARCHY),
            ),
        ),
        CompatibilityRule(
            target=CompatibilityTarget.MISSION_PLANNER,
            requirements=(
                CapabilityRequirement(CapabilityId.SHORT_HORIZON_PLANNING),
            ),
        ),
        CompatibilityRule(
            target=CompatibilityTarget.TOOL_EXECUTOR,
            requirements=(
                CapabilityRequirement(CapabilityId.STATEFUL_TOOL_USE),
            ),
        ),
    )


class CompatibilityRegistry:
    def __init__(self, rules: Iterable[CompatibilityRule] | None = None):
        selected = tuple(rules or default_compatibility_rules())
        self._rules: Mapping[CompatibilityTarget, CompatibilityRule] = {
            rule.target: rule for rule in selected
        }
        if len(self._rules) != len(selected):
            raise ValueError("Compatibility target duplicado.")

    def rules(self) -> tuple[CompatibilityRule, ...]:
        return tuple(
            self._rules[target]
            for target in sorted(self._rules, key=lambda item: item.value)
        )

    def requires(
        self,
        target: CompatibilityTarget | str,
    ) -> tuple[CapabilityRequirement, ...]:
        return self.rule(target).requirements

    def rule(
        self,
        target: CompatibilityTarget | str,
    ) -> CompatibilityRule:
        normalized = self.normalize_target(target)
        try:
            return self._rules[normalized]
        except KeyError as exc:
            raise UnknownCompatibilityTargetError(
                f"Target sem regra: {normalized.value}."
            ) from exc

    @staticmethod
    def normalize_target(
        target: CompatibilityTarget | str,
    ) -> CompatibilityTarget:
        if isinstance(target, CompatibilityTarget):
            return target
        normalized = str(target or "").strip().upper()
        try:
            return CompatibilityTarget(normalized)
        except ValueError as exc:
            raise UnknownCompatibilityTargetError(
                f"Compatibility target desconhecido: {normalized or '<vazio>'}."
            ) from exc


def compatibility_from_decisions(
    *,
    model_name: str,
    rule: CompatibilityRule,
    decisions: tuple,
) -> CapabilityCompatibility:
    return CapabilityCompatibility(
        model_name=model_name,
        target=rule.target,
        compatible=bool(decisions) and all(
            decision.supported for decision in decisions
        ),
        requirements=rule.requirements,
        decisions=decisions,
    )
