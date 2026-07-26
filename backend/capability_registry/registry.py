from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Iterable, Mapping
from dataclasses import replace
from pathlib import Path

from backend.capability_registry.benchmark_result import LoadedBenchmarkResult
from backend.capability_registry.capability import (
    canonical_capability_id,
    default_capability_catalog,
)
from backend.capability_registry.compatibility import CompatibilityRegistry
from backend.capability_registry.contracts import (
    REGISTRY_VERSION,
    Capability,
    CapabilityCompatibility,
    CapabilityDecision,
    CapabilityDefinition,
    CapabilityId,
    CapabilityRegistrySnapshot,
    CapabilityRequirement,
    CapabilitySelection,
    CompatibilityRule,
    CompatibilityTarget,
    ModelCapabilityProfile,
    RegistryValidationResult,
    sha256_json,
)
from backend.capability_registry.exceptions import (
    CapabilityRegistryNotLoadedError,
    UnknownModelError,
)
from backend.capability_registry.loader import BenchmarkLoader
from backend.capability_registry.model_profile import ModelProfileBuilder
from backend.capability_registry.selector import (
    DeterministicCapabilitySelector,
)
from backend.capability_registry.telemetry import (
    CapabilityRegistryTelemetry,
)
from backend.capability_registry.validator import (
    CapabilityRegistryValidator,
)


