from __future__ import annotations

from typing import Any

from backend.capability_registry import (
    REGISTRY_VERSION,
    SUPPORTED_CAPABILITY_STATUSES,
    CapabilityRegistry,
)
from backend.semantic_context.contracts import (
    BuilderConfiguration,
    CapabilityContext,
    CompatibilityAssessment,
    DemonstratedCapability,
    sha256_json,
    to_jsonable,
)


class CapabilityContextReader:
    """Project benchmark evidence through the Capability Registry public API."""

    def __init__(self, registry: CapabilityRegistry):
        self.registry = registry

    def read(self, configuration: BuilderConfiguration) -> CapabilityContext:
        profile = self.registry.get_model(configuration.model_name)
        registry_snapshot = self.registry.export_snapshot()
        demonstrated: list[DemonstratedCapability] = []
        for capability in sorted(
            profile.capabilities,
            key=lambda item: item.id.value,
        ):
            if capability.status not in SUPPORTED_CAPABILITY_STATUSES:
                continue
            if configuration.capability_configuration_hash:
                decision = self.registry.supports(
                    configuration.model_name,
                    capability.id,
                    configuration_hash=(
                        configuration.capability_configuration_hash
                    ),
                )
                if not decision.supported:
                    continue
            evidence_references = tuple(
                sorted({
                    f"benchmark:{evidence.benchmark.artifact}"
                    for evidence in capability.evidence
                })
            )
            demonstrated.append(
                DemonstratedCapability(
                    capability_id=capability.id.value,
                    status=capability.status.value,
                    confidence=capability.confidence,
                    last_verified=capability.last_verified,
                    evidence_references=evidence_references,
                    limitations=tuple(
                        _limitation_payload(item)
                        for item in capability.limitations
                    ),
                    configurations=tuple(
                        _configuration_payload(item)
                        for item in capability.configurations
                    ),
                )
            )

        compatibility: list[CompatibilityAssessment] = []
        for target in configuration.compatibility_targets:
            result = self.registry.compatible_with(
                configuration.model_name,
                target,
                configuration_hash=(
                    configuration.capability_configuration_hash
                ),
            )
            compatibility.append(
                CompatibilityAssessment(
                    target=result.target.value,
                    compatible=result.compatible,
                    requirements=tuple(
                        item.capability_id.value
                        for item in result.requirements
                    ),
                    failed_requirements=tuple(
                        item.capability_id.value
                        for item in result.decisions
                        if not item.supported
                    ),
                )
            )

        limitations = tuple(
            _limitation_payload(item)
            for item in sorted(
                profile.limitations,
                key=lambda value: (
                    value.code,
                    value.source_artifact,
                ),
            )
        )
        source_payload: dict[str, Any] = {
            "registry_version": REGISTRY_VERSION,
            "registry_snapshot_version": registry_snapshot.snapshot_version,
            "registry_content_sha256": registry_snapshot.content_sha256,
            "model_name": profile.model_name,
            "configuration_hash": (
                configuration.capability_configuration_hash
            ),
            "capabilities": demonstrated,
            "limitations": limitations,
            "compatibility": compatibility,
        }
        return CapabilityContext(
            registry_version=REGISTRY_VERSION,
            registry_snapshot_version=registry_snapshot.snapshot_version,
            model_name=profile.model_name,
            configuration_hash=(
                configuration.capability_configuration_hash
            ),
            capabilities=tuple(demonstrated),
            limitations=limitations,
            compatibility=tuple(compatibility),
            last_validation=profile.last_validation,
            source_sha256=sha256_json(source_payload),
        )


def _limitation_payload(value: Any) -> dict[str, Any]:
    return {
        "code": value.code,
        "description": value.description,
        "severity": value.severity.value,
        "source_artifact": value.source_artifact,
    }


def _configuration_payload(value: Any) -> dict[str, Any]:
    payload = to_jsonable(value)
    return dict(payload)
