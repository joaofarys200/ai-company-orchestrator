from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.capability_registry.benchmark_result import (
    LoadedBenchmarkResult,
    LoadedCapabilityResult,
)
from backend.capability_registry.capability import canonical_capability_id
from backend.capability_registry.contracts import (
    BenchmarkEvidence,
    BenchmarkEvidenceKind,
    BenchmarkOutcome,
    CapabilityConfiguration,
    CapabilityLimitation,
    CapabilityMetrics,
    CapabilityStatus,
    LimitationSeverity,
    sha256_json,
)
from backend.capability_registry.exceptions import (
    BenchmarkArtifactError,
    BenchmarkHashMismatchError,
    UnsupportedBenchmarkFormatError,
)


BOUNDED_BENCHMARK_VERSION = "model_harness_qwen35_capabilities_v1"
STATEFUL_BENCHMARK_VERSION = "model_harness_qwen35_stateful_v2"
PROVIDER_DIAGNOSTIC_PREFIX = "stateful_provider_path_diagnostic_"

BOUNDED_SCOPE_LIMITATIONS = (
    "Synthetic, read-only bounded cases do not demonstrate general capability.",
    "Results apply only to the recorded cases and configuration.",
)


class BenchmarkLoader:
    def __init__(self, source_root: str | Path, *, strict: bool = True):
        self.source_root = Path(source_root).resolve()
        self.strict = bool(strict)

    def load(self) -> tuple[LoadedBenchmarkResult, ...]:
        if not self.source_root.exists():
            raise BenchmarkArtifactError(
                f"Diretorio de benchmark inexistente: {self.source_root}."
            )
        results: list[LoadedBenchmarkResult] = []
        for run_dir in self.discover_runs():
            try:
                result = self._load_run(run_dir)
            except UnsupportedBenchmarkFormatError:
                if self.strict:
                    raise
                continue
            if result is not None:
                results.append(result)
        return tuple(
            sorted(
                results,
                key=lambda item: (
                    item.evidence.timestamp,
                    item.evidence.artifact,
                ),
            )
        )

    def discover_runs(self) -> tuple[Path, ...]:
        candidates: set[Path] = set()
        filenames = (
            "summary.json",
            "capability_profile.json",
            "manifest.json",
        )
        for filename in filenames:
            for path in self.source_root.rglob(filename):
                candidates.add(path.parent.resolve())
        supported = [
            path
            for path in candidates
            if self._run_format(path) is not None
        ]
        return tuple(sorted(supported, key=lambda item: item.as_posix()))

    def _load_run(self, run_dir: Path) -> LoadedBenchmarkResult | None:
        run_format = self._run_format(run_dir)
        if run_format is None:
            raise UnsupportedBenchmarkFormatError(
                f"Formato de benchmark desconhecido: {run_dir}."
            )
        manifest = self._optional_json(run_dir / "manifest.json")
        summary = self._optional_json(run_dir / "summary.json")
        profile = self._optional_json(run_dir / "capability_profile.json")
        self._assert_versions(
            run_format,
            manifest=manifest,
            summary=summary,
            profile=profile,
        )
        if run_format == BOUNDED_BENCHMARK_VERSION:
            if not summary:
                raise BenchmarkArtifactError(
                    f"Benchmark bounded sem summary.json: {run_dir}."
                )
            return self._load_bounded(run_dir, manifest, summary)
        if run_format == STATEFUL_BENCHMARK_VERSION:
            if not summary or not profile:
                raise BenchmarkArtifactError(
                    f"Benchmark stateful incompleto: {run_dir}."
                )
            return self._load_stateful(run_dir, manifest, summary, profile)
        if run_format.startswith(PROVIDER_DIAGNOSTIC_PREFIX):
            return self._load_provider_diagnostic(
                run_dir,
                manifest,
                summary,
                run_format,
            )
        raise UnsupportedBenchmarkFormatError(
            f"Benchmark nao suportado: {run_format}."
        )

    def _load_bounded(
        self,
        run_dir: Path,
        manifest: Mapping[str, Any],
        summary: Mapping[str, Any],
    ) -> LoadedBenchmarkResult:
        model = self._required_text(summary.get("model"), "summary.model")
        config = self._configuration(
            raw=summary.get("config") or manifest.get("config") or {},
            model=model,
            provider=self._provider(run_dir, manifest, summary),
            declared_hash="",
            stateful=False,
        )
        artifact = run_dir / "summary.json"
        artifact_ref = self._artifact_ref(artifact)
        artifact_hash = self._sha256_file(artifact)
        sidecar_verified = self._validate_declared_artifact_hashes(
            run_dir,
            manifest,
        )
        limitations = self._limitations(
            tuple(summary.get("limitations_observed") or ())
            + BOUNDED_SCOPE_LIMITATIONS,
            artifact_ref,
        )
        demonstrated = {
            str(item).strip()
            for item in summary.get("capabilities_demonstrated") or ()
        }
        capabilities: list[LoadedCapabilityResult] = []
        seen_case_ids: set[str] = set()
        for case in summary.get("cases") or ():
            if not isinstance(case, Mapping):
                raise BenchmarkArtifactError(
                    f"Case invalido em {artifact_ref}."
                )
            raw_capability = self._required_text(
                case.get("capability"),
                "case.capability",
            )
            capability_id = canonical_capability_id(raw_capability)
            passed_repetitions = self._integer(
                case.get("passed_repetitions"),
                default=0,
            )
            repetitions = self._integer(
                case.get("total_repetitions"),
                default=0,
            )
            pass_rate = (
                passed_repetitions / repetitions if repetitions else 0.0
            )
            passed = bool(case.get("passed"))
            if passed and raw_capability in demonstrated:
                status = CapabilityStatus.DEMONSTRATED_PRELIMINARY
            elif passed:
                status = CapabilityStatus.NOT_DEMONSTRATED
            else:
                status = CapabilityStatus.FAILED
            case_id = self._required_text(
                case.get("case_id"),
                "case.case_id",
            )
            if case_id in seen_case_ids:
                raise BenchmarkArtifactError(
                    f"Case duplicado em {artifact_ref}: {case_id}."
                )
            seen_case_ids.add(case_id)
            capabilities.append(
                LoadedCapabilityResult(
                    capability_id=capability_id,
                    status=status,
                    confidence=round(pass_rate, 6),
                    metrics=CapabilityMetrics(
                        calls=repetitions,
                        cases=1,
                        passed_cases=1 if passed else 0,
                        failed_cases=0 if passed else 1,
                        pass_rate=pass_rate,
                        repetitions=repetitions,
                        mean_latency_ms=self._optional_float(
                            case.get("mean_latency_ms")
                        ),
                    ),
                    cases=(case_id,),
                    limitations=limitations,
                )
            )
        total_cases = self._integer(
            summary.get("total_cases"),
            default=len(capabilities),
        )
        passed_cases = self._integer(summary.get("passed_cases"), default=0)
        failed_cases = self._integer(
            summary.get("failed_cases"),
            default=max(0, total_cases - passed_cases),
        )
        outcome = self._outcome(passed_cases, failed_cases)
        benchmark_metrics = CapabilityMetrics(
            calls=self._integer(summary.get("total_calls"), default=0),
            cases=total_cases,
            passed_cases=passed_cases,
            failed_cases=failed_cases,
            pass_rate=passed_cases / total_cases if total_cases else 0.0,
            repetitions=self._config_integer(
                config.parameters,
                "repetitions",
                default=0,
            ),
            mean_latency_ms=self._nested_float(
                summary,
                "latency_ms",
                "mean",
            ),
            p95_latency_ms=self._nested_float(
                summary,
                "latency_ms",
                "p95",
            ),
        )
        report_artifact, report_sha256 = self._report_metadata(run_dir)
        evidence = BenchmarkEvidence(
            benchmark_id=BOUNDED_BENCHMARK_VERSION,
            run_id=run_dir.name,
            kind=BenchmarkEvidenceKind.BOUNDED,
            artifact=artifact_ref,
            artifact_sha256=artifact_hash,
            timestamp=self._timestamp(summary, manifest),
            configuration_hash=config.configuration_hash,
            outcome=outcome,
            metrics=benchmark_metrics,
            configuration=config,
            cases=tuple(
                item
                for capability in capabilities
                for item in capability.cases
            ),
            limitations=limitations,
            report_artifact=report_artifact,
            report_sha256=report_sha256,
            artifact_hashes=self._run_artifact_hashes(run_dir),
            declared_hash_verified=sidecar_verified,
        )
        return self._loaded_result(
            run_dir=run_dir,
            manifest=manifest,
            summary=summary,
            evidence=evidence,
            capabilities=tuple(capabilities),
            limitations=limitations,
        )

    def _load_stateful(
        self,
        run_dir: Path,
        manifest: Mapping[str, Any],
        summary: Mapping[str, Any],
        profile: Mapping[str, Any],
    ) -> LoadedBenchmarkResult:
        model = self._required_text(summary.get("model"), "summary.model")
        declared_hash = self._consistent_declared_hash(
            profile.get("configuration_hash"),
            summary.get("configuration_hash"),
            manifest.get("configuration_hash"),
        )
        provider = self._provider(run_dir, manifest, summary)
        config = self._configuration(
            raw=(
                summary.get("configuration")
                or manifest.get("configuration")
                or {}
            ),
            model=model,
            provider=provider,
            declared_hash=declared_hash,
            stateful=True,
        )
        artifact = run_dir / "capability_profile.json"
        artifact_ref = self._artifact_ref(artifact)
        artifact_hash = self._sha256_file(artifact)
        self._validate_declared_artifact_hashes(
            run_dir,
            manifest,
        )
        run_limitations = self._limitations(
            summary.get("limitations") or (),
            self._artifact_ref(run_dir / "summary.json"),
        )
        scenario_map: dict[str, list[str]] = {}
        for scenario in manifest.get("scenarios") or ():
            if not isinstance(scenario, Mapping):
                continue
            capability_name = str(scenario.get("capability") or "").strip()
            scenario_id = str(scenario.get("scenario_id") or "").strip()
            if capability_name and scenario_id:
                scenario_map.setdefault(capability_name, []).append(scenario_id)
        capabilities: list[LoadedCapabilityResult] = []
        seen_capabilities: set[str] = set()
        for item in profile.get("capabilities") or ():
            if not isinstance(item, Mapping):
                raise BenchmarkArtifactError(
                    f"Capability invalida em {artifact_ref}."
                )
            raw_capability = self._required_text(
                item.get("capability"),
                "capability_profile.capability",
            )
            if raw_capability in seen_capabilities:
                raise BenchmarkArtifactError(
                    "Capability duplicada em "
                    f"{artifact_ref}: {raw_capability}."
                )
            seen_capabilities.add(raw_capability)
            capability_id = canonical_capability_id(raw_capability)
            status = self._capability_status(item.get("status"))
            total_cases = self._integer(item.get("total_cases"), default=0)
            passed_cases = self._integer(item.get("passed_cases"), default=0)
            failed_cases = self._integer(item.get("failed_cases"), default=0)
            item_limitations = self._limitations(
                item.get("limitations") or (),
                artifact_ref,
            )
            limitations = self._unique_limitations(
                item_limitations + run_limitations
            )
            context_range = item.get("context_range")
            capabilities.append(
                LoadedCapabilityResult(
                    capability_id=capability_id,
                    status=status,
                    confidence=self._confidence(item.get("confidence")),
                    metrics=CapabilityMetrics(
                        calls=self._integer(
                            item.get("total_calls"),
                            default=0,
                        ),
                        cases=total_cases,
                        passed_cases=passed_cases,
                        failed_cases=failed_cases,
                        pass_rate=(
                            passed_cases / total_cases
                            if total_cases
                            else 0.0
                        ),
                        repetitions=self._integer(
                            item.get("repetitions"),
                            default=0,
                        ),
                        mean_latency_ms=self._optional_float(
                            item.get("mean_latency_ms")
                        ),
                        p95_latency_ms=self._optional_float(
                            item.get("p95_latency_ms")
                        ),
                        context_range=self._context_range(context_range),
                    ),
                    cases=tuple(sorted(scenario_map.get(raw_capability, ()))),
                    limitations=limitations,
                )
            )
        total_cases = self._integer(
            summary.get("scenario_repetitions"),
            default=0,
        )
        passed_cases = self._integer(
            summary.get("passed_repetitions"),
            default=0,
        )
        failed_cases = self._integer(
            summary.get("failed_repetitions"),
            default=max(0, total_cases - passed_cases),
        )
        performance = summary.get("performance")
        if not isinstance(performance, Mapping):
            performance = {}
        latency = performance.get("latency_ms")
        if not isinstance(latency, Mapping):
            latency = {}
        report_artifact, report_sha256 = self._report_metadata(run_dir)
        evidence = BenchmarkEvidence(
            benchmark_id=STATEFUL_BENCHMARK_VERSION,
            run_id=run_dir.name,
            kind=BenchmarkEvidenceKind.STATEFUL,
            artifact=artifact_ref,
            artifact_sha256=artifact_hash,
            timestamp=self._timestamp(summary, manifest),
            configuration_hash=config.configuration_hash,
            outcome=self._outcome(passed_cases, failed_cases),
            metrics=CapabilityMetrics(
                calls=self._integer(summary.get("model_calls"), default=0),
                cases=total_cases,
                passed_cases=passed_cases,
                failed_cases=failed_cases,
                pass_rate=(
                    passed_cases / total_cases if total_cases else 0.0
                ),
                repetitions=self._config_integer(
                    config.parameters,
                    "repetitions",
                    default=0,
                ),
                mean_latency_ms=self._optional_float(latency.get("mean")),
                p95_latency_ms=self._optional_float(latency.get("p95")),
            ),
            configuration=config,
            cases=tuple(
                sorted(
                    str(item.get("scenario_id"))
                    for item in manifest.get("scenarios") or ()
                    if isinstance(item, Mapping)
                    and item.get("scenario_id")
                )
            ),
            limitations=run_limitations,
            decision=str(summary.get("decision") or ""),
            report_artifact=report_artifact,
            report_sha256=report_sha256,
            artifact_hashes=self._run_artifact_hashes(run_dir),
            declared_hash_verified=True,
        )
        return self._loaded_result(
            run_dir=run_dir,
            manifest=manifest,
            summary=summary,
            evidence=evidence,
            capabilities=tuple(capabilities),
            limitations=run_limitations,
        )

    def _load_provider_diagnostic(
        self,
        run_dir: Path,
        manifest: Mapping[str, Any],
        summary: Mapping[str, Any],
        diagnostic_version: str,
    ) -> LoadedBenchmarkResult | None:
        raw_config = (
            summary.get("configuration")
            or manifest.get("configuration")
            or {}
        )
        model = str(summary.get("model") or "").strip()
        if not model and isinstance(raw_config, Mapping):
            model = str(raw_config.get("model") or "").strip()
        if not model:
            if self.strict:
                raise BenchmarkArtifactError(
                    f"Provider diagnostic sem model: {run_dir}."
                )
            return None
        config = self._configuration(
            raw=raw_config,
            model=model,
            provider="ollama",
            declared_hash="",
            stateful=False,
        )
        artifact = (
            run_dir / "summary.json"
            if (run_dir / "summary.json").exists()
            else run_dir / "manifest.json"
        )
        artifact_ref = self._artifact_ref(artifact)
        matrix = summary.get("matrix_statuses")
        if not isinstance(matrix, Mapping):
            matrix = {}
        cases = tuple(sorted(str(key) for key in matrix))
        passed = sum(
            1
            for status in matrix.values()
            if str(status).upper() in {"SUCCEEDED", "ALIAS_CONFIRMED"}
        )
        metrics = CapabilityMetrics(
            calls=len(cases),
            cases=len(cases),
            passed_cases=passed,
            failed_cases=max(0, len(cases) - passed),
            pass_rate=passed / len(cases) if cases else 0.0,
            repetitions=1 if cases else 0,
        )
        report_artifact, report_sha256 = self._report_metadata(run_dir)
        evidence = BenchmarkEvidence(
            benchmark_id=diagnostic_version,
            run_id=run_dir.name,
            kind=BenchmarkEvidenceKind.PROVIDER_DIAGNOSTIC,
            artifact=artifact_ref,
            artifact_sha256=self._sha256_file(artifact),
            timestamp=self._timestamp(summary, manifest),
            configuration_hash=config.configuration_hash,
            outcome=BenchmarkOutcome.DIAGNOSTIC,
            metrics=metrics,
            configuration=config,
            cases=cases,
            decision=str(summary.get("decision") or ""),
            report_artifact=report_artifact,
            report_sha256=report_sha256,
            artifact_hashes=self._run_artifact_hashes(run_dir),
            declared_hash_verified=self._validate_declared_artifact_hashes(
                run_dir,
                manifest,
            ),
        )
        return self._loaded_result(
            run_dir=run_dir,
            manifest=manifest,
            summary=summary,
            evidence=evidence,
            capabilities=(),
            limitations=(),
        )

    def _loaded_result(
        self,
        *,
        run_dir: Path,
        manifest: Mapping[str, Any],
        summary: Mapping[str, Any],
        evidence: BenchmarkEvidence,
        capabilities: tuple[LoadedCapabilityResult, ...],
        limitations: tuple[CapabilityLimitation, ...],
    ) -> LoadedBenchmarkResult:
        metadata = self._model_metadata(run_dir, manifest, summary)
        return LoadedBenchmarkResult(
            evidence=evidence,
            model_name=evidence.configuration.model,
            provider=evidence.configuration.provider,
            architecture=metadata["architecture"],
            parameter_count=metadata["parameter_count"],
            quantization=metadata["quantization"],
            context_length=metadata["context_length"],
            advertised_features=metadata["advertised_features"],
            capabilities=capabilities,
            configurations=(evidence.configuration,),
            limitations=limitations,
        )

    def _configuration(
        self,
        *,
        raw: Any,
        model: str,
        provider: str,
        declared_hash: str,
        stateful: bool,
    ) -> CapabilityConfiguration:
        if not isinstance(raw, Mapping):
            raise BenchmarkArtifactError("Configuracao deve ser um objeto.")
        parameters = {
            str(key): value
            for key, value in raw.items()
        }
        configured_model = str(parameters.get("model") or "").strip()
        if configured_model and configured_model != model:
            raise BenchmarkArtifactError(
                "Modelo da configuracao difere do modelo do benchmark: "
                f"{configured_model!r} != {model!r}."
            )
        hash_payload = dict(parameters)
        if stateful:
            hash_payload.pop("output_dir", None)
            hash_payload.pop("debug_prompts", None)
        computed_hash = sha256_json(hash_payload)
        if declared_hash:
            normalized = declared_hash.strip().lower()
            if normalized != computed_hash:
                raise BenchmarkHashMismatchError(
                    "configuration_hash nao corresponde a configuracao "
                    f"em {model}: esperado={normalized}, atual={computed_hash}."
                )
            configuration_hash = normalized
        else:
            configuration_hash = computed_hash
        return CapabilityConfiguration(
            configuration_hash=configuration_hash,
            model=model,
            provider=provider,
            mode=str(parameters.get("mode") or ""),
            context_tokens=self._optional_integer(
                parameters.get("context_tokens")
            ),
            max_output_tokens=self._optional_integer(
                parameters.get("max_output_tokens")
                if "max_output_tokens" in parameters
                else parameters.get("output_tokens")
            ),
            temperature=self._optional_float(parameters.get("temperature")),
            top_p=self._optional_float(parameters.get("top_p")),
            thinking=self._optional_bool(
                parameters.get("think")
                if "think" in parameters
                else parameters.get("thinking")
            ),
            streaming=self._optional_bool(
                parameters.get("stream")
                if "stream" in parameters
                else parameters.get("streaming")
            ),
            timeout_seconds=self._optional_float(
                parameters.get("timeout_seconds")
            ),
            seed=self._optional_integer(parameters.get("seed")),
            parameters=parameters,
        )

    def _model_metadata(
        self,
        run_dir: Path,
        manifest: Mapping[str, Any],
        summary: Mapping[str, Any],
    ) -> dict[str, Any]:
        runtime = summary.get("runtime")
        if isinstance(runtime, Mapping) and isinstance(
            runtime.get("before"),
            Mapping,
        ):
            runtime = runtime.get("before")
        if not isinstance(runtime, Mapping):
            runtime = manifest.get("runtime_before") or manifest.get("runtime")
        if not isinstance(runtime, Mapping):
            runtime = {}
        model_info = runtime.get("model_info")
        if not isinstance(model_info, Mapping):
            model_info = {}
        list_entry = runtime.get("model_list_entry")
        if not isinstance(list_entry, Mapping):
            list_entry = {}
        details = list_entry.get("details")
        if not isinstance(details, Mapping):
            details = runtime.get("model_details")
        if not isinstance(details, Mapping):
            details = {}
        architecture = str(
            model_info.get("general.architecture")
            or details.get("family")
            or ""
        )
        parameter_count = self._optional_integer(
            model_info.get("general.parameter_count")
        )
        context_length = self._optional_integer(
            details.get("context_length")
            or model_info.get(f"{architecture}.context_length")
        )
        advertised = runtime.get("model_capabilities")
        if not advertised:
            advertised = list_entry.get("capabilities")
        return {
            "architecture": architecture,
            "parameter_count": parameter_count,
            "quantization": str(details.get("quantization_level") or ""),
            "context_length": context_length,
            "advertised_features": tuple(
                sorted(
                    {
                        str(item).strip().lower()
                        for item in advertised or ()
                        if str(item).strip()
                    }
                )
            ),
        }

    def _provider(
        self,
        run_dir: Path,
        manifest: Mapping[str, Any],
        summary: Mapping[str, Any],
    ) -> str:
        for container in (
            summary.get("config"),
            summary.get("configuration"),
            manifest.get("config"),
            manifest.get("configuration"),
        ):
            if isinstance(container, Mapping) and container.get("provider"):
                return str(container["provider"]).strip().lower()
        runtime = manifest.get("runtime") or manifest.get("runtime_before")
        if isinstance(runtime, Mapping) and runtime.get("ollama_version"):
            return "ollama"
        for response_path in sorted(run_dir.glob("cases/*/rep-*/response.json")):
            response = self._optional_json(response_path)
            provider = str(response.get("provider") or "").strip().lower()
            if provider:
                return provider
        return ""

    def _run_format(self, run_dir: Path) -> str | None:
        manifest = self._optional_json(run_dir / "manifest.json")
        summary = self._optional_json(run_dir / "summary.json")
        profile = self._optional_json(run_dir / "capability_profile.json")
        version = str(
            summary.get("benchmark_version")
            or profile.get("benchmark_version")
            or manifest.get("benchmark_version")
            or summary.get("diagnostic_version")
            or manifest.get("diagnostic_version")
            or ""
        ).strip()
        if version in {BOUNDED_BENCHMARK_VERSION, STATEFUL_BENCHMARK_VERSION}:
            return version
        if version.startswith(PROVIDER_DIAGNOSTIC_PREFIX):
            return version
        return None

    @staticmethod
    def _assert_versions(
        expected: str,
        *,
        manifest: Mapping[str, Any],
        summary: Mapping[str, Any],
        profile: Mapping[str, Any],
    ) -> None:
        observed = {
            str(value).strip()
            for container in (manifest, summary, profile)
            for value in (
                container.get("benchmark_version"),
                container.get("diagnostic_version"),
            )
            if str(value or "").strip()
        }
        if observed != {expected}:
            raise BenchmarkArtifactError(
                "Versoes divergentes no mesmo run: "
                f"esperado={expected}, observadas={sorted(observed)}."
            )

    @staticmethod
    def _consistent_declared_hash(*values: Any) -> str:
        observed = {
            str(value).strip().lower()
            for value in values
            if str(value or "").strip()
        }
        if not observed:
            raise BenchmarkArtifactError(
                "configuration_hash e obrigatorio."
            )
        if len(observed) != 1:
            raise BenchmarkHashMismatchError(
                f"configuration_hash divergente: {sorted(observed)}."
            )
        return next(iter(observed))

    def _validate_declared_artifact_hashes(
        self,
        run_dir: Path,
        manifest: Mapping[str, Any],
    ) -> bool:
        declared = manifest.get("artifact_hashes")
        if not isinstance(declared, Mapping) or not declared:
            return False
        for relative_path, value in declared.items():
            expected = (
                value.get("sha256")
                if isinstance(value, Mapping)
                else value
            )
            expected_text = str(expected or "").strip().lower()
            path = (run_dir / str(relative_path)).resolve()
            try:
                path.relative_to(run_dir.resolve())
            except ValueError as exc:
                raise BenchmarkArtifactError(
                    f"Hash declarado fora do run: {relative_path}."
                ) from exc
            if not path.is_file():
                raise BenchmarkArtifactError(
                    f"Artefacto com hash declarado nao existe: {path}."
                )
            actual = self._sha256_file(path)
            if actual != expected_text:
                raise BenchmarkHashMismatchError(
                    f"Hash invalido para {path}: "
                    f"esperado={expected_text}, atual={actual}."
                )
        return True

    def _artifact_ref(self, path: Path) -> str:
        resolved = path.resolve()
        try:
            return resolved.relative_to(self.source_root).as_posix()
        except ValueError as exc:
            raise BenchmarkArtifactError(
                f"Artefacto fora de source_root: {resolved}."
            ) from exc

    def _report_metadata(self, run_dir: Path) -> tuple[str, str]:
        path = run_dir / "REPORT.md"
        if not path.is_file():
            return "", ""
        return self._artifact_ref(path), self._sha256_file(path)

    def _run_artifact_hashes(self, run_dir: Path) -> dict[str, str]:
        paths = (
            run_dir / "manifest.json",
            run_dir / "summary.json",
            run_dir / "capability_profile.json",
            run_dir / "REPORT.md",
        )
        return {
            self._artifact_ref(path): self._sha256_file(path)
            for path in paths
            if path.is_file()
        }

    @staticmethod
    def _optional_json(path: Path) -> dict[str, Any]:
        if not path.is_file():
            return {}
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise BenchmarkArtifactError(
                f"JSON de benchmark invalido: {path}: {exc}"
            ) from exc
        if not isinstance(value, dict):
            raise BenchmarkArtifactError(
                f"Artefacto deve conter objeto JSON: {path}."
            )
        return value

    @staticmethod
    def _sha256_file(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _timestamp(
        summary: Mapping[str, Any],
        manifest: Mapping[str, Any],
    ) -> str:
        value = (
            summary.get("completed_at")
            or summary.get("started_at")
            or manifest.get("created_at")
            or manifest.get("started_at")
        )
        raw = BenchmarkLoader._required_text(value, "benchmark timestamp")
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError as exc:
            raise BenchmarkArtifactError(
                f"Timestamp de benchmark invalido: {raw!r}."
            ) from exc
        if parsed.utcoffset() is None:
            raise BenchmarkArtifactError(
                f"Timestamp de benchmark sem timezone: {raw!r}."
            )
        return parsed.astimezone(timezone.utc).isoformat()

    @staticmethod
    def _required_text(value: Any, field_name: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise BenchmarkArtifactError(f"{field_name} e obrigatorio.")
        return normalized

    @staticmethod
    def _integer(value: Any, *, default: int) -> int:
        if value is None:
            return default
        if isinstance(value, bool):
            raise BenchmarkArtifactError("Inteiro de benchmark invalido.")
        try:
            return int(value)
        except (TypeError, ValueError) as exc:
            raise BenchmarkArtifactError(
                f"Inteiro de benchmark invalido: {value!r}."
            ) from exc

    @staticmethod
    def _optional_integer(value: Any) -> int | None:
        if value is None or value == "":
            return None
        return BenchmarkLoader._integer(value, default=0)

    @staticmethod
    def _optional_float(value: Any) -> float | None:
        if value is None or value == "":
            return None
        if isinstance(value, bool):
            raise BenchmarkArtifactError("Float de benchmark invalido.")
        try:
            return float(value)
        except (TypeError, ValueError) as exc:
            raise BenchmarkArtifactError(
                f"Float de benchmark invalido: {value!r}."
            ) from exc

    @staticmethod
    def _optional_bool(value: Any) -> bool | None:
        if value is None:
            return None
        if isinstance(value, bool):
            return value
        raise BenchmarkArtifactError(f"Booleano de benchmark invalido: {value!r}.")

    @staticmethod
    def _confidence(value: Any) -> float:
        result = BenchmarkLoader._optional_float(value)
        if result is None or not 0.0 <= result <= 1.0:
            raise BenchmarkArtifactError(
                f"Confidence de benchmark invalida: {value!r}."
            )
        return result

    @staticmethod
    def _capability_status(value: Any) -> CapabilityStatus:
        normalized = str(value or "").strip().upper()
        try:
            return CapabilityStatus(normalized)
        except ValueError as exc:
            raise BenchmarkArtifactError(
                f"Capability status invalido: {normalized or '<vazio>'}."
            ) from exc

    @staticmethod
    def _context_range(value: Any) -> tuple[int, int] | None:
        if not isinstance(value, (tuple, list)) or len(value) != 2:
            return None
        return (
            BenchmarkLoader._integer(value[0], default=0),
            BenchmarkLoader._integer(value[1], default=0),
        )

    @staticmethod
    def _outcome(passed: int, failed: int) -> BenchmarkOutcome:
        if passed > 0 and failed == 0:
            return BenchmarkOutcome.PASSED
        if passed > 0 and failed > 0:
            return BenchmarkOutcome.DEGRADED
        if failed > 0:
            return BenchmarkOutcome.FAILED
        return BenchmarkOutcome.UNKNOWN

    @staticmethod
    def _nested_float(
        value: Mapping[str, Any],
        container: str,
        key: str,
    ) -> float | None:
        nested = value.get(container)
        if not isinstance(nested, Mapping):
            return None
        return BenchmarkLoader._optional_float(nested.get(key))

    @staticmethod
    def _config_integer(
        parameters: Mapping[str, Any],
        key: str,
        *,
        default: int,
    ) -> int:
        return BenchmarkLoader._integer(parameters.get(key), default=default)

    @staticmethod
    def _limitations(
        values: Any,
        source_artifact: str,
    ) -> tuple[CapabilityLimitation, ...]:
        limitations: list[CapabilityLimitation] = []
        for value in values or ():
            description = str(value or "").strip()
            if not description:
                continue
            code_hash = hashlib.sha256(
                description.encode("utf-8")
            ).hexdigest()[:12].upper()
            limitations.append(
                CapabilityLimitation(
                    code=f"BENCHMARK_LIMITATION_{code_hash}",
                    description=description,
                    severity=LimitationSeverity.WARNING,
                    source_artifact=source_artifact,
                )
            )
        return BenchmarkLoader._unique_limitations(tuple(limitations))

    @staticmethod
    def _unique_limitations(
        values: tuple[CapabilityLimitation, ...],
    ) -> tuple[CapabilityLimitation, ...]:
        by_key = {
            (
                item.code,
                item.description,
                item.source_artifact,
            ): item
            for item in values
        }
        return tuple(
            by_key[key]
            for key in sorted(by_key)
        )
