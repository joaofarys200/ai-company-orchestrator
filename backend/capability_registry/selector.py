from __future__ import annotations

from collections.abc import Iterable, Mapping

from backend.capability_registry.capability import canonical_capability_id
from backend.capability_registry.compatibility import (
    CompatibilityRegistry,
    compatibility_from_decisions,
)
from backend.capability_registry.contracts import (
    Capability,
    CapabilityCompatibility,
    CapabilityDecision,
    CapabilityId,
    CapabilitySelection,
    CapabilityStatus,
    CompatibilityTarget,
    ModelCapabilityProfile,
    SUPPORTED_CAPABILITY_STATUSES,
    SelectionReason,
)


class DeterministicCapabilitySelector:
    def __init__(
        self,
        profiles: Mapping[str, ModelCapabilityProfile],
        compatibility: CompatibilityRegistry,
    ):
        self.profiles = dict(profiles)
        self.compatibility = compatibility

    def supports(
        self,
        model_name: str,
        capability: CapabilityId | str,
        *,
        configuration_hash: str = "",
    ) -> CapabilityDecision:
        capability_id = canonical_capability_id(capability)
        profile = self.profiles.get(str(model_name))
        if profile is None:
            return CapabilityDecision(
                model_name=str(model_name),
                capability_id=capability_id,
                supported=False,
                status=CapabilityStatus.UNKNOWN,
                reason=SelectionReason.MODEL_NOT_FOUND,
                configuration_hash=str(configuration_hash),
            )
        item = profile.capability(capability_id)
        if item is None:
            return CapabilityDecision(
                model_name=profile.model_name,
                capability_id=capability_id,
                supported=False,
                status=CapabilityStatus.UNKNOWN,
                reason=SelectionReason.NO_BENCHMARK_EVIDENCE,
                configuration_hash=str(configuration_hash),
            )
        if configuration_hash and not self._has_configuration(
            item,
            configuration_hash,
        ):
            return CapabilityDecision(
                model_name=profile.model_name,
                capability_id=capability_id,
                supported=False,
                status=item.status,
                reason=SelectionReason.CONFIGURATION_NOT_TESTED,
                configuration_hash=str(configuration_hash),
                evidence_artifacts=self._artifacts(item),
            )
        supported = item.status in SUPPORTED_CAPABILITY_STATUSES
        return CapabilityDecision(
            model_name=profile.model_name,
            capability_id=capability_id,
            supported=supported,
            status=item.status,
            reason=(
                SelectionReason.SUPPORTED
                if supported
                else SelectionReason.STATUS_NOT_SUPPORTED
            ),
            configuration_hash=str(configuration_hash),
            evidence_artifacts=self._artifacts(item),
        )

    def compatible_with(
        self,
        model_name: str,
        target: CompatibilityTarget | str,
        *,
        configuration_hash: str = "",
    ) -> CapabilityCompatibility:
        rule = self.compatibility.rule(target)
        decisions = tuple(
            self.supports(
                model_name,
                requirement.capability_id,
                configuration_hash=configuration_hash,
            )
            for requirement in rule.requirements
        )
        adjusted = tuple(
            decision
            if requirement.accepts(decision.status)
            else CapabilityDecision(
                model_name=decision.model_name,
                capability_id=decision.capability_id,
                supported=False,
                status=decision.status,
                reason=SelectionReason.COMPATIBILITY_REQUIREMENT_FAILED,
                configuration_hash=decision.configuration_hash,
                evidence_artifacts=decision.evidence_artifacts,
            )
            for requirement, decision in zip(
                rule.requirements,
                decisions,
                strict=True,
            )
        )
        return compatibility_from_decisions(
            model_name=str(model_name),
            rule=rule,
            decisions=adjusted,
        )

    def select_models(
        self,
        required_capabilities: Iterable[CapabilityId | str],
        *,
        compatibility_target: CompatibilityTarget | str | None = None,
        configuration_hash: str = "",
        model_names: Iterable[str] | None = None,
    ) -> CapabilitySelection:
        requested = tuple(
            sorted(
                {
                    canonical_capability_id(item)
                    for item in required_capabilities
                },
                key=lambda item: item.value,
            )
        )
        target = (
            self.compatibility.normalize_target(compatibility_target)
            if compatibility_target is not None
            else None
        )
        candidates = (
            sorted({str(item) for item in model_names})
            if model_names is not None
            else sorted(self.profiles)
        )
        selected: list[str] = []
        rejected: list[str] = []
        decisions: list[CapabilityDecision] = []
        for model_name in candidates:
            model_decisions = [
                self.supports(
                    model_name,
                    capability_id,
                    configuration_hash=configuration_hash,
                )
                for capability_id in requested
            ]
            if target is not None:
                compatibility = self.compatible_with(
                    model_name,
                    target,
                    configuration_hash=configuration_hash,
                )
                model_decisions.extend(compatibility.decisions)
            decisions.extend(model_decisions)
            if model_decisions and all(
                item.supported for item in model_decisions
            ):
                selected.append(model_name)
            elif not model_decisions and model_name in self.profiles:
                selected.append(model_name)
            else:
                rejected.append(model_name)
        return CapabilitySelection(
            requested_capabilities=requested,
            selected_models=tuple(selected),
            rejected_models=tuple(rejected),
            decisions=tuple(decisions),
            compatibility_target=target,
            configuration_hash=str(configuration_hash),
        )

    def select_capabilities(
        self,
        model_name: str,
        *,
        configuration_hash: str = "",
    ) -> tuple[Capability, ...]:
        profile = self.profiles.get(str(model_name))
        if profile is None:
            return ()
        return tuple(
            capability
            for capability in profile.capabilities
            if self.supports(
                model_name,
                capability.id,
                configuration_hash=configuration_hash,
            ).supported
        )

    @staticmethod
    def _has_configuration(
        capability: Capability,
        configuration_hash: str,
    ) -> bool:
        return any(
            item.configuration_hash == configuration_hash
            for item in capability.configurations
        )

    @staticmethod
    def _artifacts(capability: Capability) -> tuple[str, ...]:
        return tuple(
            sorted({
                item.benchmark.artifact
                for item in capability.evidence
            })
        )
