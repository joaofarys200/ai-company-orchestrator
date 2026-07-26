from __future__ import annotations

import asyncio
import copy
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import time
import traceback
import uuid
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlparse

import httpx
from jsonschema import Draft202012Validator

from backend.model_harness import (
    EnumConstraint,
    ExecutionConstraints,
    ExpectedOutput,
    ModelHarness,
    ModelPreferences,
    ModelRequest,
    ModelResponseStatus,
    ModelRoute,
    OutputFormat,
    ProviderRegistry,
    ReferenceConstraint,
)
from backend.model_harness.benchmarking.contracts import (
    BenchmarkMode,
    StatefulContext,
    sha256_json,
    to_jsonable,
)
from backend.model_harness.benchmarking.runner import (
    DECISION_VALUES,
    STOP_VALUES,
    build_step_context,
    build_step_prompt,
    decision_schema,
)
from backend.model_harness.benchmarking.scenarios import (
    BENCHMARK_VERSION,
    benchmark_scenarios,
    fixture_catalog_hash,
)
from backend.model_harness.benchmarking.tools import (
    create_read_only_tool_registry,
)
from scripts.model_harness_benchmark import (
    BenchmarkConfig as OllamaConfig,
    OllamaBenchmarkProvider,
    command_output,
    nvidia_snapshot,
    sha256_file,
    tree_integrity,
)


