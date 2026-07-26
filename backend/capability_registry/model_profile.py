from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import replace

from backend.capability_registry.benchmark_result import LoadedBenchmarkResult
from backend.capability_registry.contracts import (
    Capability,
    CapabilityConfiguration,
    CapabilityDefinition,
    CapabilityEvidence,
    CapabilityId,
    CapabilityLimitation,
    ModelCapabilityProfile,
)


class ModelProfileBuilder:
    def __init__(
        self,
        catalog: Mapping[CapabilityId, CapabilityDefinition],
    ):
        self.catalog = dict(catalog)

    def build(
        self,
        results: Iterable[LoadedBenchmarkResult],
    ) -> tuple[ModelCapabilityProfile, ...]:
        grouped: dict[str, list[LoadedBenchmarkResult]] = defaultdict(list)
        for result in results:
            grouped[result.model_name].append(result)
        profiles = [
            self._build_one(model_name, model_results)
            for model_name, model_results in grouped.items()
        ]
        return tuple(sorted(profiles, key=lambda item: item.model_name))

    def _build_one(
        self,
        model_name: str,
        values: list[LoadedBenchmarkResult],
    ) -> ModelCapabilityProfile:
        results = sorted(
            values,
            key=lambda item: (
                item.evidence.timestamp,
                item.evidence.artifact,
            ),
        )
        provider = ""
        architecture = ""
        parameter_count: int | None = None
        quantization = ""
        context_length: int | None = None
        advertised_features: set[str] = set()
        limitations: list[CapabilityLimitation] = []
        capability_evidence: dict[
            CapabilityId,
            list[CapabilityEvidence],
        ] = defaultdict(list)
        configurations: dict[str, CapabilityConfiguration] = {}
        benchmarks = {}
        for result in results:
            if result.provider:
                provider = result.provider
            if result.architecture:
                architecture = result.architecture
            if result.parameter_count is not None:
                parameter_count = result.parameter_count
            if result.quantization:
                quantization = result.quantization
            if result.context_length is not None:
                context_length = result.context_length
            advertised_features.update(result.advertised_features)
            limitations.extend(result.limitations)
            benchmarks[
                (
                    result.evidence.run_id,
                    result.evidence.artifact,
                    result.evidence.configuration_hash,
                )
            ] = result.evidence
            for configuration in result.configurations:
                configurations[configuration.configuration_hash] = (
                    configuration
                )
            for item in result.capabilities:
                benchmark = replace(
                    result.evidence,
                    metrics=item.metrics,
                    cases=item.cases,
                    limitations=item.limitations,
                )
                capability_evidence[item.capability_id].append(
                    CapabilityEvidence(
                        capability_id=item.capability_id,
                        status=item.status,
                        confidence=item.confidence,
                        benchmark=benchmark,
                    )
                )
                limitations.extend(item.limitations)
        capabilities = tuple(
            self._capability(capability_id, evidence)
            for capability_id, evidence in sorted(
                capability_evidence.items(),
                key=lambda pair: pair[0].value,
            )
        )
        last_validation = max(
            (result.evidence.timestamp for result in results),
            default="",
        )
        return ModelCapabilityProfile(
            model_name=model_name,
            provider=provider,
            architecture=architecture,
            parameter_count=parameter_count,
            quantization=quantization,
            context_length=context_length,
            capabilities=capabilities,
            limitations=self._unique_limitations(limitations),
            benchmarks=tuple(
                benchmarks[key] for key in sorted(benchmarks)
            ),
            configurations=tuple(
                configurations[key] for key in sorted(configurations)
            ),
            advertised_features=tuple(sorted(advertised_features)),
            last_validation=last_validation,
        )

    def _capability(
        self,
        capability_id: CapabilityId,
        raw_evidence: list[CapabilityEvidence],
    ) -> Capability:
        definition = self.catalog[capability_id]
        evidence = tuple(
            sorted(
                raw_evidence,
                key=lambda item: (
                    item.benchmark.timestamp,
                    item.benchmark.artifact,
                ),
            )
        )
        current = evidence[-1]
        configurations = {
            item.benchmark.configuration_hash: item.benchmark.configuration
            for item in evidence
        }
        limitations = [
            limitation
            for item in evidence
            for limitation in item.benchmark.limitations
        ]
        return Capability(
            id=capability_id,
            display_name=definition.display_name,
            description=definition.description,
            status=current.status,
            confidence=current.confidence,
            limitations=self._unique_limitations(limitations),
            requirements=definition.requirements,
            evidence=evidence,
            configurations=tuple(
                configurations[key] for key in sorted(configurations)
            ),
            last_verified=current.benchmark.timestamp,
        )

    @staticmethod
    def _unique_limitations(
        values: Iterable[CapabilityLimitation],
    ) -> tuple[CapabilityLimitation, ...]:
        by_key = {
            (
                item.code,
                item.description,
                item.source_artifact,
            ): item
            for item in values
        }
        return tuple(by_key[key] for key in sorted(by_key))
