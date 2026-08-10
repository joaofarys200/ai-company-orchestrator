from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
import time
import uuid
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.model_harness import (  # noqa: E402
    ModelRequest,
    ModelRoute,
    ProviderResult,
)
from backend.model_harness.benchmarking import (  # noqa: E402
    BenchmarkConfig,
    BenchmarkMode,
    BenchmarkScenario,
    ScenarioStatus,
    benchmark_scenarios,
)
from backend.model_harness.benchmarking.contracts import (  # noqa: E402
    sha256_json,
    to_jsonable,
)
from backend.model_harness.benchmarking.runner import (  # noqa: E402
    StatefulBenchmarkRunner,
    condition_stateful_transition_request,
    integrity_snapshot,
    write_json,
)
from backend.model_harness.benchmarking.tools import (  # noqa: E402
    create_read_only_tool_registry,
)
from scripts.model_harness_benchmark import (  # noqa: E402
    BenchmarkConfig as OllamaConfig,
    OllamaBenchmarkProvider,
    _assert_output_location,
    sha256_file,
)


DIAGNOSTIC_VERSION = "stateful_tool_sequence_semantic_diagnostic_v1"
SCENARIO_ID = "A01_FIND_RELEVANT_FILE"
REPETITIONS = 2


@dataclass(frozen=True)
class SequenceVariant:
    variant_id: str
    title: str
    explicit_state: bool = False
    structured_prevalidation: bool = False
    conditioned_schema: bool = False
    semantic_retry: bool = False