DIAGNOSTIC_VERSION = "stateful_provider_path_diagnostic_v1"
REPO_ROOT = Path(__file__).resolve().parents[3]
DIAGNOSTIC_ROOT = (
    REPO_ROOT / "diagnostics" / "model_harness_provider_diagnostic"
)
DEFAULT_STATEFUL_RUN = (
    REPO_ROOT
    / "diagnostics"
    / "model_harness_benchmark"
    / "20260725-204739-stateful-smoke"
)
DEFAULT_V1_RUN = (
    REPO_ROOT
    / "diagnostics"
    / "model_harness_benchmark"
    / "20260725-184843-qwen35-9b"
)
DEFAULT_SCENARIO = "A01_FIND_RELEVANT_FILE"
DEFAULT_V1_CASE = "B07_TOOL_SELECTION"
TIMELINE_STAGES = (
    ("T00", "diagnostic_start"),
    ("T01", "scenario_loaded"),
    ("T02", "context_built"),
    ("T03", "request_constructed"),
    ("T04", "profile_resolved"),
    ("T05", "route_resolved"),
    ("T06", "schema_generated"),
    ("T07", "schema_normalized"),
    ("T08", "payload_serialized"),
    ("T09", "provider_call_started"),
    ("T10", "dns_or_endpoint_resolved"),
    ("T11", "tcp_connected"),
    ("T12", "request_headers_sent"),
    ("T13", "request_body_sent"),
    ("T14", "response_headers_received"),
    ("T15", "first_byte_received"),
    ("T16", "first_chunk_received"),
    ("T17", "first_token_observed"),
    ("T18", "response_completed"),
    ("T19", "parsing_started"),
    ("T20", "parsing_completed"),
    ("T21", "validation_completed"),
    ("T22", "recovery_decided"),
    ("T23", "diagnostic_completed"),
)
STAGE_BY_NAME = {name: code for code, name in TIMELINE_STAGES}
STAGE_NAMES = {code: name for code, name in TIMELINE_STAGES}
INTEGRITY_TREES = {
    "workspace_projects": REPO_ROOT / "workspace" / "projects",
    "mission_metadata": REPO_ROOT / "workspace" / ".jarvis",
    "chroma_collections": REPO_ROOT / "chroma_db",
    "frontend_source": REPO_ROOT / "frontend" / "src",
}
CRITICAL_FILES = (
    "backend/model_harness/contracts.py",
    "backend/model_harness/context_builder.py",
    "backend/model_harness/harness.py",
    "backend/model_harness/profiles.py",
    "backend/model_harness/provider.py",
    "backend/model_harness/recovery.py",
    "backend/model_harness/router.py",
    "backend/model_harness/validation.py",
    "backend/model_harness/benchmarking/runner.py",
    "scripts/model_harness_benchmark.py",
    "scripts/model_harness_stateful_benchmark.py",
    "agents/orchestrator/project_builder.py",
    "agents/mission_state.py",
    "agents/mission_executor.py",
    "agents/mission_autonomy.py",
    "agents/executors/registry.py",
    "intelligence/coding_session.py",
)
SECRET_KEY = re.compile(
    r"^(api[_-]?key|authorization|token|access[_-]?token|"
    r"refresh[_-]?token|auth[_-]?token|secret|password|credential)$",
    re.IGNORECASE,
)
WINDOWS_PATH = re.compile(r"[A-Za-z]:\\(?:[^\\\s\"']+\\)*[^\\\s\"']*")
BEARER_VALUE = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        to_jsonable(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def wire_json_bytes(value: Any, *, url: str = "http://localhost/") -> bytes:
    return httpx.Request("POST", url, json=value).content


def redact_text(value: str) -> str:
    text = BEARER_VALUE.sub("Bearer [REDACTED]", str(value))
    text = WINDOWS_PATH.sub("[LOCAL_PATH]", text)
    text = re.sub(
        r"(?i)(api[_-]?key|token|secret|password)\s*[=:]\s*\S+",
        r"\1=[REDACTED]",
        text,
    )
    return text[:2_000]


def redact_mapping(value: Any) -> Any:
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for key, item in value.items():
            normalized = str(key)
            if SECRET_KEY.search(normalized):
                result[normalized] = "[REDACTED]"
            else:
                result[normalized] = redact_mapping(item)
        return result
    if isinstance(value, (list, tuple)):
        return [redact_mapping(item) for item in value]
    if isinstance(value, str):
        return redact_text(value)
    return value


@dataclass(frozen=True)
class DiagnosticConfig:
    scenario: str = DEFAULT_SCENARIO
    model: str = "qwen3.5:9b"
    base_url: str = "http://127.0.0.1:11434"
    timeout_seconds: float = 300.0
    output_dir: Path = DIAGNOSTIC_ROOT / "pending"
    mode: str = "exact"
    keep_alive: str = "15m"
    debug_payload: bool = False
    capture_ollama_logs: bool = False
    compare_v1: bool = False
    direct_ollama: bool = False
    reset_model_between_variants: bool = False
    stream_probe_only: bool = False
    context_tokens: int = 8_192
    max_output_tokens: int = 1_024
    temperature: float = 0.0
    top_p: float = 0.8
    seed: int = 42
    think: bool = False
    stream: bool = False

    def __post_init__(self) -> None:
        if self.mode not in {"exact", "matrix", "compare"}:
            raise ValueError(f"Unsupported diagnostic mode: {self.mode}")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout must be positive")
        if self.context_tokens <= 0 or self.max_output_tokens <= 0:
            raise ValueError("token limits must be positive")
        assert_output_location(self.output_dir)

    def ollama_config(self) -> OllamaConfig:
        return OllamaConfig(
            model=self.model,
            base_url=self.base_url,
            context_tokens=self.context_tokens,
            output_tokens=self.max_output_tokens,
            temperature=self.temperature,
            top_p=self.top_p,
            seed=self.seed,
            think=self.think,
            stream=self.stream,
            repetitions=1,
            keep_alive=self.keep_alive,
            timeout_seconds=self.timeout_seconds,
        )


@dataclass
class Timeline:
    correlation_id: str
    variant_id: str
    started_ns: int = field(default_factory=time.monotonic_ns)
    events: dict[str, dict[str, Any]] = field(default_factory=dict)

    def observe(
        self,
        stage: str,
        *,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        code = self._stage_code(stage)
        if code in self.events:
            return
        now_ns = time.monotonic_ns()
        self.events[code] = {
            "correlation_id": self.correlation_id,
            "variant_id": self.variant_id,
            "stage": code,
            "name": STAGE_NAMES[code],
            "status": "OBSERVED",
            "utc": utc_now(),
            "monotonic_ns": now_ns,
            "elapsed_ms": round((now_ns - self.started_ns) / 1_000_000, 3),
            "details": redact_mapping(dict(details or {})),
        }

    def unavailable(self, stage: str, reason: str) -> None:
        code = self._stage_code(stage)
        if code in self.events:
            return
        self.events[code] = {
            "correlation_id": self.correlation_id,
            "variant_id": self.variant_id,
            "stage": code,
            "name": STAGE_NAMES[code],
            "status": "NOT_OBSERVABLE",
            "utc": utc_now(),
            "monotonic_ns": None,
            "elapsed_ms": None,
            "details": {"reason": redact_text(reason)},
        }

    def finalized(self) -> list[dict[str, Any]]:
        for code, name in TIMELINE_STAGES:
            if code not in self.events:
                self.unavailable(
                    code,
                    f"{name} was not reached or is unavailable in this path",
                )
        return [self.events[code] for code, _ in TIMELINE_STAGES]

    @staticmethod
    def _stage_code(stage: str) -> str:
        if stage in STAGE_NAMES:
            return stage
        if stage in STAGE_BY_NAME:
            return STAGE_BY_NAME[stage]
        raise KeyError(f"Unknown timeline stage: {stage}")


@dataclass(frozen=True)
class RequestBundle:
    scenario_id: str
    request: ModelRequest
    resolved_request: ModelRequest
    route: ModelRoute
    schema: dict[str, Any]
    payload: dict[str, Any]
    payload_bytes: bytes
    context_hash: str
    source_manifest: Mapping[str, Any]
    reconstruction: Mapping[str, Any]


@dataclass(frozen=True)
class MatrixVariant:
    variant_id: str
    title: str
    payload: Mapping[str, Any] | None
    schema: Mapping[str, Any] | None
    execution_path: str
    changed_dimension: str
    expected_equivalence: str = ""
    request: ModelRequest | None = field(
        default=None,
        repr=False,
        compare=False,
    )


@dataclass
class HttpCallResult:
    variant_id: str
    status: str
    execution_path: str
    duration_ms: float
    status_code: int | None = None
    response_bytes: int = 0
    response_sha256: str = ""
    model_content_chars: int = 0
    model_content_sha256: str = ""
    done: bool | None = None
    done_reason: str = ""
    input_tokens: int | None = None
    output_tokens: int | None = None
    json_valid: bool | None = None
    schema_valid: bool | None = None
    partial_response: bool = False
    exception: dict[str, Any] | None = None
    timeline: list[dict[str, Any]] = field(default_factory=list)
    payload_sha256: str = ""
    payload_bytes: int = 0
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def assert_output_location(path: Path) -> None:
    resolved = path.resolve()
    allowed = DIAGNOSTIC_ROOT.resolve()
    try:
        common = os.path.commonpath((str(allowed), str(resolved)))
    except ValueError as exc:
        raise ValueError(
            "Diagnostic output must stay below its dedicated root."
        ) from exc
    if common != str(allowed) or resolved == allowed:
        raise ValueError(
            "Diagnostic output must be a run directory below "
            "diagnostics/model_harness_provider_diagnostic."
        )


def _relative_trace_path(filename: str) -> str:
    path = Path(filename)
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except (OSError, ValueError):
        return path.name


def exception_record(
    exc: BaseException,
    *,
    stage: str,
    correlation_id: str,
    variant_id: str,
) -> dict[str, Any]:
    causes: list[dict[str, Any]] = []
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        message = str(current)
        causes.append({
            "class": type(current).__name__,
            "module": type(current).__module__,
            "message_redacted": redact_text(message),
            "message_sha256": sha256_text(message),
            "errno": getattr(current, "errno", None),
            "status_http": (
                getattr(getattr(current, "response", None), "status_code", None)
            ),
        })
        current = (
            current.__cause__
            if current.__cause__ is not None
            else current.__context__
        )
    frames = []
    for frame in traceback.extract_tb(exc.__traceback__):
        frames.append({
            "file": _relative_trace_path(frame.filename),
            "line": frame.lineno,
            "function": frame.name,
        })
    return {
        "correlation_id": correlation_id,
        "variant_id": variant_id,
        "classification": classify_exception(exc),
        "class": type(exc).__name__,
        "module": type(exc).__module__,
        "stage": stage,
        "timeout_type": _timeout_type(exc),
        "errno": getattr(exc, "errno", None),
        "status_http": getattr(
            getattr(exc, "response", None),
            "status_code",
            None,
        ),
        "message_redacted": redact_text(str(exc)),
        "message_sha256": sha256_text(str(exc)),
        "causes": causes,
        "traceback": frames,
    }


def _timeout_type(exc: BaseException) -> str:
    if isinstance(exc, httpx.ConnectTimeout):
        return "connect"
    if isinstance(exc, httpx.ReadTimeout):
        return "read"
    if isinstance(exc, httpx.WriteTimeout):
        return "write"
    if isinstance(exc, httpx.PoolTimeout):
        return "pool"
    if isinstance(exc, (TimeoutError, asyncio.TimeoutError)):
        return "total"
    return ""


def classify_exception(exc: BaseException) -> str:
    if isinstance(exc, httpx.ConnectTimeout):
        return "CONNECT_TIMEOUT"
    if isinstance(exc, httpx.ReadTimeout):
        return "READ_TIMEOUT"
    if isinstance(exc, httpx.WriteTimeout):
        return "WRITE_TIMEOUT"
    if isinstance(exc, httpx.PoolTimeout):
        return "POOL_TIMEOUT"
    if isinstance(exc, (TimeoutError, asyncio.TimeoutError)):
        return "TOTAL_TIMEOUT"
    if isinstance(exc, httpx.HTTPStatusError):
        status = getattr(exc.response, "status_code", 0)
        return "OLLAMA_SERVER_ERROR" if status >= 500 else "HTTP_ERROR"
    if isinstance(exc, httpx.RemoteProtocolError):
        return "CLIENT_PROTOCOL_ERROR"
    if isinstance(exc, httpx.ConnectError):
        text = str(exc).casefold()
        if "reset" in text:
            return "CONNECTION_RESET"
        return "HTTP_ERROR"
    if isinstance(exc, (json.JSONDecodeError, ValueError)):
        return "PARSING_ERROR"
    if isinstance(exc, TypeError):
        return "SERIALIZATION_ERROR"
    if exc.__class__.__module__.startswith("jsonschema"):
        return "VALIDATION_ERROR"
    return "UNKNOWN_ERROR"


def integrity_snapshot() -> dict[str, Any]:
    return {
        "captured_at": utc_now(),
        "trees": {
            name: tree_integrity(path)
            for name, path in INTEGRITY_TREES.items()
        },
        "critical_files": {
            relative: _file_integrity(REPO_ROOT / relative)
            for relative in CRITICAL_FILES
        },
        "fixture_catalog_sha256": fixture_catalog_hash(),
    }


def _file_integrity(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"exists": False, "size_bytes": 0, "sha256": ""}
    return {
        "exists": True,
        "size_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def integrity_comparison(
    before: Mapping[str, Any],
    after: Mapping[str, Any],
) -> dict[str, Any]:
    tree_changes: dict[str, Any] = {}
    file_changes: dict[str, Any] = {}
    for name, value in before.get("trees", {}).items():
        later = after.get("trees", {}).get(name)
        if value != later:
            tree_changes[name] = {"before": value, "after": later}
    for name, value in before.get("critical_files", {}).items():
        later = after.get("critical_files", {}).get(name)
        if value != later:
            file_changes[name] = {"before": value, "after": later}
    unchanged = (
        not tree_changes
        and not file_changes
        and before.get("fixture_catalog_sha256")
        == after.get("fixture_catalog_sha256")
    )
    return {
        "before": before,
        "after": after,
        "tree_changes": tree_changes,
        "critical_file_changes": file_changes,
        "unchanged": unchanged,
    }


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected object in {path}")
    return value


def _scenario_by_id(scenario_id: str):
    candidates = benchmark_scenarios(
        BenchmarkMode.STANDARD,
        include_fault_injection=True,
        seed=42,
    )
    try:
        return next(
            item for item in candidates
            if item.scenario_id == scenario_id
        )
    except StopIteration as exc:
        raise ValueError(f"Unknown benchmark scenario: {scenario_id}") from exc


def effective_user_prompt(request: ModelRequest) -> str:
    value = request.user_prompt
    if not request.context.items:
        return value
    context_payload = [
        {
            "source": item.source,
            "kind": item.kind,
            "content": item.content,
            "inclusion_reason": item.inclusion_reason,
        }
        for item in request.context.items
    ]
    return (
        value
        + "\n\nAUTHORITATIVE_CONTEXT:\n"
        + json.dumps(
            context_payload,
            ensure_ascii=False,
            separators=(",", ":"),
        )
    )


def build_provider_payload(
    request: ModelRequest,
    route: ModelRoute,
    config: DiagnosticConfig,
) -> dict[str, Any]:
    expected = request.expected_output
    response_format: str | dict[str, Any] = "json"
    if (
        expected is not None
        and expected.format == OutputFormat.JSON_SCHEMA
        and expected.schema is not None
    ):
        response_format = dict(expected.schema)
    return {
        "model": route.model,
        "messages": [
            {"role": "system", "content": request.system_prompt},
            {"role": "user", "content": effective_user_prompt(request)},
        ],
        "stream": False,
        "format": response_format,
        "think": route.thinking,
        "keep_alive": config.keep_alive,
        "options": {
            "temperature": request.temperature,
            "top_p": config.top_p,
            "seed": config.seed,
            "num_ctx": request.max_context_tokens,
            "num_predict": request.max_output_tokens,
        },
    }


def reconstruct_stateful_request(
    config: DiagnosticConfig,
    timeline: Timeline | None = None,
) -> RequestBundle:
    manifest = _load_json(DEFAULT_STATEFUL_RUN / "manifest.json")
    if timeline is not None:
        timeline.observe("T00", details={"version": DIAGNOSTIC_VERSION})
    scenario = _scenario_by_id(config.scenario)
    if timeline is not None:
        timeline.observe(
            "T01",
            details={
                "scenario_id": scenario.scenario_id,
                "fixture_sha256": scenario.fixture.content_sha256,
            },
        )
    state = StatefulContext(
        objective=scenario.objective,
        constraints=scenario.constraints,
    )
    context, context_hash = build_step_context(
        scenario,
        state,
        create_read_only_tool_registry(),
        max_chars=config.context_tokens * 8,
    )
    if timeline is not None:
        timeline.observe(
            "T02",
            details={
                "context_hash": context_hash,
                "context_chars": context.total_chars,
                "context_items": len(context.items),
            },
        )
    system_prompt, user_prompt = build_step_prompt(scenario, state, 1)
    schema = decision_schema(scenario.available_tools)
    expected = ExpectedOutput(
        format=OutputFormat.JSON_SCHEMA,
        schema=schema,
        enum_constraints=(
            EnumConstraint("$.decision", DECISION_VALUES),
            EnumConstraint("$.tool_name", scenario.available_tools),
            EnumConstraint("$.stop_reason", STOP_VALUES),
        ),
        reference_constraints=(
            ReferenceConstraint(
                "$.evidence_refs",
                (),
                allow_empty=True,
            ),
        ),
    )
    request = ModelRequest(
        task_profile="TOOL_SELECTION",
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        context=context,
        allowed_tools=scenario.available_tools,
        expected_output=expected,
        temperature=config.temperature,
        max_context_tokens=config.context_tokens,
        max_output_tokens=config.max_output_tokens,
        metadata={
            "benchmark_version": BENCHMARK_VERSION,
            "consumer": "stateful_benchmark",
            "scenario": scenario.scenario_id,
            "step": 1,
            "repetition": 1,
            "progress_key": f"{scenario.scenario_id}:1",
        },
        model_preferences=ModelPreferences(
            providers=("ollama",),
            models=(config.model,),
        ),
        execution_constraints=ExecutionConstraints(
            max_attempts=2,
            timeout_seconds=config.timeout_seconds,
            streaming=False,
            thinking=False,
            allow_recovery=True,
            stop_on_no_progress=True,
        ),
    )
    if timeline is not None:
        timeline.observe(
            "T03",
            details={
                "request_fingerprint": request.fingerprint(),
                "allowed_tool_count": len(request.allowed_tools),
            },
        )
    provider = OllamaBenchmarkProvider(config.ollama_config())
    harness = ModelHarness(ProviderRegistry([provider]))
    profile = harness.profiles.get(request.task_profile)
    resolved = harness._apply_profile(request, profile)
    if timeline is not None:
        timeline.observe(
            "T04",
            details={
                "profile": profile.name,
                "validation_pipeline": list(profile.validation_pipeline),
            },
        )
    route = harness.router.route(resolved, profile)
    if timeline is not None:
        timeline.observe("T05", details=asdict(route))
        timeline.observe(
            "T06",
            details={
                "schema_sha256": sha256_json(schema),
                "schema_bytes": len(canonical_json_bytes(schema)),
            },
        )
        timeline.observe(
            "T07",
            details={
                "method": "shallow_dict_copy_in_existing_provider",
                "input_sha256": sha256_json(schema),
                "output_sha256": sha256_json(dict(schema)),
            },
        )
    payload = build_provider_payload(resolved, route, config)
    payload_bytes = wire_json_bytes(
        payload,
        url=config.base_url.rstrip("/") + "/api/chat",
    )
    if timeline is not None:
        timeline.observe(
            "T08",
            details={
                "payload_sha256": sha256_bytes(payload_bytes),
                "payload_bytes": len(payload_bytes),
            },
        )
    historical_step = _first_step_trace(config.scenario)
    reconstruction = {
        "historical_context_hash": historical_step.get("context_hash"),
        "reconstructed_context_hash": context_hash,
        "context_hash_matches": (
            historical_step.get("context_hash") == context_hash
        ),
        "historical_request_fingerprint": historical_step.get(
            "request_fingerprint"
        ),
        "reconstructed_request_fingerprint": request.fingerprint(),
        "request_fingerprint_matches": (
            historical_step.get("request_fingerprint")
            == request.fingerprint()
        ),
        "historical_configuration_hash": manifest.get(
            "configuration_hash"
        ),
        "configuration_equivalent": _configuration_equivalence(
            config,
            manifest.get("configuration") or {},
        ),
    }
    return RequestBundle(
        scenario_id=scenario.scenario_id,
        request=request,
        resolved_request=resolved,
        route=route,
        schema=schema,
        payload=payload,
        payload_bytes=payload_bytes,
        context_hash=context_hash,
        source_manifest=manifest,
        reconstruction=reconstruction,
    )


def _first_step_trace(scenario_id: str) -> dict[str, Any]:
    path = DEFAULT_STATEFUL_RUN / "step_trace.jsonl"
    for line in path.read_text(encoding="utf-8").splitlines():
        value = json.loads(line)
        if (
            value.get("scenario_id") == scenario_id
            and value.get("step_number") == 1
            and value.get("repetition") == 1
        ):
            return value
    raise ValueError(f"Historical trace missing for {scenario_id}")


def _configuration_equivalence(
    config: DiagnosticConfig,
    historical: Mapping[str, Any],
) -> dict[str, Any]:
    current = {
        "model": config.model,
        "base_url": config.base_url,
        "context_tokens": config.context_tokens,
        "max_output_tokens": config.max_output_tokens,
        "seed": config.seed,
        "keep_alive": config.keep_alive,
        "timeout_seconds": config.timeout_seconds,
        "temperature": config.temperature,
        "top_p": config.top_p,
        "think": config.think,
        "stream": config.stream,
    }
    differences = {
        key: {
            "historical": historical.get(key),
            "diagnostic": value,
        }
        for key, value in current.items()
        if historical.get(key) != value
    }
    return {
        "equivalent": not differences,
        "differences": differences,
    }


def load_v1_payload(
    *,
    case_id: str = DEFAULT_V1_CASE,
    run_dir: Path = DEFAULT_V1_RUN,
) -> tuple[dict[str, Any], dict[str, Any]]:
    request_path = run_dir / "cases" / case_id / "rep-1" / "request.json"
    response_path = run_dir / "cases" / case_id / "rep-1" / "response.json"
    if not request_path.is_file():
        case_id = "B01_LOCAL_CHOICE"
        request_path = (
            run_dir / "cases" / case_id / "rep-1" / "request.json"
        )
        response_path = (
            run_dir / "cases" / case_id / "rep-1" / "response.json"
        )
    request = _load_json(request_path)
    response = _load_json(response_path)
    context_items = (request.get("context") or {}).get("items") or []
    user_prompt = str(request.get("user_prompt") or "")
    if context_items:
        context_payload = [
            {
                "source": item["source"],
                "kind": item["kind"],
                "content": item["content"],
                "inclusion_reason": item["inclusion_reason"],
            }
            for item in context_items
        ]
        user_prompt += (
            "\n\nAUTHORITATIVE_CONTEXT:\n"
            + json.dumps(
                context_payload,
                ensure_ascii=False,
                separators=(",", ":"),
            )
        )
    generation = request["generation"]
    payload = {
        "model": generation["model"],
        "messages": [
            {
                "role": "system",
                "content": request["system_prompt"],
            },
            {"role": "user", "content": user_prompt},
        ],
        "stream": False,
        "format": request["schema"],
        "think": generation["think"],
        "keep_alive": generation["keep_alive"],
        "options": {
            "temperature": generation["temperature"],
            "top_p": generation["top_p"],
            "seed": generation["seed"],
            "num_ctx": generation["context_tokens"],
            "num_predict": generation["output_tokens"],
        },
    }
    source = {
        "case_id": case_id,
        "request_artifact": request_path.relative_to(REPO_ROOT).as_posix(),
        "response_status": response.get("status"),
        "response_latency_ms": response.get("latency_ms"),
        "response_validation": (
            response.get("validation") or {}
        ).get("status"),
        "request_fingerprint": request.get("request_fingerprint"),
    }
    return payload, source


def schema_analysis(schema: Mapping[str, Any]) -> dict[str, Any]:
    counts = {
        "nodes": 0,
        "properties": 0,
        "arrays": 0,
        "objects": 0,
        "enums": 0,
        "enum_values": 0,
        "required": 0,
        "optionals": 0,
        "refs": 0,
        "refs_resolved": 0,
        "oneOf": 0,
        "anyOf": 0,
        "allOf": 0,
        "nullable_representations": 0,
        "additionalProperties": 0,
        "patterns": 0,
        "limits": 0,
        "examples": 0,
        "defaults": 0,
        "descriptions": 0,
        "titles": 0,
    }
    max_depth = 0
    local_refs: list[str] = []
    cycles: list[str] = []
    potential: list[dict[str, str]] = []

    def walk(value: Any, path: str, depth: int, ancestry: tuple[int, ...]) -> None:
        nonlocal max_depth
        max_depth = max(max_depth, depth)
        if isinstance(value, Mapping):
            counts["nodes"] += 1
            identity = id(value)
            if identity in ancestry:
                cycles.append(path)
                return
            next_ancestry = ancestry + (identity,)
            node_type = value.get("type")
            if node_type == "object":
                counts["objects"] += 1
                properties = value.get("properties")
                if not properties and value.get("additionalProperties", True):
                    potential.append({
                        "path": path,
                        "construction": "unconstrained_object",
                    })
            if node_type == "array":
                counts["arrays"] += 1
            if (
                node_type == "null"
                or isinstance(node_type, list)
                and "null" in node_type
            ):
                counts["nullable_representations"] += 1
            properties = value.get("properties")
            if isinstance(properties, Mapping):
                counts["properties"] += len(properties)
                required = value.get("required") or []
                counts["required"] += len(required)
                counts["optionals"] += max(
                    0,
                    len(properties) - len(required),
                )
            enum = value.get("enum")
            if isinstance(enum, list):
                counts["enums"] += 1
                counts["enum_values"] += len(enum)
                if not enum:
                    potential.append({
                        "path": path,
                        "construction": "empty_enum",
                    })
            for keyword in ("oneOf", "anyOf", "allOf"):
                branch = value.get(keyword)
                if isinstance(branch, list):
                    counts[keyword] += len(branch)
                    if any(
                        isinstance(item, Mapping)
                        and item.get("type") == "null"
                        for item in branch
                    ):
                        counts["nullable_representations"] += 1
            if "$ref" in value:
                counts["refs"] += 1
                reference = str(value["$ref"])
                local_refs.append(reference)
                if _resolve_local_ref(schema, reference) is not None:
                    counts["refs_resolved"] += 1
            if "additionalProperties" in value:
                counts["additionalProperties"] += 1
            if "pattern" in value:
                counts["patterns"] += 1
            for key in (
                "minimum",
                "maximum",
                "minLength",
                "maxLength",
                "minItems",
                "maxItems",
            ):
                if key in value:
                    counts["limits"] += 1
            for key in ("examples", "default", "description", "title"):
                if key in value:
                    target = "defaults" if key == "default" else key
                    counts[target] += 1
            for key, item in value.items():
                walk(item, f"{path}/{key}", depth + 1, next_ancestry)
        elif isinstance(value, list):
            for index, item in enumerate(value):
                walk(item, f"{path}/{index}", depth + 1, ancestry)

    walk(schema, "#", 0, ())
    cycles.extend(_local_ref_cycles(schema, local_refs))
    return {
        "sha256": sha256_json(schema),
        "bytes": len(canonical_json_bytes(schema)),
        **counts,
        "maximum_depth": max_depth,
        "refs_list": local_refs,
        "cycles_or_recursion": sorted(set(cycles)),
        "potentially_problematic": potential,
        "compatibility_conclusion": (
            "HEURISTIC_ONLY_REQUIRES_MATRIX_CONFIRMATION"
            if potential
            else "NO_HEURISTIC_INCOMPATIBILITY_FOUND"
        ),
    }


def _local_ref_cycles(
    root: Mapping[str, Any],
    references: list[str],
) -> list[str]:
    graph: dict[str, set[str]] = {}
    for reference in set(references):
        target = _resolve_local_ref(root, reference)
        if target is None:
            continue
        nested: set[str] = set()

        def collect(value: Any) -> None:
            if isinstance(value, Mapping):
                child_ref = value.get("$ref")
                if isinstance(child_ref, str) and child_ref.startswith("#/"):
                    nested.add(child_ref)
                for item in value.values():
                    collect(item)
            elif isinstance(value, list):
                for item in value:
                    collect(item)

        collect(target)
        graph[reference] = nested
    cycles: set[str] = set()

    def visit(node: str, path: tuple[str, ...]) -> None:
        if node in path:
            start = path.index(node)
            cycles.add(" -> ".join(path[start:] + (node,)))
            return
        for child in graph.get(node, ()):
            visit(child, path + (node,))

    for node in graph:
        visit(node, ())
    return sorted(cycles)


def _resolve_local_ref(
    root: Mapping[str, Any],
    reference: str,
) -> Any | None:
    if not reference.startswith("#/"):
        return None
    current: Any = root
    for part in reference[2:].split("/"):
        key = part.replace("~1", "/").replace("~0", "~")
        if not isinstance(current, Mapping) or key not in current:
            return None
        current = current[key]
    return current


def payload_structure(
    payload: Mapping[str, Any],
    *,
    source: str,
    adapter: str,
    client: str,
) -> dict[str, Any]:
    wire = wire_json_bytes(payload)
    messages = payload.get("messages") or []
    schema = payload.get("format")
    schema_value = schema if isinstance(schema, Mapping) else None
    tools = payload.get("tools") or []
    context_chars, context_tool_chars = _transport_context_sizes(messages)
    message_summary = [
        {
            "role": item.get("role"),
            "content_chars": len(str(item.get("content") or "")),
            "content_bytes": len(
                str(item.get("content") or "").encode("utf-8")
            ),
            "content_sha256": sha256_text(
                str(item.get("content") or "")
            ),
        }
        for item in messages
    ]
    return {
        "source": source,
        "endpoint": "/api/chat",
        "http_method": "POST",
        "headers": ["accept", "content-type", "host", "user-agent"],
        "payload_bytes": len(wire),
        "payload_sha256": sha256_bytes(wire),
        "message_count": len(messages),
        "role_order": [item.get("role") for item in messages],
        "messages": message_summary,
        "system_prompt_size": (
            message_summary[0]["content_chars"]
            if message_summary
            else 0
        ),
        "user_prompt_size": (
            message_summary[1]["content_chars"]
            if len(message_summary) > 1
            else 0
        ),
        "context_size": context_chars,
        "schema": (
            schema_analysis(schema_value)
            if schema_value is not None
            else {
                "mode": schema,
                "bytes": (
                    len(str(schema).encode("utf-8"))
                    if schema is not None
                    else 0
                ),
            }
        ),
        "tool_count": len(tools),
        "tool_schema_size": len(canonical_json_bytes(tools)),
        "context_tool_representation_size": context_tool_chars,
        "tool_transport": (
            "top_level_tools"
            if tools
            else "no_top_level_tools_context_and_schema_only"
        ),
        "options": redact_mapping(payload.get("options") or {}),
        "think": payload.get("think"),
        "stream": payload.get("stream"),
        "keep_alive": payload.get("keep_alive"),
        "provider_adapter": adapter,
        "http_client": client,
        "response_handling": (
            "buffer_complete_response"
            if not payload.get("stream")
            else "incremental_ndjson"
        ),
    }


def _transport_context_sizes(
    messages: list[Mapping[str, Any]],
) -> tuple[int, int]:
    if len(messages) < 2:
        return 0, 0
    content = str(messages[1].get("content") or "")
    marker = "\n\nAUTHORITATIVE_CONTEXT:\n"
    if marker not in content:
        return 0, 0
    raw = content.split(marker, 1)[1]
    try:
        context = json.loads(raw)
    except ValueError:
        return len(raw), 0
    tool_chars = sum(
        len(str(item.get("content") or ""))
        for item in context
        if isinstance(item, Mapping) and item.get("kind") == "tools"
    )
    return len(raw), tool_chars


def payload_diff(
    v1: Mapping[str, Any],
    v2: Mapping[str, Any],
) -> dict[str, Any]:
    keys = sorted(set(v1) | set(v2))
    differences = {
        key: {"v1": v1.get(key), "v2": v2.get(key)}
        for key in keys
        if v1.get(key) != v2.get(key)
    }
    return {
        "same_adapter": (
            v1.get("provider_adapter") == v2.get("provider_adapter")
        ),
        "same_http_client": v1.get("http_client") == v2.get("http_client"),
        "same_endpoint": (
            v1.get("endpoint") == v2.get("endpoint")
            and v1.get("http_method") == v2.get("http_method")
        ),
        "different_fields": differences,
        "material_differences": [
            key for key in differences
            if key not in {"source", "payload_sha256", "messages"}
        ],
    }


def render_payload_diff(diff: Mapping[str, Any]) -> str:
    lines = [
        "# Payload V1 vs V2",
        "",
        f"- Same adapter: `{str(diff['same_adapter']).lower()}`",
        f"- Same HTTP client: `{str(diff['same_http_client']).lower()}`",
        f"- Same endpoint: `{str(diff['same_endpoint']).lower()}`",
        "",
        "| Field | V1 | V2 |",
        "|---|---:|---:|",
    ]
    for key, values in diff.get("different_fields", {}).items():
        left = _compact_markdown_value(values.get("v1"))
        right = _compact_markdown_value(values.get("v2"))
        lines.append(f"| `{key}` | {left} | {right} |")
    return "\n".join(lines) + "\n"


def _compact_markdown_value(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return f"`sha256:{sha256_json(value)[:12]} size:{len(canonical_json_bytes(value))}`"
    return f"`{str(value).replace('|', '/').replace(chr(10), ' ')[:80]}`"


def _context_without_tools(request: ModelRequest):
    return replace(
        request.context,
        items=tuple(
            item for item in request.context.items
            if item.kind != "tools"
        ),
        decisions=tuple(
            item for item in request.context.decisions
            if item.kind != "tools"
        ),
        total_chars=sum(
            len(item.content)
            for item in request.context.items
            if item.kind != "tools"
        ),
    )


def _request_with_tools(
    bundle: RequestBundle,
    config: DiagnosticConfig,
    tools: tuple[str, ...],
    *,
    unconstrained_tool_name: bool = False,
) -> tuple[ModelRequest, dict[str, Any], dict[str, Any]]:
    scenario = _scenario_by_id(bundle.scenario_id)
    state = StatefulContext(
        objective=scenario.objective,
        constraints=scenario.constraints,
    )
    scenario_tools = (
        tools
        if "finish" in tools
        else tools + ("finish",)
    )
    modified_scenario = replace(
        scenario,
        available_tools=scenario_tools,
        required_tools=tuple(
            item
            for item in scenario.required_tools
            if item in scenario_tools
        ),
    )
    context, _ = build_step_context(
        modified_scenario,
        state,
        create_read_only_tool_registry(),
        max_chars=config.context_tokens * 8,
    )
    system_prompt, user_prompt = build_step_prompt(
        modified_scenario,
        state,
        1,
    )
    schema = decision_schema(scenario_tools)
    if unconstrained_tool_name:
        schema["properties"]["tool_name"] = {"type": "string"}
    expected = replace(
        bundle.request.expected_output,
        schema=schema,
        enum_constraints=(
            EnumConstraint("$.decision", DECISION_VALUES),
            EnumConstraint("$.stop_reason", STOP_VALUES),
        ),
    )
    request = replace(
        bundle.request,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        context=context,
        allowed_tools=scenario_tools,
        expected_output=expected,
        request_id=uuid.uuid4().hex,
    )
    if not tools:
        user_payload = json.loads(request.user_prompt)
        for field_name in (
            "available_tools",
            "tools_already_called",
            "required_tools_before_finish",
            "required_tools_remaining",
        ):
            user_payload[field_name] = []
        request = replace(
            request,
            context=_context_without_tools(request),
            user_prompt=json.dumps(
                user_payload,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ),
            allowed_tools=(),
        )
    payload = build_provider_payload(request, bundle.route, config)
    return request, schema, payload


def minimal_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["continue", "finish"],
            },
        },
        "required": ["action"],
        "additionalProperties": False,
    }