class CapabilityRegistry:
    def __init__(
        self,
        source_root: str | Path = "diagnostics",
        *,
        catalog: Mapping[
            CapabilityId,
            CapabilityDefinition,
        ] | None = None,
        compatibility_rules: Iterable[CompatibilityRule] | None = None,
        loader: BenchmarkLoader | None = None,
        telemetry: CapabilityRegistryTelemetry | None = None,
    ):
        self.source_root = Path(source_root).resolve()
        self.catalog = dict(catalog or default_capability_catalog())
        self.compatibility = CompatibilityRegistry(compatibility_rules)
        self.loader = loader or BenchmarkLoader(self.source_root)
        self.telemetry = telemetry or CapabilityRegistryTelemetry()
        self.validator = CapabilityRegistryValidator()
        self._results: tuple[LoadedBenchmarkResult, ...] = ()
        self._profiles: dict[str, ModelCapabilityProfile] = {}
        self._snapshot: CapabilityRegistrySnapshot | None = None
        self._loaded = False

    def load(self) -> CapabilityRegistrySnapshot:
        results = self.loader.load()
        profiles = ModelProfileBuilder(self.catalog).build(results)
        self.validator.validate_or_raise(
            catalog=self.catalog,
            profiles=profiles,
            rules=self.compatibility.rules(),
        )
        self._results = results
        self._profiles = {
            profile.model_name: profile
            for profile in profiles
        }
        self._snapshot = self._build_snapshot()
        self.validator.validate_or_raise(
            catalog=self.catalog,
            profiles=profiles,
            rules=self.compatibility.rules(),
            snapshot=self._snapshot,
        )
        self._loaded = True
        for result in results:
            self.telemetry.record(
                event="benchmark_loaded",
                registry_version=REGISTRY_VERSION,
                snapshot_version=self._snapshot.snapshot_version,
                model=result.model_name,
                benchmark=result.evidence.benchmark_id,
                configuration_hash=result.evidence.configuration_hash,
            )
        self.telemetry.record(
            event="registry_loaded",
            registry_version=REGISTRY_VERSION,
            snapshot_version=self._snapshot.snapshot_version,
        )
        return self._snapshot

    def reload(self) -> CapabilityRegistrySnapshot:
        return self.load()

    def get_model(self, model_name: str) -> ModelCapabilityProfile:
        self._require_loaded()
        try:
            return self._profiles[str(model_name)]
        except KeyError as exc:
            raise UnknownModelError(
                f"Modelo nao registado: {model_name}."
            ) from exc

    def list_models(self) -> tuple[ModelCapabilityProfile, ...]:
        self._require_loaded()
        return tuple(
            self._profiles[name]
            for name in sorted(self._profiles)
        )

    def get_capability(
        self,
        capability: CapabilityId | str,
        model_name: str | None = None,
    ) -> CapabilityDefinition | Capability | None:
        capability_id = canonical_capability_id(capability)
        if model_name is None:
            return self.catalog[capability_id]
        return self.get_model(model_name).capability(capability_id)

    def supports(
        self,
        model_name: str,
        capability: CapabilityId | str,
        *,
        configuration_hash: str = "",
    ) -> CapabilityDecision:
        selector = self._selector()
        decision = selector.supports(
            model_name,
            capability,
            configuration_hash=configuration_hash,
        )
        self.telemetry.record(
            event="capability_support_checked",
            registry_version=REGISTRY_VERSION,
            snapshot_version=self._snapshot_version(),
            model=str(model_name),
            configuration_hash=str(configuration_hash),
            selection_reason=decision.reason.value,
            rejected_capabilities=(
                ()
                if decision.supported
                else (decision.capability_id.value,)
            ),
        )
        return decision

    def requires(
        self,
        target: CompatibilityTarget | str,
    ) -> tuple[CapabilityRequirement, ...]:
        return self.compatibility.requires(target)

    def compatible_with(
        self,
        model_name: str,
        target: CompatibilityTarget | str,
        *,
        configuration_hash: str = "",
    ) -> CapabilityCompatibility:
        result = self._selector().compatible_with(
            model_name,
            target,
            configuration_hash=configuration_hash,
        )
        failures = tuple(
            decision.capability_id.value
            for decision in result.decisions
            if not decision.supported
        )
        self.telemetry.record(
            event="compatibility_checked",
            registry_version=REGISTRY_VERSION,
            snapshot_version=self._snapshot_version(),
            model=str(model_name),
            configuration_hash=str(configuration_hash),
            selection_reason=(
                "COMPATIBLE" if result.compatible else "INCOMPATIBLE"
            ),
            compatibility_failures=failures,
        )
        return result

    def select_capabilities(
        self,
        model_name: str,
        *,
        configuration_hash: str = "",
    ) -> tuple[Capability, ...]:
        return self._selector().select_capabilities(
            model_name,
            configuration_hash=configuration_hash,
        )

    def select_models(
        self,
        required_capabilities: Iterable[CapabilityId | str],
        *,
        compatibility_target: CompatibilityTarget | str | None = None,
        configuration_hash: str = "",
        model_names: Iterable[str] | None = None,
    ) -> CapabilitySelection:
        result = self._selector().select_models(
            required_capabilities,
            compatibility_target=compatibility_target,
            configuration_hash=configuration_hash,
            model_names=model_names,
        )
        self.telemetry.record(
            event="models_selected",
            registry_version=REGISTRY_VERSION,
            snapshot_version=self._snapshot_version(),
            configuration_hash=str(configuration_hash),
            selection_reason=(
                "MATCHES_FOUND"
                if result.selected_models
                else "NO_MATCH"
            ),
            rejected_capabilities=tuple(
                sorted({
                    decision.capability_id.value
                    for decision in result.decisions
                    if not decision.supported
                })
            ),
            compatibility_failures=tuple(result.rejected_models),
        )
        return result

    def select(
        self,
        required_capabilities: Iterable[CapabilityId | str],
        **options,
    ) -> CapabilitySelection:
        return self.select_models(required_capabilities, **options)

    def validate(self) -> RegistryValidationResult:
        self._require_loaded()
        result = self.validator.validate(
            catalog=self.catalog,
            profiles=self.list_models(),
            rules=self.compatibility.rules(),
            snapshot=self._snapshot,
        )
        self.telemetry.record(
            event="registry_validated",
            registry_version=REGISTRY_VERSION,
            snapshot_version=self._snapshot_version(),
            selection_reason="VALID" if result.valid else "INVALID",
        )
        return result

    def export_snapshot(
        self,
        destination: str | Path | None = None,
    ) -> CapabilityRegistrySnapshot:
        self._require_loaded()
        assert self._snapshot is not None
        if destination is not None:
            path = Path(destination)
            path.parent.mkdir(parents=True, exist_ok=True)
            payload = json.dumps(
                self._snapshot.to_dict(),
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            ) + "\n"
            temporary_path = ""
            try:
                with tempfile.NamedTemporaryFile(
                    mode="w",
                    encoding="utf-8",
                    newline="\n",
                    dir=path.parent,
                    prefix=f".{path.name}.",
                    suffix=".tmp",
                    delete=False,
                ) as stream:
                    stream.write(payload)
                    stream.flush()
                    os.fsync(stream.fileno())
                    temporary_path = stream.name
                os.replace(temporary_path, path)
            finally:
                if temporary_path and os.path.exists(temporary_path):
                    os.unlink(temporary_path)
        self.telemetry.record(
            event="snapshot_exported",
            registry_version=REGISTRY_VERSION,
            snapshot_version=self._snapshot.snapshot_version,
        )
        return self._snapshot

    def _build_snapshot(self) -> CapabilityRegistrySnapshot:
        models = tuple(
            self._profiles[name]
            for name in sorted(self._profiles)
        )
        rules = self.compatibility.rules()
        source_payload = [
            {
                "artifact": item.evidence.artifact,
                "artifact_sha256": item.evidence.artifact_sha256,
                "artifact_hashes": dict(item.evidence.artifact_hashes),
                "report_artifact": item.evidence.report_artifact,
                "report_sha256": item.evidence.report_sha256,
                "configuration_hash": item.evidence.configuration_hash,
            }
            for item in self._results
        ]
        source_sha256 = sha256_json(source_payload)
        generated_at = max(
            (
                benchmark.timestamp
                for profile in models
                for benchmark in profile.benchmarks
            ),
            default="1970-01-01T00:00:00+00:00",
        )
        snapshot = CapabilityRegistrySnapshot(
            registry_version=REGISTRY_VERSION,
            snapshot_version=(
                f"{REGISTRY_VERSION}-{source_sha256[:16]}"
            ),
            generated_at=generated_at,
            models=models,
            compatibility_rules=rules,
            source_sha256=source_sha256,
            content_sha256="0" * 64,
        )
        return replace(
            snapshot,
            content_sha256=snapshot.computed_content_sha256(),
        )

    def _selector(self) -> DeterministicCapabilitySelector:
        self._require_loaded()
        return DeterministicCapabilitySelector(
            self._profiles,
            self.compatibility,
        )

    def _require_loaded(self) -> None:
        if not self._loaded:
            raise CapabilityRegistryNotLoadedError(
                "CapabilityRegistry ainda nao foi carregado."
            )

    def _snapshot_version(self) -> str:
        return self._snapshot.snapshot_version if self._snapshot else ""