VARIANTS = (
    SequenceVariant("S01_CURRENT", "Current behavior"),
    SequenceVariant(
        "S02_EXPLICIT_STATE",
        "Explicit required, completed and remaining tools",
        explicit_state=True,
    ),
    SequenceVariant(
        "S03_PREVALIDATION",
        "Structured pre-tool rejection of premature FINISH",
        explicit_state=True,
        structured_prevalidation=True,
    ),
    SequenceVariant(
        "S04_CONDITIONED_SCHEMA",
        "Schema conditioned by the current legal transition",
        explicit_state=True,
        conditioned_schema=True,
    ),
    SequenceVariant(
        "S05_SEMANTIC_RETRY",
        "One retry with rejection reason and next required tool",
        explicit_state=True,
        structured_prevalidation=True,
        semantic_retry=True,
    ),
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def scenario_a01() -> BenchmarkScenario:
    return next(
        scenario
        for scenario in benchmark_scenarios(
            BenchmarkMode.STANDARD,
            include_fault_injection=False,
        )
        if scenario.scenario_id == SCENARIO_ID
    )


def prompt_sequence_state(payload: Mapping[str, Any]) -> dict[str, Any]:
    required = list(
        payload.get("required_tools")
        or payload.get("required_tools_before_finish")
        or ()
    )
    completed = list(
        payload.get("completed_tools")
        or payload.get("tools_already_called")
        or ()
    )
    remaining = [
        tool
        for tool in required
        if tool != "finish" and tool not in completed
    ]
    known = payload.get("known_references") or ()
    minimum = int(payload.get("minimum_evidence_references") or 0)
    return {
        "required_tools": required,
        "completed_tools": completed,
        "remaining_tools": remaining,
        "finish_allowed": (
            not remaining and len(known) >= minimum
        ),
    }


def decode_prompt_payload(prompt: str) -> tuple[dict[str, Any], str]:
    decoder = json.JSONDecoder()
    start = len(prompt) - len(prompt.lstrip())
    value, end = decoder.raw_decode(prompt, idx=start)
    if not isinstance(value, dict):
        raise ValueError("Stateful prompt must start with a JSON object.")
    return value, prompt[end:]


def encode_prompt_payload(
    payload: Mapping[str, Any],
    suffix: str = "",
) -> str:
    return (
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + suffix
    )


def explicit_state_request(request: ModelRequest) -> ModelRequest:
    payload, suffix = decode_prompt_payload(request.user_prompt)
    state = prompt_sequence_state(payload)
    payload.pop("tools_already_called", None)
    payload.pop("required_tools_before_finish", None)
    payload.pop("required_tools_remaining", None)
    payload.update(state)
    return replace(
        request,
        system_prompt=(
            request.system_prompt
            + " The fields required_tools, completed_tools, "
            "remaining_tools and finish_allowed are authoritative state, "
            "not suggestions."
        ),
        user_prompt=encode_prompt_payload(payload, suffix),
        request_id=uuid.uuid4().hex,
    )


def conditioned_schema_request(request: ModelRequest) -> ModelRequest:
    return condition_stateful_transition_request(
        request,
        create_read_only_tool_registry(),
    )


def premature_finish(
    raw_text: str,
    request: ModelRequest,
) -> dict[str, Any] | None:
    try:
        value = json.loads(raw_text)
        payload, _suffix = decode_prompt_payload(request.user_prompt)
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    state = prompt_sequence_state(payload)
    if (
        str(value.get("decision") or "").upper() != "FINISH"
        or not state["remaining_tools"]
    ):
        return None
    return {
        "code": "PREMATURE_FINISH",
        "reason": (
            "FINISH is not allowed while required tools remain: "
            + ", ".join(state["remaining_tools"])
        ),
        "next_required_tool": state["remaining_tools"][0],
        "remaining_tools": state["remaining_tools"],
    }


def semantic_retry_request(
    request: ModelRequest,
    rejection: Mapping[str, Any],
) -> ModelRequest:
    payload, suffix = decode_prompt_payload(request.user_prompt)
    payload["semantic_rejection"] = {
        **dict(rejection),
        "required_action": (
            "Return one complete corrected decision. Do not use FINISH "
            "until remaining_tools is empty."
        ),
    }
    return replace(
        request,
        system_prompt=(
            request.system_prompt
            + " The rejected decision did not advance state. Correct it "
            "using semantic_rejection; tool arguments remain your "
            "responsibility."
        ),
        user_prompt=encode_prompt_payload(payload, suffix),
        request_id=uuid.uuid4().hex,
    )


class SemanticVariantProvider:
    name = "ollama"

    def __init__(
        self,
        variant: SequenceVariant,
        delegate: OllamaBenchmarkProvider,
    ):
        self.variant = variant
        self.delegate = delegate
        self.default_model = delegate.default_model
        self.attempts: list[dict[str, Any]] = []

    @property
    def runner_guard_events(self) -> list[dict[str, Any]]:
        return self.delegate.runner_guard_events

    async def generate(
        self,
        request: ModelRequest,
        route: ModelRoute,
        progress,
    ) -> ProviderResult:
        actual = request
        if self.variant.explicit_state:
            actual = explicit_state_request(actual)
        if (
            self.variant.conditioned_schema
            and actual.metadata.get("transition_policy")
            != "contract_driven"
        ):
            actual = conditioned_schema_request(actual)

        result = await self._call(
            actual,
            route,
            progress,
            semantic_retry=False,
        )
        rejection = premature_finish(result.raw_text, actual)
        if (
            self.variant.semantic_retry
            and rejection is not None
        ):
            corrected = semantic_retry_request(actual, rejection)
            return await self._call(
                corrected,
                route,
                progress,
                semantic_retry=True,
                rejection=rejection,
            )
        return result

    async def _call(
        self,
        request: ModelRequest,
        route: ModelRoute,
        progress,
        *,
        semantic_retry: bool,
        rejection: Mapping[str, Any] | None = None,
    ) -> ProviderResult:
        started = time.perf_counter()
        record = {
            "variant_id": self.variant.variant_id,
            "repetition": int(request.metadata["repetition"]),
            "step": int(request.metadata["step"]),
            "semantic_retry": semantic_retry,
            "request_fingerprint": request.fingerprint(),
            "schema_sha256": sha256_json(
                request.expected_output.schema
                if request.expected_output is not None
                else None
            ),
            "state": prompt_sequence_state(
                decode_prompt_payload(request.user_prompt)[0]
            ),
            "rejection": dict(rejection or {}),
        }
        try:
            result = await self.delegate.generate(
                request,
                route,
                progress,
            )
        except Exception as exc:
            record.update({
                "status": "PROVIDER_FAILED",
                "error_type": type(exc).__name__,
                "duration_ms": round(
                    (time.perf_counter() - started) * 1_000,
                    3,
                ),
            })
            self.attempts.append(record)
            raise
        record.update({
            "status": "SUCCEEDED",
            "duration_ms": round(
                (time.perf_counter() - started) * 1_000,
                3,
            ),
            "output_sha256": hashlib.sha256(
                result.raw_text.encode("utf-8")
            ).hexdigest(),
            "decision": _safe_decision(result.raw_text),
            "premature_finish": (
                premature_finish(result.raw_text, request) is not None
            ),
            "input_tokens": result.usage.input_tokens,
            "output_tokens": result.usage.output_tokens,
        })
        self.attempts.append(record)
        return result


def _safe_decision(raw_text: str) -> Mapping[str, Any] | None:
    try:
        value = json.loads(raw_text)
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    return value if isinstance(value, Mapping) else None


def structured_prevalidation_events(
    variant: SequenceVariant,
    attempts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not variant.structured_prevalidation:
        return []
    events = []
    for attempt in attempts:
        if not attempt.get("premature_finish"):
            continue
        remaining = list(attempt["state"]["remaining_tools"])
        events.append({
            "code": "PREMATURE_FINISH",
            "stage": "PRE_TOOL",
            "remaining_tools": remaining,
            "next_required_tool": remaining[0] if remaining else "",
            "tool_executed": False,
        })
    return events


def _repetition_result(
    variant,
    scenario,
    result,
    steps,
    attempts: list[dict[str, Any]],
) -> dict[str, Any]:
    sequence = list(result.tools_called)
    premature = sum(
        bool(attempt.get("premature_finish"))
        for attempt in attempts
    )
    repeated = len(sequence) - len(set(sequence))
    timeouts = sum(
        "timeout" in str(attempt.get("error_type") or "").casefold()
        for attempt in attempts
    )
    exact_sequence = sequence == list(scenario.required_tools)
    recovered = (
        result.status == ScenarioStatus.PASS
        and exact_sequence
        and repeated == 0
        and timeouts == 0
    )
    strict = recovered and premature == 0
    return {
        "repetition": result.repetition,
        "strict_pass": strict,
        "recovered_sequence": recovered,
        "scenario_status": result.status.value,
        "stop_reason": result.stop_reason.value,
        "expected_sequence": list(scenario.required_tools),
        "actual_sequence": sequence,
        "premature_finish_attempts": premature,
        "repeated_tool_calls": repeated,
        "timeouts": timeouts,
        "model_calls": len(attempts),
        "semantic_retries": sum(
            bool(attempt["semantic_retry"]) for attempt in attempts
        ),
        "prevalidation_events": structured_prevalidation_events(
            variant,
            attempts,
        ),
        "errors": list(result.errors),
        "scenario_result": to_jsonable(result),
        "steps": [to_jsonable(step) for step in steps],
        "provider_attempts": attempts,
    }


def summarize_variant(
    variant: SequenceVariant,
    repetitions: list[dict[str, Any]],
    provider: SemanticVariantProvider,
) -> dict[str, Any]:
    return {
        "variant": to_jsonable(variant),
        "repetitions": repetitions,
        "strict_consecutive_success": all(
            result["strict_pass"] for result in repetitions
        ),
        "recovered_consecutive_sequence": all(
            result["recovered_sequence"] for result in repetitions
        ),
        "total_model_calls": sum(
            result["model_calls"] for result in repetitions
        ),
        "total_premature_finish_attempts": sum(
            result["premature_finish_attempts"]
            for result in repetitions
        ),
        "total_repeated_tool_calls": sum(
            result["repeated_tool_calls"] for result in repetitions
        ),
        "total_timeouts": sum(
            result["timeouts"] for result in repetitions
        ),
        "runner_guard": provider.runner_guard_events,
    }


def diagnostic_conclusion(
    variants: list[dict[str, Any]],
    *,
    integrity_unchanged: bool,
) -> tuple[str, str]:
    if not integrity_unchanged:
        return (
            "STATEFUL_TOOL_SEQUENCE_DIAGNOSTIC_INVALID",
            "Integrity changed during a read-only diagnostic.",
        )
    strict = [
        result["variant"]["variant_id"]
        for result in variants
        if result["strict_consecutive_success"]
    ]
    if strict:
        explanations = {
            "S01_CURRENT": "The current representation was sufficient.",
            "S02_EXPLICIT_STATE": (
                "Explicit sequence state was the first sufficient mechanism."
            ),
            "S03_PREVALIDATION": (
                "S03 has no additional model-facing information over S02; "
                "the difference requires a nondeterminism review."
            ),
            "S04_CONDITIONED_SCHEMA": (
                "The contract-conditioned transition schema was the first "
                "sufficient mechanism."
            ),
            "S05_SEMANTIC_RETRY": (
                "Semantic retry was the first strict sufficient mechanism."
            ),
        }
        return (
            "STATEFUL_TOOL_SEQUENCE_SEMANTICS_VALIDATED",
            explanations[strict[0]],
        )
    recovered = any(
        result["recovered_consecutive_sequence"]
        for result in variants
    )
    if recovered:
        return (
            "STATEFUL_TOOL_SEQUENCE_RECOVERABLE_NOT_STRICT",
            (
                "The sequence was recovered twice, but a premature FINISH "
                "attempt violated the strict criterion."
            ),
        )
    return (
        "STATEFUL_TOOL_SEQUENCE_SEMANTICS_NOT_VALIDATED",
        "No tested representation produced the required sequence twice.",
    )


def render_report(summary: Mapping[str, Any]) -> str:
    lines = [
        "# Stateful Tool Sequence Semantic Diagnostic",
        "",
        f"- Scenario: `{summary['scenario_id']}` only.",
        f"- Model: `{summary['model']}`.",
        "- Semantic Context Builder: not integrated.",
        "- Tool execution: temporary read-only FixtureSandbox only.",
        "",
        "| Variant | Strict 2/2 | Recovered 2/2 | Calls | Early FINISH | Repeats | Timeouts |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for item in summary["variants"]:
        lines.append(
            "| {id} | {strict} | {recovered} | {calls} | {early} | "
            "{repeats} | {timeouts} |".format(
                id=item["variant"]["variant_id"],
                strict="yes" if item["strict_consecutive_success"] else "no",
                recovered=(
                    "yes"
                    if item["recovered_consecutive_sequence"]
                    else "no"
                ),
                calls=item["total_model_calls"],
                early=item["total_premature_finish_attempts"],
                repeats=item["total_repeated_tool_calls"],
                timeouts=item["total_timeouts"],
            )
        )
    lines.extend((
        "",
        f"- Decision: `{summary['decision']}`.",
        f"- Conclusion: {summary['conclusion']}",
        f"- Integrity unchanged: `{summary['integrity_unchanged']}`.",
        "",
        "The diagnostic never executes productive tools. S04 represents the "
        "single legal transition and public reference contract in the JSON "
        "schema. S05 reports one concrete rejection and next obligation "
        "without executing it.",
        "",
    ))
    return "\n".join(lines)


async def run_diagnostic(
    *,
    model: str,
    output_dir: Path,
    timeout_seconds: float,
    variant_ids: tuple[str, ...] = (),
) -> dict[str, Any]:
    _assert_output_location(output_dir)
    if output_dir.exists():
        raise FileExistsError(f"Diagnostic output exists: {output_dir}")
    output_dir.mkdir(parents=True)
    scenario = scenario_a01()
    selected_variants = tuple(
        variant
        for variant in VARIANTS
        if not variant_ids or variant.variant_id in variant_ids
    )
    unknown_variants = set(variant_ids) - {
        variant.variant_id for variant in VARIANTS
    }
    if unknown_variants:
        raise ValueError(
            "Unknown variants: " + ", ".join(sorted(unknown_variants))
        )
    if not selected_variants:
        raise ValueError("At least one diagnostic variant is required.")
    before = integrity_snapshot()
    started_at = utc_now()
    started = time.perf_counter()
    write_json(output_dir / "manifest.json", {
        "diagnostic_version": DIAGNOSTIC_VERSION,
        "started_at": started_at,
        "scenario_id": scenario.scenario_id,
        "fixture_sha256": scenario.fixture.content_sha256,
        "model": model,
        "configuration": {
            "context_tokens": 8_192,
            "max_output_tokens": 1_024,
            "temperature": 0.0,
            "top_p": 0.8,
            "seed": 42,
            "think": False,
            "stream": False,
            "timeout_seconds": timeout_seconds,
            "repetitions": REPETITIONS,
        },
        "variants": [
            to_jsonable(variant) for variant in selected_variants
        ],
        "script_sha256": sha256_file(Path(__file__)),
        "safety": {
            "scenario_count": 1,
            "semantic_context_builder": False,
            "fixture_sandbox_only": True,
            "model_selects_tools": True,
        },
    })

    variant_results = []
    for variant in selected_variants:
        delegate = OllamaBenchmarkProvider(OllamaConfig(
            model=model,
            base_url="http://127.0.0.1:11434",
            context_tokens=8_192,
            output_tokens=1_024,
            temperature=0.0,
            top_p=0.8,
            seed=42,
            think=False,
            stream=False,
            repetitions=REPETITIONS,
            keep_alive="15m",
            timeout_seconds=timeout_seconds,
            recycle_loaded_model_before_first_request=True,
        ))
        provider = SemanticVariantProvider(variant, delegate)
        config = BenchmarkConfig(
            mode=BenchmarkMode.STANDARD,
            model=model,
            output_dir=str(output_dir / variant.variant_id),
            repetitions=REPETITIONS,
            seed=42,
            context_tokens=8_192,
            max_steps=6,
            keep_alive="15m",
            timeout_seconds=timeout_seconds,
            fault_injection=False,
            debug_prompts=False,
            transition_policy=(
                "contract_driven"
                if variant.conditioned_schema
                else "model_selected"
            ),
        )
        runner = StatefulBenchmarkRunner(config, live_provider=provider)
        repetitions = []
        for repetition in range(1, REPETITIONS + 1):
            attempt_start = len(provider.attempts)
            result, steps = await runner._run_live_scenario(
                scenario,
                repetition,
            )
            repetitions.append(_repetition_result(
                variant,
                scenario,
                result,
                steps,
                provider.attempts[attempt_start:],
            ))
        variant_results.append(
            summarize_variant(variant, repetitions, provider)
        )

    after = integrity_snapshot()
    integrity = {
        "before": before,
        "after": after,
        "unchanged": before == after,
    }
    decision, conclusion = diagnostic_conclusion(
        variant_results,
        integrity_unchanged=integrity["unchanged"],
    )
    summary = {
        "diagnostic_version": DIAGNOSTIC_VERSION,
        "started_at": started_at,
        "completed_at": utc_now(),
        "duration_seconds": round(time.perf_counter() - started, 3),
        "scenario_id": scenario.scenario_id,
        "model": model,
        "variants": variant_results,
        "integrity_unchanged": integrity["unchanged"],
        "decision": decision,
        "conclusion": conclusion,
    }
    write_json(output_dir / "results.json", {
        "diagnostic_version": DIAGNOSTIC_VERSION,
        "variants": variant_results,
    })
    write_json(output_dir / "integrity.json", integrity)
    write_json(output_dir / "summary.json", summary)
    (output_dir / "REPORT.md").write_text(
        render_report(summary),
        encoding="utf-8",
        newline="\n",
    )
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the isolated A01 semantic sequence matrix."
    )
    parser.add_argument("--model", default="qwen3.5:9b")
    parser.add_argument("--timeout", type=float, default=300.0)
    parser.add_argument("--output")
    parser.add_argument(
        "--only",
        action="append",
        choices=[variant.variant_id for variant in VARIANTS],
        help="Run only the selected variant; repeat to select more than one.",
    )
    return parser


async def async_main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    output = Path(args.output) if args.output else Path(
        "diagnostics",
        "model_harness_benchmark",
        (
            datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
            + "-stateful-sequence-semantic"
        ),
    )
    summary = await run_diagnostic(
        model=args.model,
        output_dir=output,
        timeout_seconds=args.timeout,
        variant_ids=tuple(args.only or ()),
    )
    print(json.dumps({
        "output": str(output.resolve()),
        "decision": summary["decision"],
        "integrity_unchanged": summary["integrity_unchanged"],
        "variants": [{
            "variant_id": item["variant"]["variant_id"],
            "strict_consecutive_success": (
                item["strict_consecutive_success"]
            ),
            "timeouts": item["total_timeouts"],
        } for item in summary["variants"]],
    }, ensure_ascii=False, indent=2))
    return 0 if summary["integrity_unchanged"] else 1


def main() -> int:
    return asyncio.run(async_main())


if __name__ == "__main__":
    raise SystemExit(main())