def build_matrix_variants(
    bundle: RequestBundle,
    config: DiagnosticConfig,
    *,
    v1_payload: Mapping[str, Any] | None = None,
) -> list[MatrixVariant]:
    exact = copy.deepcopy(bundle.payload)
    no_schema = copy.deepcopy(exact)
    no_schema.pop("format", None)
    minimal = copy.deepcopy(exact)
    minimal["format"] = minimal_schema()
    no_tool_request, no_tool_schema, no_tool_payload = _request_with_tools(
        bundle,
        config,
        (),
        unconstrained_tool_name=True,
    )
    one_request, one_schema, one_payload = _request_with_tools(
        bundle,
        config,
        ("list_files",),
    )
    prompt_schema = copy.deepcopy(exact)
    prompt_schema.pop("format", None)
    prompt_schema["messages"][1]["content"] += (
        "\n\nOUTPUT_CONTRACT_FOR_DIAGNOSTIC_ONLY:\n"
        + json.dumps(
            bundle.schema,
            ensure_ascii=False,
            separators=(",", ":"),
        )
    )
    variants = [
        MatrixVariant(
            "D01_BASELINE_SIMPLE",
            "Minimal prompt without schema or tools",
            {
                "model": config.model,
                "messages": [
                    {
                        "role": "system",
                        "content": "Answer directly and briefly.",
                    },
                    {"role": "user", "content": "Reply with OK."},
                ],
                "stream": False,
                "think": config.think,
                "keep_alive": config.keep_alive,
                "options": exact["options"],
            },
            None,
            "direct_ollama",
            "baseline",
        ),
        MatrixVariant(
            "D02_STATEFUL_PROMPT_NO_SCHEMA",
            "Exact stateful messages without structured format",
            no_schema,
            None,
            "direct_ollama",
            "stateful_prompt",
        ),
        MatrixVariant(
            "D03_STATEFUL_PROMPT_MINIMAL_SCHEMA",
            "Exact stateful messages with minimal schema",
            minimal,
            minimal_schema(),
            "direct_ollama",
            "minimal_schema",
        ),
        MatrixVariant(
            "D04_FULL_SCHEMA_NO_TOOLS",
            "Full decision schema without tool representation",
            no_tool_payload,
            no_tool_schema,
            "direct_ollama",
            "full_schema_without_tools",
            request=no_tool_request,
        ),
        MatrixVariant(
            "D05_FULL_SCHEMA_ONE_TOOL",
            "Full decision schema with one read-only tool",
            one_payload,
            one_schema,
            "direct_ollama",
            "one_tool_representation",
            request=one_request,
        ),
        MatrixVariant(
            "D06_FULL_SCHEMA_ALL_TOOLS",
            "Exact full stateful request",
            exact,
            bundle.schema,
            "direct_ollama",
            "all_tool_representations",
            expected_equivalence="exact_payload",
            request=bundle.resolved_request,
        ),
        MatrixVariant(
            "D07_DIRECT_OLLAMA_FULL_REQUEST",
            "Exact full payload sent directly to Ollama",
            exact,
            bundle.schema,
            "direct_ollama",
            "execution_path_direct",
            expected_equivalence="same_payload_as_D06",
            request=bundle.resolved_request,
        ),
        MatrixVariant(
            "D08_HARNESS_FULL_REQUEST",
            "Exact request through ModelHarness and existing provider",
            exact,
            bundle.schema,
            "model_harness",
            "execution_path_harness",
            expected_equivalence="same_logical_request_as_D07",
            request=bundle.request,
        ),
        MatrixVariant(
            "D09_V1_PROVIDER_WITH_V2_PAYLOAD",
            "Existing v1 adapter with v2 request",
            exact,
            bundle.schema,
            "alias",
            "provider_adapter",
            expected_equivalence="identical_to_D08_existing_shared_adapter",
            request=bundle.request,
        ),
        MatrixVariant(
            "D10_V2_PROVIDER_WITH_V1_PAYLOAD",
            "Put v1 payload through a distinct v2 adapter",
            v1_payload,
            (
                v1_payload.get("format")
                if isinstance(v1_payload, Mapping)
                and isinstance(v1_payload.get("format"), Mapping)
                else None
            ),
            "not_applicable",
            "provider_adapter",
            expected_equivalence="no_distinct_v2_adapter_exists",
        ),
        MatrixVariant(
            "D11_SCHEMA_AS_PROMPT_ONLY",
            "Full schema represented in prompt only",
            prompt_schema,
            bundle.schema,
            "direct_ollama",
            "schema_transport",
        ),
        MatrixVariant(
            "D12_SCHEMA_COMPLEXITY_REDUCTION",
            "Progressive deterministic schema reduction",
            exact,
            bundle.schema,
            "schema_reduction",
            "schema_fragments",
        ),
    ]
    return variants


