from __future__ import annotations

from dataclasses import dataclass

from backend.capability_registry.contracts import (
    BenchmarkEvidence,
    CapabilityConfiguration,
    CapabilityId,
    CapabilityLimitation,
    CapabilityMetrics,
    CapabilityStatus,
)


@dataclass(frozen=True)
class LoadedCapabilityResult:
    capability_id: CapabilityId
    status: CapabilityStatus
    confidence: float
    metrics: CapabilityMetrics
    cases: tuple[str, ...]
    limitations: tuple[CapabilityLimitation, ...]


@dataclass(frozen=True)
class LoadedBenchmarkResult:
    evidence: BenchmarkEvidence
    model_name: str
    provider: str
    architecture: str
    parameter_count: int | None
    quantization: str
    context_length: int | None
    advertised_features: tuple[str, ...]
    capabilities: tuple[LoadedCapabilityResult, ...]
    configurations: tuple[CapabilityConfiguration, ...]
    limitations: tuple[CapabilityLimitation, ...]