def schema_reduction_variants(
    payload: Mapping[str, Any],
    schema: Mapping[str, Any],
) -> list[MatrixVariant]:
    without_plan = copy.deepcopy(schema)
    without_plan["required"] = [
        item for item in without_plan["required"] if item != "plan"
    ]
    without_plan["properties"].pop("plan", None)
    without_arguments = copy.deepcopy(schema)
    without_arguments["required"] = [
        item
        for item in without_arguments["required"]
        if item != "arguments"
    ]
    without_arguments["properties"].pop("arguments", None)
    core = {
        "type": "object",
        "required": ["decision", "tool_name"],
        "properties": {
            "decision": copy.deepcopy(
                schema["properties"]["decision"]
            ),
            "tool_name": copy.deepcopy(
                schema["properties"]["tool_name"]
            ),
        },
        "additionalProperties": False,
    }
    core_arguments = copy.deepcopy(core)
    core_arguments["required"].append("arguments")
    core_arguments["properties"]["arguments"] = copy.deepcopy(
        schema["properties"]["arguments"]
    )
    core_arrays = copy.deepcopy(core)
    for name in ("evidence_refs", "retained_constraint_ids"):
        core_arrays["required"].append(name)
        core_arrays["properties"][name] = copy.deepcopy(
            schema["properties"][name]
        )
    definitions = (
        ("D12_R1_WITHOUT_PLAN", without_plan, "remove_plan"),
        (
            "D12_R2_WITHOUT_ARGUMENTS",
            without_arguments,
            "remove_unconstrained_arguments",
        ),
        ("D12_R3_CORE_DECISION", core, "core_fields_only"),
        (
            "D12_R4_CORE_PLUS_ARGUMENTS",
            core_arguments,
            "add_unconstrained_arguments",
        ),
        (
            "D12_R5_CORE_PLUS_ARRAYS",
            core_arrays,
            "add_reference_arrays",
        ),
    )
    variants: list[MatrixVariant] = []
    for variant_id, candidate, dimension in definitions:
        candidate_payload = copy.deepcopy(payload)
        candidate_payload["format"] = candidate
        variants.append(MatrixVariant(
            variant_id,
            variant_id.replace("_", " ").title(),
            candidate_payload,
            candidate,
            "direct_ollama",
            dimension,
        ))
    return variants


def _trace_stage(name: str) -> str | None:
    normalized = name.casefold()
    if "connect_tcp.complete" in normalized:
        return "T11"
    if "send_request_headers.complete" in normalized:
        return "T12"
    if "send_request_body.complete" in normalized:
        return "T13"
    if "receive_response_headers.complete" in normalized:
        return "T14"
    return None


async def direct_ollama_call(
    variant: MatrixVariant,
    config: DiagnosticConfig,
    *,
    correlation_id: str | None = None,
    stream_override: bool | None = None,
    runtime_sink: list[dict[str, Any]] | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> HttpCallResult:
    if variant.payload is None:
        raise ValueError(f"{variant.variant_id} has no payload")
    correlation = correlation_id or uuid.uuid4().hex
    timeline = Timeline(correlation, variant.variant_id)
    timeline.observe(
        "T00",
        details={"diagnostic_version": DIAGNOSTIC_VERSION},
    )
    for code in ("T01", "T02", "T03", "T04", "T05", "T06", "T07"):
        timeline.unavailable(
            code,
            "The direct HTTP path receives an already constructed payload.",
        )
    payload = copy.deepcopy(dict(variant.payload))
    if stream_override is not None:
        payload["stream"] = stream_override
    endpoint = config.base_url.rstrip("/") + "/api/chat"
    payload_bytes = wire_json_bytes(payload, url=endpoint)
    timeline.observe(
        "T08",
        details={
            "payload_sha256": sha256_bytes(payload_bytes),
            "payload_bytes": len(payload_bytes),
            "stream": payload.get("stream"),
        },
    )
    started = time.perf_counter()
    response_data = bytearray()
    model_parts: list[str] = []
    response_status: int | None = None
    envelope: dict[str, Any] = {}
    exception: dict[str, Any] | None = None
    parse_valid: bool | None = None
    schema_valid: bool | None = None
    monitor_stop = asyncio.Event()
    monitor_task: asyncio.Task | None = None
    if runtime_sink is not None:
        monitor_task = asyncio.create_task(
            monitor_runtime(
                config,
                variant.variant_id,
                correlation,
                runtime_sink,
                monitor_stop,
            )
        )

    async def trace(event_name: str, info: Mapping[str, Any]) -> None:
        stage = _trace_stage(event_name)
        if stage is not None:
            timeline.observe(
                stage,
                details={
                    "httpcore_event": event_name,
                    "info_keys": sorted(str(key) for key in info),
                },
            )

    try:
        timeline.observe(
            "T09",
            details={
                "endpoint": "/api/chat",
                "execution_path": "direct_ollama",
            },
        )
        parsed_url = urlparse(config.base_url)
        timeline.observe(
            "T10",
            details={
                "scheme": parsed_url.scheme,
                "host": parsed_url.hostname,
                "port": parsed_url.port,
                "resolution": "httpcore_trace_for_actual_connection",
            },
        )
        timeout = httpx.Timeout(
            connect=15.0,
            read=config.timeout_seconds,
            write=30.0,
            pool=15.0,
        )
        headers = {"content-type": "application/json"}
        async with httpx.AsyncClient(
            timeout=timeout,
            transport=transport,
        ) as client:
            async with client.stream(
                "POST",
                endpoint,
                content=payload_bytes,
                headers=headers,
                extensions={"trace": trace},
            ) as response:
                response_status = response.status_code
                timeline.observe(
                    "T14",
                    details={"status_code": response.status_code},
                )
                if response.status_code >= 400:
                    body = await response.aread()
                    response_data.extend(body)
                    response.raise_for_status()
                buffer = ""
                async for chunk in _response_chunks(response):
                    if not chunk:
                        continue
                    if not response_data:
                        timeline.observe(
                            "T15",
                            details={"bytes": len(chunk)},
                        )
                        timeline.observe(
                            "T16",
                            details={"bytes": len(chunk)},
                        )
                    response_data.extend(chunk)
                    if payload.get("stream"):
                        buffer += chunk.decode("utf-8", errors="replace")
                        lines = buffer.splitlines(keepends=True)
                        buffer = ""
                        if lines and not lines[-1].endswith(("\n", "\r")):
                            buffer = lines.pop()
                        for line in lines:
                            parsed = _parse_stream_line(line)
                            if parsed is None:
                                continue
                            content = str(
                                (parsed.get("message") or {}).get(
                                    "content"
                                )
                                or ""
                            )
                            if content:
                                if not model_parts:
                                    timeline.observe(
                                        "T17",
                                        details={
                                            "observation": (
                                                "first non-empty content "
                                                "in streamed Ollama chunk"
                                            )
                                        },
                                    )
                                model_parts.append(content)
                            if parsed.get("done") is True:
                                envelope = parsed
                if payload.get("stream") and buffer.strip():
                    parsed = _parse_stream_line(buffer)
                    if parsed is not None:
                        content = str(
                            (parsed.get("message") or {}).get("content")
                            or ""
                        )
                        if content:
                            if not model_parts:
                                timeline.observe(
                                    "T17",
                                    details={
                                        "observation": (
                                            "first non-empty content "
                                            "in final streamed chunk"
                                        )
                                    },
                                )
                            model_parts.append(content)
                        if parsed.get("done") is True:
                            envelope = parsed
        timeline.observe(
            "T18",
            details={
                "response_bytes": len(response_data),
                "partial_response": False,
            },
        )
        timeline.observe("T19")
        if payload.get("stream"):
            model_content = "".join(model_parts)
            if not envelope:
                raise ValueError("Stream completed without done envelope")
        else:
            envelope = json.loads(response_data.decode("utf-8"))
            model_content = str(
                (envelope.get("message") or {}).get("content") or ""
            )
            if model_content:
                timeline.observe(
                    "T17",
                    details={
                        "observation": (
                            "content became observable only after the "
                            "non-streamed response completed"
                        )
                    },
                )
        timeline.observe(
            "T20",
            details={
                "envelope_keys": sorted(envelope),
                "model_content_chars": len(model_content),
            },
        )
        if variant.schema is not None:
            structured = json.loads(model_content)
            parse_valid = True
            errors = sorted(
                Draft202012Validator(variant.schema).iter_errors(
                    structured
                ),
                key=lambda item: list(item.path),
            )
            schema_valid = not errors
        else:
            parse_valid = _is_json(model_content)
            schema_valid = None
        timeline.observe(
            "T21",
            details={
                "json_valid": parse_valid,
                "schema_valid": schema_valid,
            },
        )
        timeline.unavailable(
            "T22",
            "Direct Ollama calls do not invoke RecoveryCoordinator.",
        )
        status = (
            "SUCCEEDED"
            if variant.schema is None or schema_valid
            else "VALIDATION_FAILED"
        )
    except Exception as exc:
        stage = _exception_stage(timeline)
        exception = exception_record(
            exc,
            stage=stage,
            correlation_id=correlation,
            variant_id=variant.variant_id,
        )
        status = exception["classification"]
        model_content = "".join(model_parts)
        if response_data:
            timeline.events.get("T18", {}).setdefault(
                "details",
                {},
            )["partial_response"] = True
    finally:
        monitor_stop.set()
        if monitor_task is not None:
            try:
                await asyncio.wait_for(monitor_task, timeout=5)
            except (TimeoutError, asyncio.TimeoutError):
                monitor_task.cancel()
        timeline.observe(
            "T23",
            details={
                "status": status,
                "exception_classification": (
                    exception.get("classification")
                    if exception
                    else ""
                ),
            },
        )
    result = HttpCallResult(
        variant_id=variant.variant_id,
        status=status,
        execution_path="direct_ollama",
        duration_ms=round((time.perf_counter() - started) * 1_000, 3),
        status_code=response_status,
        response_bytes=len(response_data),
        response_sha256=sha256_bytes(bytes(response_data)),
        model_content_chars=len(model_content),
        model_content_sha256=sha256_text(model_content),
        done=envelope.get("done") if envelope else None,
        done_reason=str(envelope.get("done_reason") or ""),
        input_tokens=_optional_int(envelope.get("prompt_eval_count")),
        output_tokens=_optional_int(envelope.get("eval_count")),
        json_valid=parse_valid,
        schema_valid=schema_valid,
        partial_response=bool(response_data) and status != "SUCCEEDED",
        exception=exception,
        timeline=timeline.finalized(),
        payload_sha256=sha256_bytes(payload_bytes),
        payload_bytes=len(payload_bytes),
    )
    return result


def _parse_stream_line(line: str) -> dict[str, Any] | None:
    stripped = line.strip()
    if not stripped:
        return None
    value = json.loads(stripped)
    if not isinstance(value, dict):
        raise ValueError("Ollama stream chunk is not an object")
    return value


async def _response_chunks(response: httpx.Response):
    if response.is_stream_consumed:
        if response.content:
            yield response.content
        return
    async for chunk in response.aiter_raw():
        yield chunk


def _is_json(value: str) -> bool:
    if not value.strip():
        return False
    try:
        json.loads(value)
    except (TypeError, ValueError):
        return False
    return True


def _exception_stage(timeline: Timeline) -> str:
    observed = [
        code
        for code, _ in TIMELINE_STAGES
        if (
            timeline.events.get(code, {}).get("status")
            == "OBSERVED"
        )
    ]
    return observed[-1] if observed else "T00"


def _optional_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


async def harness_ollama_call(
    bundle: RequestBundle,
    config: DiagnosticConfig,
    *,
    variant_id: str = "D08_HARNESS_FULL_REQUEST",
    runtime_sink: list[dict[str, Any]] | None = None,
) -> HttpCallResult:
    correlation = uuid.uuid4().hex
    timeline = Timeline(correlation, variant_id)
    timeline.observe("T00", details={"version": DIAGNOSTIC_VERSION})
    timeline.observe(
        "T01",
        details={"scenario_id": bundle.scenario_id},
    )
    timeline.observe(
        "T02",
        details={
            "context_hash": bundle.context_hash,
            "context_chars": bundle.request.context.total_chars,
        },
    )
    timeline.observe(
        "T03",
        details={
            "request_fingerprint": bundle.request.fingerprint(),
        },
    )
    provider = OllamaBenchmarkProvider(config.ollama_config())
    harness = ModelHarness(ProviderRegistry([provider]))
    profile = harness.profiles.get(bundle.request.task_profile)
    timeline.observe("T04", details={"profile": profile.name})
    resolved = harness._apply_profile(bundle.request, profile)
    route = harness.router.route(resolved, profile)
    timeline.observe("T05", details=asdict(route))
    timeline.observe(
        "T06",
        details={"schema_sha256": sha256_json(bundle.schema)},
    )
    timeline.observe(
        "T07",
        details={
            "method": "existing_provider_shallow_dict_copy",
            "schema_sha256": sha256_json(bundle.schema),
        },
    )
    timeline.observe(
        "T08",
        details={
            "payload_sha256": sha256_bytes(bundle.payload_bytes),
            "payload_bytes": len(bundle.payload_bytes),
        },
    )
    monitor_stop = asyncio.Event()
    monitor_task: asyncio.Task | None = None
    if runtime_sink is not None:
        monitor_task = asyncio.create_task(
            monitor_runtime(
                config,
                variant_id,
                correlation,
                runtime_sink,
                monitor_stop,
            )
        )
    started = time.perf_counter()
    timeline.observe(
        "T09",
        details={
            "provider": type(provider).__name__,
            "execution_path": "ModelHarness.execute",
        },
    )
    try:
        response = await harness.execute(bundle.request)
        if response.status == ModelResponseStatus.PROVIDER_FAILED:
            exc = response.provider_exception or RuntimeError(
                "Provider failed without preserved exception"
            )
            exception = exception_record(
                exc,
                stage="T09",
                correlation_id=correlation,
                variant_id=variant_id,
            )
        else:
            exception = None
        timeline.unavailable(
            "T10",
            "Existing provider does not expose DNS/endpoint trace hooks.",
        )
        for stage in ("T11", "T12", "T13", "T14", "T15", "T16"):
            timeline.unavailable(
                stage,
                "Existing buffered provider does not expose this HTTP phase.",
            )
        if response.raw_text:
            timeline.unavailable(
                "T17",
                "Buffered provider exposes content only after completion.",
            )
        else:
            timeline.unavailable(
                "T17",
                "No model content was returned.",
            )
        if response.status != ModelResponseStatus.PROVIDER_FAILED:
            timeline.observe(
                "T18",
                details={"raw_chars": len(response.raw_text)},
            )
            timeline.observe("T19")
            timeline.observe(
                "T20",
                details={
                    "structured_output": (
                        response.structured_output is not None
                    )
                },
            )
            timeline.observe(
                "T21",
                details={
                    "validation": response.validation.status.value
                },
            )
        else:
            for stage in ("T18", "T19", "T20", "T21"):
                timeline.unavailable(
                    stage,
                    "Provider exception prevented this phase.",
                )
        timeline.observe(
            "T22",
            details={
                "recovery": [
                    item.action.value for item in response.recovery
                ]
            },
        )
        status = response.status.value
        model_content = response.raw_text
        envelope = provider.envelopes.get(response.request_id, {})
    finally:
        monitor_stop.set()
        if monitor_task is not None:
            try:
                await asyncio.wait_for(monitor_task, timeout=5)
            except (TimeoutError, asyncio.TimeoutError):
                monitor_task.cancel()
    timeline.observe(
        "T23",
        details={
            "status": status,
            "exception_classification": (
                exception.get("classification") if exception else ""
            ),
        },
    )
    return HttpCallResult(
        variant_id=variant_id,
        status=status,
        execution_path="ModelHarness.execute -> OllamaBenchmarkProvider",
        duration_ms=round((time.perf_counter() - started) * 1_000, 3),
        status_code=None,
        response_bytes=0,
        response_sha256="",
        model_content_chars=len(model_content),
        model_content_sha256=sha256_text(model_content),
        done=envelope.get("done") if envelope else None,
        done_reason=str(envelope.get("done_reason") or ""),
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
        json_valid=(
            response.validation.status.value != "NOT_RUN"
            if model_content
            else None
        ),
        schema_valid=response.validation.is_valid,
        partial_response=bool(model_content) and exception is not None,
        exception=exception,
        timeline=timeline.finalized(),
        payload_sha256=sha256_bytes(bundle.payload_bytes),
        payload_bytes=len(bundle.payload_bytes),
        notes=[
            "T10-T17 are intentionally NOT_OBSERVABLE in the existing "
            "buffered provider path."
        ],
    )


async def monitor_runtime(
    config: DiagnosticConfig,
    variant_id: str,
    correlation_id: str,
    sink: list[dict[str, Any]],
    stop: asyncio.Event,
) -> None:
    sequence = 0
    while True:
        sequence += 1
        snapshot = await runtime_snapshot(
            config,
            variant_id=variant_id,
            correlation_id=correlation_id,
            sequence=sequence,
        )
        sink.append(snapshot)
        if stop.is_set():
            return
        try:
            await asyncio.wait_for(stop.wait(), timeout=10.0)
        except (TimeoutError, asyncio.TimeoutError):
            continue


async def runtime_snapshot(
    config: DiagnosticConfig,
    *,
    variant_id: str,
    correlation_id: str,
    sequence: int,
) -> dict[str, Any]:
    endpoint: dict[str, Any]
    try:
        timeout = httpx.Timeout(3.0)
        async with httpx.AsyncClient(
            base_url=config.base_url,
            timeout=timeout,
        ) as client:
            response = await client.get("/api/ps")
            endpoint = {
                "reachable": True,
                "status_code": response.status_code,
                "ollama_ps": (
                    response.json()
                    if response.status_code < 400
                    else {}
                ),
            }
    except Exception as exc:
        endpoint = {
            "reachable": False,
            "exception": {
                "class": type(exc).__name__,
                "classification": classify_exception(exc),
                "message_sha256": sha256_text(str(exc)),
            },
        }
    gpu, system = await asyncio.gather(
        asyncio.to_thread(nvidia_snapshot),
        asyncio.to_thread(_system_snapshot),
    )
    return {
        "utc": utc_now(),
        "monotonic_ns": time.monotonic_ns(),
        "variant_id": variant_id,
        "correlation_id": correlation_id,
        "sequence": sequence,
        "endpoint": endpoint,
        "gpu": gpu,
        "system": system,
    }


def _system_snapshot() -> dict[str, Any]:
    try:
        import psutil
    except ImportError:
        return {"status": "NOT_OBSERVABLE", "reason": "psutil unavailable"}
    memory = psutil.virtual_memory()
    processes = []
    for process in psutil.process_iter(
        ["pid", "name", "cpu_percent", "memory_info", "create_time"]
    ):
        try:
            name = str(process.info.get("name") or "")
            if "ollama" not in name.casefold():
                continue
            memory_info = process.info.get("memory_info")
            processes.append({
                "pid": process.info.get("pid"),
                "name": name,
                "cpu_percent": process.info.get("cpu_percent"),
                "rss_bytes": (
                    getattr(memory_info, "rss", None)
                    if memory_info is not None
                    else None
                ),
                "create_time": process.info.get("create_time"),
            })
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            continue
    return {
        "platform": platform.platform(),
        "cpu_percent": psutil.cpu_percent(interval=0.1),
        "ram_total_bytes": memory.total,
        "ram_used_bytes": memory.used,
        "ram_available_bytes": memory.available,
        "ollama_processes": processes,
    }


def runtime_identity(config: DiagnosticConfig) -> dict[str, Any]:
    return {
        "captured_at": utc_now(),
        "python": sys.version,
        "platform": platform.platform(),
        "ollama_version": command_output(["ollama", "--version"]),
        "ollama_ps": {
            "command": "ollama ps",
            "output": redact_text(command_output(["ollama", "ps"])),
        },
        "gpu": nvidia_snapshot(),
        "system": _system_snapshot(),
        "base_url": config.base_url,
    }


def reset_ollama_model(
    model: str,
    base_url: str = "http://127.0.0.1:11434",
) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            ["ollama", "stop", model],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return {
            "status": "FAILED",
            "exit_code": None,
            "error": {
                "class": type(exc).__name__,
                "message_sha256": sha256_text(str(exc)),
            },
        }
    unloaded = False
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        try:
            response = httpx.get(
                base_url.rstrip("/") + "/api/ps",
                timeout=2,
            )
            models = response.json().get("models") or []
            unloaded = not any(
                str(item.get("name") or item.get("model") or "")
                == model
                for item in models
            )
            if unloaded:
                break
        except (httpx.HTTPError, ValueError):
            pass
        time.sleep(0.25)
    return {
        "status": (
            "SUCCEEDED"
            if completed.returncode == 0 and unloaded
            else "FAILED"
        ),
        "exit_code": completed.returncode,
        "stdout_sha256": sha256_text(completed.stdout or ""),
        "stderr_sha256": sha256_text(completed.stderr or ""),
        "model_unloaded": unloaded,
        "elapsed_ms": round(
            (time.perf_counter() - started) * 1_000,
            3,
        ),
    }


def ollama_log_offsets() -> dict[str, int]:
    local = Path(os.environ.get("LOCALAPPDATA") or "") / "Ollama"
    candidates = [
        local / "server.log",
        Path.home() / ".ollama" / "logs" / "server.log",
    ]
    return {
        str(path): path.stat().st_size
        for path in candidates
        if path.is_file()
    }


def read_ollama_log_delta(
    offsets: Mapping[str, int],
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for name, offset in offsets.items():
        path = Path(name)
        if not path.is_file():
            continue
        with path.open("rb") as handle:
            handle.seek(max(0, offset))
            data = handle.read(512 * 1024)
        text = data.decode("utf-8", errors="replace")
        lines = [
            redact_text(line)
            for line in text.splitlines()
            if line.strip()
        ]
        records.append({
            "path": path.name,
            "start_offset": offset,
            "end_offset": path.stat().st_size,
            "bytes_captured": len(data),
            "sha256": sha256_bytes(data),
            "lines": lines[-200:],
        })
    return records


class StatefulProviderDiagnostic:
    def __init__(self, config: DiagnosticConfig):
        self.config = config
        self.output_dir = config.output_dir
        self.runtime_records: list[dict[str, Any]] = []
        self.results: list[dict[str, Any]] = []
        self.exceptions: list[dict[str, Any]] = []
        self.telemetry: list[dict[str, Any]] = []
        self.timeline_records: list[dict[str, Any]] = []
        self._log_offsets: dict[str, int] = {}

    async def run(self) -> dict[str, Any]:
        if self.output_dir.exists():
            raise FileExistsError(
                f"Diagnostic output already exists: {self.output_dir}"
            )
        self.output_dir.mkdir(parents=True)
        started_at = utc_now()
        before = integrity_snapshot()
        if self.config.capture_ollama_logs:
            self._log_offsets = ollama_log_offsets()
        reconstruction_timeline = Timeline(
            uuid.uuid4().hex,
            "REQUEST_RECONSTRUCTION",
        )
        bundle = reconstruct_stateful_request(
            self.config,
            reconstruction_timeline,
        )
        reconstruction_timeline.observe(
            "T23",
            details={"status": "REQUEST_RECONSTRUCTED"},
        )
        self.timeline_records.extend(reconstruction_timeline.finalized())
        v1_payload, v1_source = load_v1_payload()
        v1_structure = payload_structure(
            v1_payload,
            source=(
                "bounded_v1_historical_success:"
                + str(v1_source["case_id"])
            ),
            adapter="OllamaBenchmarkProvider",
            client="httpx.AsyncClient.post buffered",
        )
        v2_structure = payload_structure(
            bundle.payload,
            source="stateful_v2_reconstructed_first_request",
            adapter="OllamaBenchmarkProvider",
            client="httpx.AsyncClient.post buffered",
        )
        structure_diff = payload_diff(v1_structure, v2_structure)
        schema_metrics = schema_analysis(bundle.schema)
        manifest = self._manifest(
            started_at,
            bundle,
            v1_source,
            before,
        )
        self._write_json("manifest.json", manifest)
        self._write_json("payload_v1_structure.json", v1_structure)
        self._write_json("payload_v2_structure.json", v2_structure)
        self._write_json("payload_diff.json", structure_diff)
        (self.output_dir / "payload_diff.md").write_text(
            render_payload_diff(structure_diff),
            encoding="utf-8",
            newline="\n",
        )
        self._write_json("schema_analysis.json", schema_metrics)
        if self.config.debug_payload:
            debug_dir = self.output_dir / "debug_payloads"
            debug_dir.mkdir()
            self._write_json(
                "debug_payloads/stateful_v2_exact.json",
                bundle.payload,
            )
            self._write_json(
                "debug_payloads/bounded_v1.json",
                v1_payload,
            )
        self.runtime_records.append({
            "event": "diagnostic_runtime_before",
            **runtime_identity(self.config),
        })
        self._flush_incremental()

        if self.config.mode == "exact":
            await self._run_exact(bundle)
        elif self.config.mode == "matrix":
            await self._run_matrix(bundle, v1_payload)

        self.runtime_records.append({
            "event": "diagnostic_runtime_after",
            **runtime_identity(self.config),
        })
        if self.config.capture_ollama_logs:
            self.runtime_records.append({
                "event": "ollama_log_delta",
                "captured_at": utc_now(),
                "records": read_ollama_log_delta(self._log_offsets),
            })
        after = integrity_snapshot()
        integrity = integrity_comparison(before, after)
        matrix = {
            "diagnostic_version": DIAGNOSTIC_VERSION,
            "results": self.results,
            "executed": [
                item["variant_id"] for item in self.results
                if item.get("status")
                not in {"NOT_EXECUTED", "NOT_APPLICABLE"}
            ],
            "not_executed": [
                item for item in self.results
                if item.get("status")
                in {"NOT_EXECUTED", "NOT_APPLICABLE"}
            ],
        }
        hypotheses = assess_hypotheses(
            self.results,
            v1_structure,
            v2_structure,
            self.runtime_records,
        )
        diagnosis = derive_diagnosis(
            self.results,
            hypotheses,
            integrity,
            bundle.reconstruction,
        )
        summary = {
            "diagnostic_version": DIAGNOSTIC_VERSION,
            "started_at": started_at,
            "completed_at": utc_now(),
            "mode": self.config.mode,
            "scenario": bundle.scenario_id,
            "model": self.config.model,
            "reconstruction": bundle.reconstruction,
            "request_hashes": request_hashes(bundle),
            "v1_source": v1_source,
            "schema_analysis": schema_metrics,
            "matrix_statuses": {
                item["variant_id"]: item["status"]
                for item in self.results
            },
            "hypotheses": hypotheses,
            "diagnosis": diagnosis,
            "integrity_unchanged": integrity["unchanged"],
            "decision": diagnosis["decision"],
            "production_fix_implemented": False,
            "timeout_increased_as_fix": False,
            "operational_tools_executed": False,
        }
        self._write_json("matrix_results.json", matrix)
        self._write_json("hypothesis_assessment.json", hypotheses)
        self._write_json("exceptions.json", {
            "exceptions": self.exceptions,
        })
        self._write_json("integrity.json", integrity)
        self._write_json("summary.json", summary)
        self._write_jsonl("timeline.jsonl", self.timeline_records)
        self._write_jsonl("ollama_runtime.jsonl", self.runtime_records)
        self._write_jsonl("telemetry.jsonl", self.telemetry)
        (self.output_dir / "REPORT.md").write_text(
            render_report(
                summary,
                v1_structure,
                v2_structure,
                structure_diff,
                self.results,
                hypotheses,
                integrity,
            ),
            encoding="utf-8",
            newline="\n",
        )
        return summary

    async def _run_exact(self, bundle: RequestBundle) -> None:
        if self.config.stream_probe_only:
            variant = MatrixVariant(
                "EXACT_STREAM_PROBE",
                "Exact full payload with stream=true",
                bundle.payload,
                bundle.schema,
                "direct_ollama",
                "stream_only",
                expected_equivalence=(
                    "exact_payload_except_stream_true"
                ),
                request=bundle.resolved_request,
            )
            await self._execute_direct(
                variant,
                stream_override=True,
            )
            return
        if self.config.direct_ollama:
            variant = MatrixVariant(
                "EXACT_DIRECT",
                "Exact original request direct to Ollama",
                bundle.payload,
                bundle.schema,
                "direct_ollama",
                "none",
                expected_equivalence="exact_payload",
                request=bundle.resolved_request,
            )
            await self._execute_direct(variant)
        result = await harness_ollama_call(
            bundle,
            self.config,
            variant_id="EXACT_HARNESS",
            runtime_sink=self.runtime_records,
        )
        self._add_result(result)

    async def _run_matrix(
        self,
        bundle: RequestBundle,
        v1_payload: Mapping[str, Any],
    ) -> None:
        variants = build_matrix_variants(
            bundle,
            self.config,
            v1_payload=v1_payload,
        )
        result_by_id: dict[str, dict[str, Any]] = {}
        for variant in variants:
            if variant.execution_path == "direct_ollama":
                result = await self._execute_direct(variant)
                result_by_id[variant.variant_id] = result
            elif variant.execution_path == "model_harness":
                call = await harness_ollama_call(
                    bundle,
                    self.config,
                    variant_id=variant.variant_id,
                    runtime_sink=self.runtime_records,
                )
                result = self._add_result(call)
                result_by_id[variant.variant_id] = result
                await self._reset_model_after_variant(
                    variant.variant_id
                )
            elif variant.execution_path == "alias":
                target = result_by_id.get(
                    "D08_HARNESS_FULL_REQUEST",
                    {},
                )
                result = {
                    "variant_id": variant.variant_id,
                    "title": variant.title,
                    "status": "ALIAS_CONFIRMED",
                    "execution_path": (
                        "same OllamaBenchmarkProvider used by v1 and v2"
                    ),
                    "payload_sha256": sha256_bytes(
                        wire_json_bytes(variant.payload or {})
                    ),
                    "aliased_to": "D08_HARNESS_FULL_REQUEST",
                    "aliased_status": target.get("status"),
                    "reason": (
                        "There is no distinct stateful provider adapter; "
                        "runner.py imports the v1 OllamaBenchmarkProvider."
                    ),
                }
                self.results.append(result)
                result_by_id[variant.variant_id] = result
            elif variant.execution_path == "not_applicable":
                result = {
                    "variant_id": variant.variant_id,
                    "title": variant.title,
                    "status": "NOT_APPLICABLE",
                    "reason": (
                        "No distinct v2 provider adapter exists, so swapping "
                        "v1 payload into it is not technically meaningful."
                    ),
                }
                self.results.append(result)
                result_by_id[variant.variant_id] = result
            elif variant.execution_path == "schema_reduction":
                reduction_results = []
                for reduction in schema_reduction_variants(
                    bundle.payload,
                    bundle.schema,
                ):
                    child = await self._execute_direct(reduction)
                    reduction_results.append(child)
                    if _schema_cause_isolated(reduction_results):
                        break
                result = {
                    "variant_id": variant.variant_id,
                    "title": variant.title,
                    "status": (
                        "COMPLETED"
                        if reduction_results
                        else "NOT_EXECUTED"
                    ),
                    "children": reduction_results,
                    "early_stop": (
                        "causal_fragment_isolated"
                        if _schema_cause_isolated(reduction_results)
                        else ""
                    ),
                }
                self.results.append(result)
                result_by_id[variant.variant_id] = result
            self._flush_incremental()

        direct_full = result_by_id.get(
            "D07_DIRECT_OLLAMA_FULL_REQUEST",
            {},
        )
        if direct_full.get("status") != "SUCCEEDED":
            stream_variant = MatrixVariant(
                "D07S_DIRECT_OLLAMA_FULL_REQUEST_STREAM",
                "Exact full payload with stream enabled for observation",
                bundle.payload,
                bundle.schema,
                "direct_ollama",
                "stream_only",
                request=bundle.resolved_request,
            )
            await self._execute_direct(
                stream_variant,
                stream_override=True,
            )

    async def _execute_direct(
        self,
        variant: MatrixVariant,
        *,
        stream_override: bool | None = None,
    ) -> dict[str, Any]:
        call = await direct_ollama_call(
            variant,
            self.config,
            stream_override=stream_override,
            runtime_sink=self.runtime_records,
        )
        result = self._add_result(call, title=variant.title)
        await self._reset_model_after_variant(variant.variant_id)
        return result

    async def _reset_model_after_variant(
        self,
        variant_id: str,
    ) -> None:
        if not self.config.reset_model_between_variants:
            return
        started = time.perf_counter()
        reset = await asyncio.to_thread(
            reset_ollama_model,
            self.config.model,
            self.config.base_url,
        )
        record = {
            "event": "model_reset_between_variants",
            "captured_at": utc_now(),
            "variant_id": variant_id,
            "duration_ms": round(
                (time.perf_counter() - started) * 1_000,
                3,
            ),
            **reset,
        }
        self.runtime_records.append(record)
        self._flush_incremental()

    def _add_result(
        self,
        call: HttpCallResult,
        *,
        title: str = "",
    ) -> dict[str, Any]:
        result = call.to_dict()
        if title:
            result["title"] = title
        self.results.append(result)
        self.timeline_records.extend(call.timeline)
        if call.exception is not None:
            self.exceptions.append(call.exception)
        self.telemetry.append({
            "utc": utc_now(),
            "variant_id": call.variant_id,
            "status": call.status,
            "execution_path": call.execution_path,
            "duration_ms": call.duration_ms,
            "payload_sha256": call.payload_sha256,
            "payload_bytes": call.payload_bytes,
            "response_bytes": call.response_bytes,
            "response_sha256": call.response_sha256,
            "model_content_chars": call.model_content_chars,
            "model_content_sha256": call.model_content_sha256,
            "done": call.done,
            "done_reason": call.done_reason,
            "input_tokens": call.input_tokens,
            "output_tokens": call.output_tokens,
            "exception_classification": (
                call.exception.get("classification")
                if call.exception
                else ""
            ),
        })
        self._flush_incremental()
        return result

    def _manifest(
        self,
        started_at: str,
        bundle: RequestBundle,
        v1_source: Mapping[str, Any],
        integrity_before: Mapping[str, Any],
    ) -> dict[str, Any]:
        return {
            "diagnostic_version": DIAGNOSTIC_VERSION,
            "started_at": started_at,
            "command_scope": "stateful_provider_path_only",
            "execution_classification": (
                "live_model"
                if self.config.mode in {"exact", "matrix"}
                else "offline"
            ),
            "configuration": {
                **asdict(self.config),
                "output_dir": str(self.config.output_dir),
            },
            "source_stateful_run": (
                DEFAULT_STATEFUL_RUN.relative_to(REPO_ROOT).as_posix()
            ),
            "source_v1_run": (
                DEFAULT_V1_RUN.relative_to(REPO_ROOT).as_posix()
            ),
            "v1_source": dict(v1_source),
            "scenario": bundle.scenario_id,
            "request_reconstruction": bundle.reconstruction,
            "request_hashes": request_hashes(bundle),
            "payload_content_stored": self.config.debug_payload,
            "prompts_stored": self.config.debug_payload,
            "integrity_before": integrity_before,
            "safety": {
                "network": "localhost_ollama_only",
                "tools_executed": False,
                "fixture_materialization": False,
                "project_mutation": False,
                "mission_mutation": False,
                "production_provider_modified": False,
                "production_prompts_modified": False,
                "global_ollama_configuration_modified": False,
            },
        }

    def _flush_incremental(self) -> None:
        self._write_json("matrix_results.json", {
            "diagnostic_version": DIAGNOSTIC_VERSION,
            "results": self.results,
            "in_progress": True,
        })
        self._write_json("exceptions.json", {
            "exceptions": self.exceptions,
            "in_progress": True,
        })
        self._write_jsonl("timeline.jsonl", self.timeline_records)
        self._write_jsonl("ollama_runtime.jsonl", self.runtime_records)
        self._write_jsonl("telemetry.jsonl", self.telemetry)

    def _write_json(self, relative: str, value: Any) -> None:
        path = self.output_dir / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                to_jsonable(value),
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
            newline="\n",
        )

    def _write_jsonl(
        self,
        relative: str,
        values: list[Mapping[str, Any]],
    ) -> None:
        path = self.output_dir / relative
        path.write_text(
            "".join(
                json.dumps(
                    to_jsonable(value),
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
                + "\n"
                for value in values
            ),
            encoding="utf-8",
            newline="\n",
        )


def request_hashes(bundle: RequestBundle) -> dict[str, Any]:
    context_items = [
        {
            "source": item.source,
            "kind": item.kind,
            "content_sha256": item.content_sha256,
        }
        for item in bundle.request.context.items
    ]
    tools = [
        item.content
        for item in bundle.request.context.items
        if item.kind == "tools"
    ]
    messages = bundle.payload.get("messages") or []
    return {
        "system_prompt": {
            "sha256": sha256_text(bundle.request.system_prompt),
            "chars": len(bundle.request.system_prompt),
        },
        "user_prompt": {
            "sha256": sha256_text(bundle.request.user_prompt),
            "chars": len(bundle.request.user_prompt),
        },
        "effective_user_prompt": {
            "sha256": sha256_text(
                str(messages[1]["content"]) if len(messages) > 1 else ""
            ),
            "chars": (
                len(str(messages[1]["content"]))
                if len(messages) > 1
                else 0
            ),
        },
        "context": {
            "sha256": bundle.context_hash,
            "items_sha256": sha256_json(context_items),
            "chars": bundle.request.context.total_chars,
        },
        "schema": {
            "sha256": sha256_json(bundle.schema),
            "bytes": len(canonical_json_bytes(bundle.schema)),
        },
        "messages": {
            "sha256": sha256_json(messages),
            "count": len(messages),
        },
        "tools": {
            "top_level_sha256": sha256_json(
                bundle.payload.get("tools") or []
            ),
            "top_level_count": len(bundle.payload.get("tools") or []),
            "context_representation_sha256": sha256_json(tools),
            "context_representation_count": len(tools),
        },
        "options": {
            "sha256": sha256_json(bundle.payload.get("options") or {}),
            "value": bundle.payload.get("options") or {},
        },
        "payload": {
            "sha256": sha256_bytes(bundle.payload_bytes),
            "bytes": len(bundle.payload_bytes),
        },
    }


def _schema_cause_isolated(results: list[Mapping[str, Any]]) -> bool:
    by_id = {item.get("variant_id"): item for item in results}
    core = by_id.get("D12_R3_CORE_DECISION")
    arguments = by_id.get("D12_R4_CORE_PLUS_ARGUMENTS")
    if core and arguments:
        return (
            core.get("status") == "SUCCEEDED"
            and arguments.get("status") != "SUCCEEDED"
        )
    return False


def _result_map(
    results: list[Mapping[str, Any]],
) -> dict[str, Mapping[str, Any]]:
    mapped = {
        str(item.get("variant_id")): item
        for item in results
        if item.get("variant_id")
    }
    parent = mapped.get("D12_SCHEMA_COMPLEXITY_REDUCTION")
    if parent:
        for item in parent.get("children") or []:
            mapped[str(item.get("variant_id"))] = item
    return mapped


def assess_hypotheses(
    results: list[Mapping[str, Any]],
    v1_structure: Mapping[str, Any],
    v2_structure: Mapping[str, Any],
    runtime_records: list[Mapping[str, Any]],
) -> dict[str, Any]:
    by_id = _result_map(results)

    def status(variant: str) -> str:
        return str(by_id.get(variant, {}).get("status") or "NOT_TESTED")

    simple = status("D01_BASELINE_SIMPLE")
    no_schema = status("D02_STATEFUL_PROMPT_NO_SCHEMA")
    minimal = status("D03_STATEFUL_PROMPT_MINIMAL_SCHEMA")
    full = status("D07_DIRECT_OLLAMA_FULL_REQUEST")
    harness = status("D08_HARNESS_FULL_REQUEST")
    streamed = by_id.get(
        "D07S_DIRECT_OLLAMA_FULL_REQUEST_STREAM",
        {},
    )
    runtime_pressure = _runtime_pressure(runtime_records)
    assessments = {
        "H1_SCHEMA_COMPLEXITY": _hypothesis(
            (
                "SUPPORTED"
                if minimal == "SUCCEEDED" and full != "SUCCEEDED"
                else "NOT_SUPPORTED"
                if full == "SUCCEEDED"
                else "NOT_TESTED"
            ),
            {
                "minimal_schema": minimal,
                "full_schema": full,
                "schema_metrics_sha256": v2_structure.get(
                    "schema",
                    {},
                ).get("sha256"),
            },
        ),
        "H2_PROVIDER_ADAPTER": _hypothesis(
            (
                "NOT_SUPPORTED"
                if v1_structure.get("provider_adapter")
                == v2_structure.get("provider_adapter")
                else "PARTIALLY_SUPPORTED"
            ),
            {
                "v1_adapter": v1_structure.get("provider_adapter"),
                "v2_adapter": v2_structure.get("provider_adapter"),
                "harness_result": harness,
                "direct_result": full,
            },
        ),
        "H3_STREAM_HANDLING": _hypothesis(
            _stream_hypothesis(full, streamed),
            {
                "buffered_result": full,
                "stream_result": streamed.get("status", "NOT_TESTED"),
                "stream_first_token": _event_observed(
                    streamed,
                    "T17",
                ),
            },
        ),
        "H4_TOOL_AND_FORMAT_COMBINATION": _hypothesis(
            _tool_format_hypothesis(by_id),
            {
                "no_tools": status("D04_FULL_SCHEMA_NO_TOOLS"),
                "one_tool": status("D05_FULL_SCHEMA_ONE_TOOL"),
                "all_tools": status("D06_FULL_SCHEMA_ALL_TOOLS"),
                "top_level_tool_count": v2_structure.get("tool_count"),
            },
        ),
        "H5_CONTEXT_OR_OUTPUT_OPTIONS": _hypothesis(
            (
                "NOT_SUPPORTED"
                if simple == "SUCCEEDED"
                and no_schema == "SUCCEEDED"
                else "PARTIALLY_SUPPORTED"
                if simple == "SUCCEEDED"
                else "NOT_TESTED"
            ),
            {
                "same_generation_options_baseline": True,
                "baseline": simple,
                "stateful_no_schema": no_schema,
            },
        ),
        "H6_HTTP_TIMEOUT_LAYER": _hypothesis(
            _timeout_hypothesis(by_id),
            {
                "direct_exception": by_id.get(
                    "D07_DIRECT_OLLAMA_FULL_REQUEST",
                    {},
                ).get("exception"),
                "harness_exception": by_id.get(
                    "D08_HARNESS_FULL_REQUEST",
                    {},
                ).get("exception"),
            },
        ),
        "H7_OLLAMA_RUNTIME": _hypothesis(
            (
                "PARTIALLY_SUPPORTED"
                if runtime_pressure["pressure_observed"]
                else "NOT_SUPPORTED"
                if runtime_records
                else "NOT_TESTED"
            ),
            runtime_pressure,
        ),
        "H8_HARNESS_RESPONSE_PATH": _hypothesis(
            (
                "NOT_SUPPORTED"
                if (
                    full == harness
                    or full == "READ_TIMEOUT"
                    and harness == "PROVIDER_FAILED"
                    and (
                        by_id.get(
                            "D08_HARNESS_FULL_REQUEST",
                            {},
                        ).get("exception")
                        or {}
                    ).get("classification")
                    == "READ_TIMEOUT"
                )
                else "PARTIALLY_SUPPORTED"
                if full != "NOT_TESTED" and harness != "NOT_TESTED"
                else "NOT_TESTED"
            ),
            {"direct": full, "harness": harness},
        ),
        "H9_REQUEST_SERIALIZATION": _hypothesis(
            "NOT_SUPPORTED",
            {
                "payload_serialized": True,
                "payload_bytes": v2_structure.get("payload_bytes"),
                "payload_sha256": v2_structure.get("payload_sha256"),
            },
        ),
        "H10_MODEL_COLD_OR_RELOAD": _hypothesis(
            (
                "PARTIALLY_SUPPORTED"
                if runtime_pressure.get("model_reload_observed")
                else "NOT_SUPPORTED"
                if runtime_records
                else "NOT_TESTED"
            ),
            {
                "model_reload_observed": runtime_pressure.get(
                    "model_reload_observed"
                ),
                "loaded_context_lengths": runtime_pressure.get(
                    "loaded_context_lengths"
                ),
            },
        ),
    }
    return assessments


def _hypothesis(status: str, evidence: Mapping[str, Any]) -> dict[str, Any]:
    return {"status": status, "evidence": redact_mapping(dict(evidence))}


def _event_observed(result: Mapping[str, Any], stage: str) -> bool:
    return any(
        item.get("stage") == stage and item.get("status") == "OBSERVED"
        for item in result.get("timeline") or []
    )


def _stream_hypothesis(
    full_status: str,
    streamed: Mapping[str, Any],
) -> str:
    stream_status = str(streamed.get("status") or "NOT_TESTED")
    if stream_status == "NOT_TESTED":
        return "NOT_TESTED"
    first_token = _event_observed(streamed, "T17")
    if full_status != "SUCCEEDED" and first_token:
        return "SUPPORTED"
    if full_status != stream_status:
        return "PARTIALLY_SUPPORTED"
    return "NOT_SUPPORTED"


def _tool_format_hypothesis(
    by_id: Mapping[str, Mapping[str, Any]],
) -> str:
    no_tools = str(
        by_id.get("D04_FULL_SCHEMA_NO_TOOLS", {}).get("status")
    )
    one = str(
        by_id.get("D05_FULL_SCHEMA_ONE_TOOL", {}).get("status")
    )
    all_tools = str(
        by_id.get("D06_FULL_SCHEMA_ALL_TOOLS", {}).get("status")
    )
    if "NOT_TESTED" in {no_tools, one, all_tools}:
        return "NOT_TESTED"
    if no_tools == "SUCCEEDED" and (
        one != "SUCCEEDED" or all_tools != "SUCCEEDED"
    ):
        return "SUPPORTED"
    if all_tools == "SUCCEEDED":
        return "NOT_SUPPORTED"
    if no_tools and one and all_tools:
        return "PARTIALLY_SUPPORTED"
    return "NOT_TESTED"


def _timeout_hypothesis(
    by_id: Mapping[str, Mapping[str, Any]],
) -> str:
    direct = by_id.get("D07_DIRECT_OLLAMA_FULL_REQUEST", {})
    exception = direct.get("exception") or {}
    if exception.get("classification") == "READ_TIMEOUT":
        if not _event_observed(direct, "T14"):
            return "SUPPORTED"
        return "PARTIALLY_SUPPORTED"
    if exception:
        return "NOT_SUPPORTED"
    return "NOT_TESTED"


def _runtime_pressure(
    records: list[Mapping[str, Any]],
) -> dict[str, Any]:
    gpu_free: list[int] = []
    contexts: set[int] = set()
    loaded_presence: list[bool] = []
    for record in records:
        gpu = record.get("gpu")
        if isinstance(gpu, Mapping):
            value = _optional_int(gpu.get("memory_free_mib"))
            if value is not None:
                gpu_free.append(value)
        endpoint = record.get("endpoint")
        if not isinstance(endpoint, Mapping):
            continue
        models = (
            (endpoint.get("ollama_ps") or {}).get("models") or []
        )
        loaded_presence.append(bool(models))
        for model in models:
            context = _optional_int(model.get("context_length"))
            if context is not None:
                contexts.add(context)
    return {
        "pressure_observed": (
            bool(gpu_free) and min(gpu_free) < 256
        ),
        "gpu_free_mib_min": min(gpu_free) if gpu_free else None,
        "gpu_free_mib_max": max(gpu_free) if gpu_free else None,
        "loaded_context_lengths": sorted(contexts),
        "model_reload_observed": (
            bool(loaded_presence)
            and any(loaded_presence)
            and not all(loaded_presence)
        ),
    }


def derive_diagnosis(
    results: list[Mapping[str, Any]],
    hypotheses: Mapping[str, Any],
    integrity: Mapping[str, Any],
    reconstruction: Mapping[str, Any],
) -> dict[str, Any]:
    if not integrity.get("unchanged"):
        return {
            "decision": "REGRESSION_DETECTED",
            "root_cause": "Diagnostic integrity changed.",
            "blocking_phase": "UNKNOWN",
            "minimum_safe_fix": "Do not change production until reviewed.",
            "confidence": "high",
        }
    by_id = _result_map(results)
    direct = by_id.get("D07_DIRECT_OLLAMA_FULL_REQUEST", {})
    harness = by_id.get("D08_HARNESS_FULL_REQUEST", {})
    direct_exception = direct.get("exception") or {}
    exact_reproduced = (
        reconstruction.get("context_hash_matches")
        and reconstruction.get("request_fingerprint_matches")
        and (
            reconstruction.get("configuration_equivalent") or {}
        ).get("equivalent")
    )
    if (
        exact_reproduced
        and direct_exception.get("classification") == "READ_TIMEOUT"
    ):
        headers = _event_observed(direct, "T14")
        first_byte = _event_observed(direct, "T15")
        schema_status = (
            hypotheses.get("H1_SCHEMA_COMPLEXITY") or {}
        ).get("status")
        if schema_status == "SUPPORTED":
            cause = (
                "The exact request is accepted by the HTTP client but Ollama "
                "does not complete the full structured-schema request within "
                "the read timeout; minimal/no-schema controls complete."
            )
            confidence = "high"
        else:
            cause = (
                "The exact request blocks inside the Ollama response window "
                "after request upload and before a complete response."
            )
            confidence = "medium"
        return {
            "decision": (
                "MODEL_HARNESS_STATEFUL_PROVIDER_PATH_DIAGNOSED"
                if schema_status == "SUPPORTED"
                else "MODEL_HARNESS_STATEFUL_PROVIDER_PATH_PARTIALLY_DIAGNOSED"
            ),
            "root_cause": cause,
            "blocking_phase": (
                "after_response_headers_before_first_body_byte"
                if headers and not first_byte
                else "after_request_body_before_response_headers"
                if not headers
                else "during_response_body"
            ),
            "component": "Ollama generation/structured-output path",
            "harness_status": harness.get("status"),
            "minimum_safe_fix": (
                "Use the smallest schema fragment identified by D12 or "
                "change schema transport only after a regression test proves "
                "the exact stateful decision and v1 remain valid."
            ),
            "production_fix_implemented": False,
            "confidence": confidence,
        }
    if not results:
        return {
            "decision": "IMPLEMENTATION_INCOMPLETE",
            "root_cause": "No live diagnostic path was executed.",
            "blocking_phase": "NOT_TESTED",
            "minimum_safe_fix": "Run exact or matrix mode.",
            "confidence": "high",
        }
    return {
        "decision": "ROOT_CAUSE_NOT_IDENTIFIED",
        "root_cause": "The observed controls do not isolate one cause.",
        "blocking_phase": "UNKNOWN",
        "minimum_safe_fix": "Do not modify production; extend one controlled diagnostic dimension.",
        "confidence": "low",
    }


def render_report(
    summary: Mapping[str, Any],
    v1: Mapping[str, Any],
    v2: Mapping[str, Any],
    diff: Mapping[str, Any],
    results: list[Mapping[str, Any]],
    hypotheses: Mapping[str, Any],
    integrity: Mapping[str, Any],
) -> str:
    diagnosis = summary["diagnosis"]
    by_id = _result_map(results)
    direct = by_id.get("D07_DIRECT_OLLAMA_FULL_REQUEST", {})
    harness = by_id.get("D08_HARNESS_FULL_REQUEST", {})
    stream = by_id.get(
        "D07S_DIRECT_OLLAMA_FULL_REQUEST_STREAM",
        {},
    )
    matrix_lines = [
        "| Variant | Path | Status | Duration ms | First byte | First token |",
        "|---|---|---|---:|---|---|",
    ]
    for item in results:
        variant_id = str(item.get("variant_id") or "")
        if variant_id == "D12_SCHEMA_COMPLEXITY_REDUCTION":
            matrix_lines.append(
                f"| `{variant_id}` | schema reduction | "
                f"{item.get('status')} | - | - | - |"
            )
            for child in item.get("children") or []:
                matrix_lines.append(_matrix_report_row(child))
            continue
        matrix_lines.append(_matrix_report_row(item))
    hypothesis_lines = [
        f"- `{name}`: **{item['status']}**; evidence hash "
        f"`{sha256_json(item['evidence'])}`."
        for name, item in hypotheses.items()
    ]
    schema = summary["schema_analysis"]
    lines = [
        "# Stateful Provider Path Diagnostic",
        "",
        "## 1. Resumo executivo",
        "",
        f"- Decision: **{summary['decision']}**.",
        f"- Root cause: {diagnosis['root_cause']}",
        f"- Blocking phase: `{diagnosis['blocking_phase']}`.",
        f"- Confidence: `{diagnosis['confidence']}`.",
        "- No production fix was implemented.",
        "",
        "## 2. Problema reproduzido",
        "",
        f"- Scenario: `{summary['scenario']}`.",
        f"- Model: `{summary['model']}`.",
        f"- Historical request fingerprint matched: "
        f"`{summary['reconstruction']['request_fingerprint_matches']}`.",
        f"- Historical context hash matched: "
        f"`{summary['reconstruction']['context_hash_matches']}`.",
        "",
        "## 3. Request exato analisado",
        "",
        f"- Payload bytes: `{summary['request_hashes']['payload']['bytes']}`.",
        f"- Payload SHA-256: `{summary['request_hashes']['payload']['sha256']}`.",
        f"- Schema SHA-256: `{summary['request_hashes']['schema']['sha256']}`.",
        f"- Tools in top-level payload: "
        f"`{summary['request_hashes']['tools']['top_level_count']}`.",
        "- Tool contracts are represented in selected context and in schema enums.",
        "",
        "## 4. Timeline",
        "",
        f"- Direct exact status: `{direct.get('status', 'NOT_TESTED')}`.",
        f"- Response headers observed: `{_event_observed(direct, 'T14')}`.",
        f"- First byte observed: `{_event_observed(direct, 'T15')}`.",
        f"- First token observed: `{_event_observed(direct, 'T17')}`.",
        "- Unavailable phases are recorded as `NOT_OBSERVABLE`, never inferred.",
        "",
        "## 5. Tipo de exceção",
        "",
        f"- Direct: `{(direct.get('exception') or {}).get('classification', 'none')}` "
        f"(`{(direct.get('exception') or {}).get('class', 'none')}`).",
        f"- Harness: `{(harness.get('exception') or {}).get('classification', 'none')}` "
        f"(`{(harness.get('exception') or {}).get('class', 'none')}`).",
        "",
        "## 6. Comparação v1 vs v2",
        "",
        f"- Same endpoint: `{diff['same_endpoint']}`.",
        f"- Same provider adapter: `{diff['same_adapter']}`.",
        f"- Same HTTP client: `{diff['same_http_client']}`.",
        f"- V1 payload bytes: `{v1['payload_bytes']}`.",
        f"- V2 payload bytes: `{v2['payload_bytes']}`.",
        f"- V1 output cap: `{v1['options'].get('num_predict')}`.",
        f"- V2 output cap: `{v2['options'].get('num_predict')}`.",
        "",
        "## 7. Estrutura e complexidade do schema",
        "",
        f"- Bytes: `{schema['bytes']}`.",
        f"- Nodes: `{schema['nodes']}`.",
        f"- Maximum depth: `{schema['maximum_depth']}`.",
        f"- Properties: `{schema['properties']}`.",
        f"- Required entries: `{schema['required']}`.",
        f"- Enums / values: `{schema['enums']}` / `{schema['enum_values']}`.",
        f"- Potential constructions: "
        f"`{json.dumps(schema['potentially_problematic'], ensure_ascii=False)}`.",
        "- Heuristics are not treated as proof; matrix controls decide support.",
        "",
        "## 8. Resultados da matriz",
        "",
        *matrix_lines,
        "",
        "## 9. Chamada direta Ollama",
        "",
        f"- Status: `{direct.get('status', 'NOT_TESTED')}`.",
        f"- Payload SHA-256: `{direct.get('payload_sha256', '')}`.",
        f"- Response bytes: `{direct.get('response_bytes', 0)}`.",
        "",
        "## 10. Chamada via ModelHarness",
        "",
        f"- Status: `{harness.get('status', 'NOT_TESTED')}`.",
        f"- Exception preserved: `{bool(harness.get('exception'))}`.",
        "- The existing provider buffers `stream=false`; internal HTTP milestones "
        "are therefore marked `NOT_OBSERVABLE` on this path.",
        "",
        "## 11. Streaming e partial output",
        "",
        f"- Streaming probe status: `{stream.get('status', 'NOT_TESTED')}`.",
        f"- First streamed token observed: `{_event_observed(stream, 'T17')}`.",
        f"- Partial bytes: `{stream.get('response_bytes', 0)}`.",
        "",
        "## 12. Estado do Ollama",
        "",
        "- Runtime snapshots before, during, and after calls are in "
        "`ollama_runtime.jsonl`.",
        "",
        "## 13. GPU, VRAM, RAM e CPU",
        "",
        "- Resource measurements are correlated by `correlation_id` and "
        "`variant_id`; unavailable values are left absent.",
        "",
        "## 14. Hipóteses avaliadas",
        "",
        *hypothesis_lines,
        "",
        "## 15. Causa raiz",
        "",
        diagnosis["root_cause"],
        "",
        "## 16. Correção proposta",
        "",
        diagnosis["minimum_safe_fix"],
        "",
        "## 17. Correção implementada",
        "",
        "None. Diagnosis preceded any production change, as required.",
        "",
        "## 18. Validação após correção",
        "",
        "Not applicable because no production correction was implemented.",
        "",
        "## 19. Testes",
        "",
        "Offline unit and integration results are recorded by the invoking "
        "engineering validation; live calls are isolated from the normal suite.",
        "",
        "## 20. Integridade",
        "",
        f"- Unchanged: `{integrity['unchanged']}`.",
        f"- Changed trees: `{list(integrity['tree_changes'])}`.",
        f"- Changed critical files: "
        f"`{list(integrity['critical_file_changes'])}`.",
        "",
        "## 21. Regressões",
        "",
        (
            "No protected runtime tree or critical production file changed."
            if integrity["unchanged"]
            else "A protected integrity regression was detected."
        ),
        "",
        "## 22. Limitações",
        "",
        "- The historical failed run did not store raw prompts or provider "
        "payloads; exact reconstruction is proven by deterministic builders, "
        "matching context hash, matching request fingerprint, and matching "
        "configuration.",
        "- D10 is not applicable because stateful v2 reuses the v1 provider.",
        "",
        "## 23. Próximo passo",
        "",
        diagnosis["minimum_safe_fix"],
        "",
        "## 24. Decisão",
        "",
        f"**{summary['decision']}**",
        "",
    ]
    return "\n".join(lines)


def _matrix_report_row(item: Mapping[str, Any]) -> str:
    return (
        f"| `{item.get('variant_id', '')}` | "
        f"{item.get('execution_path', '')} | "
        f"{item.get('status', '')} | "
        f"{item.get('duration_ms', '-')} | "
        f"{_event_observed(item, 'T15')} | "
        f"{_event_observed(item, 'T17')} |"
    )
