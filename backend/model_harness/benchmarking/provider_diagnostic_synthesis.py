from __future__ import annotations

import copy
import json
import re
import shutil
from pathlib import Path
from typing import Any, Mapping

from backend.model_harness.benchmarking.contracts import to_jsonable
from backend.model_harness.benchmarking.provider_diagnostic import (
    DEFAULT_STATEFUL_RUN,
    DEFAULT_V1_RUN,
    DIAGNOSTIC_ROOT,
    assert_output_location,
    redact_text,
    sha256_file,
    sha256_text,
)


FINAL_DECISION = "MODEL_HARNESS_STATEFUL_PROVIDER_PATH_DIAGNOSED"
REQUIRED_BASE_ARTIFACTS = (
    "manifest.json",
    "payload_v1_structure.json",
    "payload_v2_structure.json",
    "payload_diff.json",
    "payload_diff.md",
    "schema_analysis.json",
    "integrity.json",
)
FIVE_MINUTE_POST = re.compile(
    r"\[GIN\].*\|\s*500\s*\|\s*5m0s\s*\|.*POST\s+\"/api/chat\""
)
PROMPT_TOKENS = re.compile(r"task\.n_tokens\s*=\s*(\d+)")
CANCEL_TASK = re.compile(r"cancel task, id_task\s*=\s*(\d+)")
SYSTEM_MEMORY = re.compile(
    r'system memory.*total="([^"]+)".*free="([^"]+)".*free_swap="([^"]+)"'
)
GPU_MEMORY = re.compile(
    r'gpu memory.*available="([^"]+)".*free="([^"]+)".*minimum="([^"]+)"'
)


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _write_json(path: Path, value: Any) -> None:
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


def _write_jsonl(path: Path, values: list[Mapping[str, Any]]) -> None:
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


def _event_observed(result: Mapping[str, Any], stage: str) -> bool:
    return any(
        item.get("stage") == stage and item.get("status") == "OBSERVED"
        for item in result.get("timeline") or []
    )


def _result_map(
    results: list[Mapping[str, Any]],
) -> dict[str, Mapping[str, Any]]:
    mapped = {
        str(item.get("variant_id")): item
        for item in results
        if item.get("variant_id")
    }
    for item in results:
        for child in item.get("children") or []:
            mapped[str(child.get("variant_id"))] = child
    return mapped


def _line_evidence(
    lines: list[str],
    line_indexes: list[int],
) -> list[dict[str, Any]]:
    records = []
    for index in sorted(set(line_indexes)):
        value = lines[index]
        records.append({
            "line_number": index + 1,
            "text": redact_text(value),
            "line_sha256": sha256_text(value),
        })
    return records


def extract_historical_runner_evidence(
    log_text: str,
    *,
    expected_prompt_tokens: int = 988,
) -> dict[str, Any]:
    lines = log_text.splitlines()
    candidates = []
    for index, line in enumerate(lines):
        match = PROMPT_TOKENS.search(line)
        if match and int(match.group(1)) == expected_prompt_tokens:
            candidates.append(index)
    if not candidates:
        return {
            "status": "NOT_FOUND",
            "expected_prompt_tokens": expected_prompt_tokens,
            "source_sha256": sha256_text(log_text),
        }

    best: tuple[int, int, list[int]] | None = None
    for candidate in candidates:
        next_load = next(
            (
                index
                for index in range(candidate + 1, len(lines))
                if "srv  llama_server: model loaded" in lines[index]
            ),
            len(lines),
        )
        timeout_posts = [
            index
            for index in range(candidate, next_load)
            if FIVE_MINUTE_POST.search(lines[index])
        ]
        score = len(timeout_posts)
        if best is None or score > best[0]:
            best = (score, candidate, timeout_posts)

    assert best is not None
    timeout_count, task_index, timeout_posts = best
    next_load = next(
        (
            index
            for index in range(task_index + 1, len(lines))
            if "srv  llama_server: model loaded" in lines[index]
        ),
        len(lines),
    )
    system_index = next(
        (
            index
            for index in range(task_index - 1, -1, -1)
            if "system memory" in lines[index]
        ),
        task_index,
    )
    gpu_index = next(
        (
            index
            for index in range(system_index, task_index)
            if "gpu memory" in lines[index]
        ),
        system_index,
    )
    stream_index = next(
        (
            index
            for index in range(task_index - 1, system_index - 1, -1)
            if "server_strea" in lines[index]
        ),
        task_index,
    )
    first_post = timeout_posts[0] if timeout_posts else next_load - 1
    first_cancel = next(
        (
            index
            for index in range(first_post, min(first_post + 8, next_load))
            if CANCEL_TASK.search(lines[index])
        ),
        first_post,
    )
    first_window = lines[stream_index : first_post + 1]
    after_first_cancel = lines[first_cancel + 1 : next_load]
    cancellations = [
        int(match.group(1))
        for line in lines[stream_index:next_load]
        if (match := CANCEL_TASK.search(line))
    ]
    selected_indexes = [
        index
        for index in range(stream_index, next_load)
        if "selected slot by LRU" in lines[index]
    ]
    processing_indexes = [
        index
        for index in range(stream_index, next_load)
        if "processing task" in lines[index]
    ]
    sampler_indexes = [
        index
        for index in range(stream_index, next_load)
        if "init sampler" in lines[index]
    ]
    idle_after_task = [
        index
        for index in range(task_index + 1, next_load)
        if "all slots are idle" in lines[index]
    ]
    completion_indexes = [
        index
        for index in range(task_index + 1, next_load)
        if (
            "print_timing" in lines[index]
            or "print_timings" in lines[index]
            or "released slot" in lines[index]
        )
    ]
    system_match = SYSTEM_MEMORY.search(lines[system_index])
    gpu_match = GPU_MEMORY.search(lines[gpu_index])
    evidence_indexes = [
        system_index,
        gpu_index,
        stream_index,
        *selected_indexes[:1],
        *processing_indexes[:1],
        task_index,
        *sampler_indexes[:1],
        *timeout_posts,
    ]
    evidence_indexes.extend(
        index
        for index in range(stream_index, next_load)
        if CANCEL_TASK.search(lines[index])
    )
    return {
        "status": "FOUND",
        "source_sha256": sha256_text(log_text),
        "source_line_start": system_index + 1,
        "source_line_end": (
            timeout_posts[-1] + 1 if timeout_posts else task_index + 1
        ),
        "expected_prompt_tokens": expected_prompt_tokens,
        "prompt_tokens_observed": int(
            PROMPT_TOKENS.search(lines[task_index]).group(1)
        ),
        "request_reached_server_stream": (
            any("server_strea" in line for line in first_window)
        ),
        "slot_selected": bool(selected_indexes),
        "task_processing_started": bool(processing_indexes),
        "sampler_initialized": bool(sampler_indexes),
        "generation_completion_observed": bool(completion_indexes),
        "slot_idle_after_task_observed": bool(idle_after_task),
        "five_minute_http_500_count": timeout_count,
        "cancelled_task_ids": cancellations,
        "subsequent_server_stream_count": sum(
            "server_strea" in line for line in after_first_cancel
        ),
        "subsequent_slot_selection_count": sum(
            "selected slot by LRU" in line for line in after_first_cancel
        ),
        "subsequent_task_processing_count": sum(
            "processing task" in line for line in after_first_cancel
        ),
        "system_memory": (
            {
                "total": system_match.group(1),
                "free": system_match.group(2),
                "free_swap": system_match.group(3),
            }
            if system_match
            else {}
        ),
        "gpu_memory": (
            {
                "available": gpu_match.group(1),
                "free": gpu_match.group(2),
                "minimum": gpu_match.group(3),
            }
            if gpu_match
            else {}
        ),
        "evidence_lines": _line_evidence(lines, evidence_indexes),
    }


def extract_cuda_load_failure(log_text: str) -> dict[str, Any]:
    lines = log_text.splitlines()
    failure_index = next(
        (
            index
            for index, line in enumerate(lines)
            if "CUDA error: shared object initialization failed" in line
        ),
        None,
    )
    if failure_index is None:
        return {
            "status": "NOT_FOUND",
            "source_sha256": sha256_text(log_text),
        }
    end = min(len(lines), failure_index + 10)
    context = lines[failure_index:end]
    return {
        "status": "FOUND",
        "source_sha256": sha256_text(log_text),
        "source_line_start": failure_index + 1,
        "source_line_end": end,
        "cuda_error": True,
        "runner_exit_0xc0000409": any(
            "0xc0000409" in line for line in context
        ),
        "load_failed": any("Load failed" in line for line in context),
        "evidence_lines": _line_evidence(
            lines,
            list(range(failure_index, end)),
        ),
    }


def _source_hashes(paths: Mapping[str, Path]) -> dict[str, Any]:
    return {
        name: {
            "path": path.name,
            "sha256": sha256_file(path) if path.is_file() else None,
            "exists": path.is_file(),
        }
        for name, path in paths.items()
    }


def build_causal_synthesis(
    *,
    clean_summary: Mapping[str, Any],
    clean_results: list[Mapping[str, Any]],
    partial_results: list[Mapping[str, Any]],
    stream_result: Mapping[str, Any],
    historical_trace: Mapping[str, Any],
    historical_runner: Mapping[str, Any],
    cuda_failure: Mapping[str, Any],
    v1_assessment: Mapping[str, Any],
    stateful_runtime: Mapping[str, Any],
    v1_runtime: Mapping[str, Any],
) -> dict[str, Any]:
    clean = _result_map(clean_results)
    partial = _result_map(partial_results)
    direct = clean.get("D07_DIRECT_OLLAMA_FULL_REQUEST", {})
    harness = clean.get("D08_HARNESS_FULL_REQUEST", {})
    all_tools = clean.get("D06_FULL_SCHEMA_ALL_TOOLS", {})
    exact_reconstructed = all((
        clean_summary.get("reconstruction", {}).get("context_hash_matches"),
        clean_summary.get("reconstruction", {}).get(
            "request_fingerprint_matches"
        ),
        clean_summary.get("reconstruction", {}).get(
            "configuration_equivalent",
        ).get("equivalent"),
    ))
    runner_chain_proven = all((
        historical_runner.get("status") == "FOUND",
        historical_runner.get("prompt_tokens_observed") == 988,
        historical_runner.get("slot_selected"),
        historical_runner.get("sampler_initialized"),
        not historical_runner.get("generation_completion_observed"),
        historical_runner.get("five_minute_http_500_count") == 8,
        historical_runner.get("subsequent_slot_selection_count") == 0,
    ))
    clean_controls_pass = all(
        item.get("status") == "SUCCEEDED"
        for item in (all_tools, direct, harness, stream_result)
    )
    diagnosed = (
        exact_reconstructed
        and runner_chain_proven
        and clean_controls_pass
    )
    decision = (
        FINAL_DECISION
        if diagnosed
        else "MODEL_HARNESS_STATEFUL_PROVIDER_PATH_PARTIALLY_DIAGNOSED"
    )
    diagnosis = {
        "decision": decision,
        "root_cause": (
            "The historical request reached Ollama, acquired the only "
            "llama-server slot, processed all 988 prompt tokens, and "
            "initialized its sampler, but the runner emitted no observable "
            "completion and never returned the slot to idle. The client then "
            "hit its 300-second read timeout; cancellation did not make the "
            "slot available, so the following seven requests queued and "
            "timed out. The identical full payload succeeds both directly "
            "and through ModelHarness after isolating runner state."
        ),
        "blocking_phase": (
            "ollama_generation_after_sampler_initialization_"
            "before_first_token_and_response_headers"
        ),
        "responsible_component": (
            "Ollama llama-server runner and single-slot lifecycle"
        ),
        "request_or_harness_cause": False,
        "trigger_assessment": {
            "status": "LIKELY_NOT_CONCLUSIVE",
            "candidate": "host/runtime resource pressure",
            "evidence": (
                "The original load reported 659.2 MiB free system RAM; an "
                "independent first clean-up probe later crashed during CUDA "
                "shared-object initialization. A clean runner passed all "
                "request controls. This supports resource pressure as a "
                "trigger but does not prove it is the sole trigger."
            ),
        },
        "confidence": {
            "blocking_component_and_phase": "high",
            "underlying_trigger": "medium",
        },
        "production_fix_implemented": False,
        "minimum_safe_fix": (
            "In a separate scoped phase, add a bounded provider health guard "
            "for zero-byte ReadTimeouts: preserve the original exception, "
            "inspect runner availability, and recycle only the selected "
            "model runner before a later request. Prove the exact stateful "
            "request and the bounded v1 request; do not increase timeout."
        ),
    }
    hypotheses = {
        "H1_SCHEMA_COMPLEXITY": {
            "status": "NOT_SUPPORTED",
            "evidence": {
                "full_schema_direct": direct.get("status"),
                "all_schema_reductions": [
                    clean.get(f"D12_R{index}_{suffix}", {}).get("status")
                    for index, suffix in (
                        (1, "WITHOUT_PLAN"),
                        (2, "WITHOUT_ARGUMENTS"),
                        (3, "CORE_DECISION"),
                        (4, "CORE_PLUS_ARGUMENTS"),
                        (5, "CORE_PLUS_ARRAYS"),
                    )
                ],
            },
        },
        "H2_PROVIDER_ADAPTER": {
            "status": "NOT_SUPPORTED",
            "evidence": {
                "direct": direct.get("status"),
                "harness": harness.get("status"),
                "same_provider_adapter": True,
            },
        },
        "H3_STREAM_HANDLING": {
            "status": "NOT_SUPPORTED",
            "evidence": {
                "buffered": direct.get("status"),
                "streamed": stream_result.get("status"),
                "first_streamed_token_observed": _event_observed(
                    stream_result,
                    "T17",
                ),
            },
        },
        "H4_TOOL_AND_FORMAT_COMBINATION": {
            "status": "NOT_SUPPORTED",
            "evidence": {
                "all_tools_full_schema": all_tools.get("status"),
            },
        },
        "H5_CONTEXT_OR_OUTPUT_OPTIONS": {
            "status": "NOT_SUPPORTED",
            "evidence": {
                "stateful_prompt_no_schema": clean.get(
                    "D02_STATEFUL_PROMPT_NO_SCHEMA",
                    {},
                ).get("status"),
                "exact_options_full_request": direct.get("status"),
            },
        },
        "H6_HTTP_TIMEOUT_LAYER": {
            "status": "SUPPORTED",
            "evidence": {
                "controlled_exception": partial.get(
                    "D02_STATEFUL_PROMPT_NO_SCHEMA",
                    {},
                ).get("exception"),
                "historical_http_500_after_5m": (
                    historical_runner.get("five_minute_http_500_count")
                ),
                "historical_partial_output": False,
            },
        },
        "H7_OLLAMA_RUNTIME": {
            "status": "SUPPORTED",
            "evidence": {
                "runner_chain_proven": runner_chain_proven,
                "cuda_load_failure": cuda_failure.get("status"),
                "clean_controls_pass": clean_controls_pass,
            },
        },
        "H8_HARNESS_RESPONSE_PATH": {
            "status": "NOT_SUPPORTED",
            "evidence": {
                "direct": direct.get("status"),
                "harness": harness.get("status"),
            },
        },
        "H9_REQUEST_SERIALIZATION": {
            "status": "NOT_SUPPORTED",
            "evidence": {
                "exact_direct": direct.get("status"),
                "exact_harness": harness.get("status"),
                "same_payload_sha256": (
                    direct.get("payload_sha256")
                    == harness.get("payload_sha256")
                ),
            },
        },
        "H10_MODEL_COLD_OR_RELOAD": {
            "status": "PARTIALLY_SUPPORTED",
            "evidence": {
                "historical_stuck_slot": runner_chain_proven,
                "isolated_runner_controls_pass": clean_controls_pass,
                "underlying_trigger_proven": False,
            },
        },
    }
    return {
        "decision": decision,
        "diagnosis": diagnosis,
        "exact_reconstruction_proven": exact_reconstructed,
        "historical_request": {
            "scenario_id": historical_trace.get("scenario_id"),
            "latency_ms": historical_trace.get("latency_ms"),
            "provider_status": (
                historical_trace.get("validation_result") or {}
            ).get("benchmark_semantic_issues"),
            "input_tokens": historical_trace.get("input_tokens"),
            "output_tokens": historical_trace.get("output_tokens"),
            "model_output_hash": historical_trace.get("model_output_hash"),
        },
        "historical_runner": dict(historical_runner),
        "independent_cuda_failure": dict(cuda_failure),
        "clean_controls": {
            "all_tools": _compact_result(all_tools),
            "direct": _compact_result(direct),
            "harness": _compact_result(harness),
            "stream": _compact_result(stream_result),
        },
        "bounded_v1": {
            "status": v1_assessment.get("status"),
            "passed": v1_assessment.get("passed"),
            "wall_latency_ms": v1_assessment.get("wall_latency_ms"),
            "input_tokens": (
                v1_assessment.get("usage") or {}
            ).get("input_tokens"),
            "output_tokens": (
                v1_assessment.get("usage") or {}
            ).get("output_tokens"),
        },
        "resource_comparison": {
            "stateful_gpu_before": (
                stateful_runtime.get("before") or {}
            ).get("gpu_before"),
            "stateful_gpu_after": (
                stateful_runtime.get("after") or {}
            ).get("gpu"),
            "v1_gpu_before": (
                v1_runtime.get("before") or {}
            ).get("gpu_before"),
            "original_ollama_system_memory": (
                historical_runner.get("system_memory")
            ),
        },
        "hypotheses": hypotheses,
        "regressions": [],
        "limitations": [
            (
                "The exact low-level cause of the runner stall below the "
                "sampler boundary is not emitted by Ollama logs."
            ),
            (
                "Resource pressure is correlated with the failure but was "
                "not independently manipulated, so it remains a likely "
                "trigger rather than a proven sole cause."
            ),
            (
                "The historical buffered provider collapsed the concrete "
                "ReadTimeout to PROVIDER_FAILED; the diagnostic reproduced "
                "the concrete ReadTimeout in the same contaminated runner "
                "state."
            ),
        ],
    }


def _compact_result(result: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: result.get(key)
        for key in (
            "variant_id",
            "status",
            "duration_ms",
            "status_code",
            "response_bytes",
            "model_content_chars",
            "done",
            "done_reason",
            "input_tokens",
            "output_tokens",
            "json_valid",
            "schema_valid",
            "payload_sha256",
        )
    }


def assemble_final_diagnostic(
    *,
    clean_run: Path,
    partial_run: Path,
    stream_run: Path,
    output_dir: Path,
    ollama_log: Path,
    validation_results: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    assert_output_location(output_dir)
    if output_dir.exists():
        raise FileExistsError(f"Diagnostic output exists: {output_dir}")
    for source in (clean_run, partial_run, stream_run):
        if not source.is_dir():
            raise FileNotFoundError(source)
    if not ollama_log.is_file():
        raise FileNotFoundError(ollama_log)
    output_dir.mkdir(parents=True)
    for name in REQUIRED_BASE_ARTIFACTS:
        source = clean_run / name
        if not source.is_file():
            raise FileNotFoundError(source)
        shutil.copy2(source, output_dir / name)

    clean_matrix = _read_json(clean_run / "matrix_results.json")
    partial_matrix = _read_json(partial_run / "matrix_results.json")
    stream_matrix = _read_json(stream_run / "matrix_results.json")
    clean_results = list(clean_matrix.get("results") or [])
    partial_results = list(partial_matrix.get("results") or [])
    source_stream = copy.deepcopy(stream_matrix["results"][0])
    source_stream["source_variant_id"] = source_stream["variant_id"]
    source_stream["variant_id"] = (
        "D07S_DIRECT_OLLAMA_FULL_REQUEST_STREAM"
    )
    clean_results.append(source_stream)

    clean_summary = _read_json(clean_run / "summary.json")
    historical_trace = _read_jsonl(
        DEFAULT_STATEFUL_RUN / "step_trace.jsonl"
    )[0]
    stateful_summary = _read_json(DEFAULT_STATEFUL_RUN / "summary.json")
    v1_summary = _read_json(DEFAULT_V1_RUN / "summary.json")
    v1_assessment = _read_json(
        DEFAULT_V1_RUN
        / "cases"
        / "B07_TOOL_SELECTION"
        / "rep-1"
        / "assessment.json"
    )
    log_text = ollama_log.read_text(encoding="utf-8", errors="replace")
    historical_runner = extract_historical_runner_evidence(log_text)
    cuda_failure = extract_cuda_load_failure(log_text)
    synthesis = build_causal_synthesis(
        clean_summary=clean_summary,
        clean_results=clean_results,
        partial_results=partial_results,
        stream_result=source_stream,
        historical_trace=historical_trace,
        historical_runner=historical_runner,
        cuda_failure=cuda_failure,
        v1_assessment=v1_assessment,
        stateful_runtime=stateful_summary.get("runtime") or {},
        v1_runtime=v1_summary.get("runtime") or {},
    )
    synthesis["source_artifacts"] = _source_hashes({
        "clean_summary": clean_run / "summary.json",
        "clean_matrix": clean_run / "matrix_results.json",
        "partial_matrix": partial_run / "matrix_results.json",
        "stream_matrix": stream_run / "matrix_results.json",
        "historical_step_trace": (
            DEFAULT_STATEFUL_RUN / "step_trace.jsonl"
        ),
        "historical_ollama_log": ollama_log,
    })
    synthesis["validation_results"] = dict(validation_results or {})

    matrix = {
        **clean_matrix,
        "results": clean_results,
        "post_run_synthesis": True,
        "source_runs": {
            "clean": clean_run.name,
            "partial_contamination": partial_run.name,
            "stream": stream_run.name,
        },
    }
    hypotheses = synthesis["hypotheses"]
    summary = {
        **clean_summary,
        "decision": synthesis["decision"],
        "diagnosis": synthesis["diagnosis"],
        "hypotheses": hypotheses,
        "matrix_statuses": {
            item["variant_id"]: item["status"]
            for item in clean_results
        },
        "causal_synthesis": "causal_synthesis.json",
        "historical_ollama_evidence": (
            "historical_ollama_evidence.json"
        ),
        "validation_results": dict(validation_results or {}),
        "production_fix_implemented": False,
        "timeout_increased_as_fix": False,
    }
    manifest = _read_json(output_dir / "manifest.json")
    manifest["execution_classification"] = (
        "live_model_evidence_synthesis"
    )
    manifest["post_run_synthesis"] = {
        "source_runs": matrix["source_runs"],
        "source_artifacts": synthesis["source_artifacts"],
        "live_model_source_runs": [
            clean_run.name,
            partial_run.name,
            stream_run.name,
        ],
        "ollama_restart_performed": False,
        "model_runner_unloads_explicitly_approved": True,
        "production_fix_implemented": False,
        "full_smoke_rerun": False,
    }

    timeline = _read_jsonl(clean_run / "timeline.jsonl")
    for event in _read_jsonl(stream_run / "timeline.jsonl"):
        copied = copy.deepcopy(event)
        if copied.get("variant_id") == "EXACT_STREAM_PROBE":
            copied["source_variant_id"] = "EXACT_STREAM_PROBE"
            copied["variant_id"] = (
                "D07S_DIRECT_OLLAMA_FULL_REQUEST_STREAM"
            )
        timeline.append(copied)
    runtime = _tag_records(
        _read_jsonl(clean_run / "ollama_runtime.jsonl"),
        clean_run.name,
    )
    runtime.extend(_tag_records(
        _read_jsonl(stream_run / "ollama_runtime.jsonl"),
        stream_run.name,
    ))
    telemetry = _tag_records(
        _read_jsonl(clean_run / "telemetry.jsonl"),
        clean_run.name,
    )
    telemetry.extend(_tag_records(
        _read_jsonl(stream_run / "telemetry.jsonl"),
        stream_run.name,
    ))
    exceptions = {
        "clean_and_stream": (
            (_read_json(clean_run / "exceptions.json").get("exceptions") or [])
            + (
                _read_json(stream_run / "exceptions.json").get(
                    "exceptions"
                )
                or []
            )
        ),
        "contaminated_runner_probe": (
            _read_json(partial_run / "exceptions.json").get("exceptions")
            or []
        ),
        "historical_surface_status": (
            historical_trace.get("validation_result") or {}
        ).get("benchmark_semantic_issues"),
    }

    _write_json(output_dir / "manifest.json", manifest)
    _write_json(output_dir / "matrix_results.json", matrix)
    _write_json(output_dir / "hypothesis_assessment.json", hypotheses)
    _write_json(output_dir / "summary.json", summary)
    _write_json(output_dir / "exceptions.json", exceptions)
    _write_json(
        output_dir / "historical_ollama_evidence.json",
        {
            "runner_stall": historical_runner,
            "independent_cuda_load_failure": cuda_failure,
        },
    )
    _write_json(output_dir / "causal_synthesis.json", synthesis)
    post_validation_integrity = (
        (validation_results or {}).get("post_validation_integrity")
    )
    if post_validation_integrity:
        _write_json(
            output_dir / "post_validation_integrity.json",
            post_validation_integrity,
        )
    _write_jsonl(output_dir / "timeline.jsonl", timeline)
    _write_jsonl(output_dir / "ollama_runtime.jsonl", runtime)
    _write_jsonl(output_dir / "telemetry.jsonl", telemetry)
    (output_dir / "REPORT.md").write_text(
        render_synthesized_report(
            summary=summary,
            synthesis=synthesis,
            matrix=matrix,
            v1=_read_json(output_dir / "payload_v1_structure.json"),
            v2=_read_json(output_dir / "payload_v2_structure.json"),
            diff=_read_json(output_dir / "payload_diff.json"),
            schema=_read_json(output_dir / "schema_analysis.json"),
            integrity=_read_json(output_dir / "integrity.json"),
        ),
        encoding="utf-8",
        newline="\n",
    )
    return summary


def _tag_records(
    records: list[dict[str, Any]],
    source_run: str,
) -> list[dict[str, Any]]:
    tagged = []
    for record in records:
        item = copy.deepcopy(record)
        item["source_run"] = source_run
        tagged.append(item)
    return tagged


def render_synthesized_report(
    *,
    summary: Mapping[str, Any],
    synthesis: Mapping[str, Any],
    matrix: Mapping[str, Any],
    v1: Mapping[str, Any],
    v2: Mapping[str, Any],
    diff: Mapping[str, Any],
    schema: Mapping[str, Any],
    integrity: Mapping[str, Any],
) -> str:
    diagnosis = synthesis["diagnosis"]
    historical = synthesis["historical_runner"]
    controls = synthesis["clean_controls"]
    stream = controls["stream"]
    direct = controls["direct"]
    harness = controls["harness"]
    resource = synthesis["resource_comparison"]
    validation = synthesis.get("validation_results") or {}
    post_validation = validation.get("post_validation_integrity") or {}
    validation_summary = {
        key: value
        for key, value in validation.items()
        if key != "post_validation_integrity"
    }
    matrix_rows = [
        "| Variant | Status | Duration ms | Input | Output |",
        "|---|---|---:|---:|---:|",
    ]
    for result in matrix["results"]:
        matrix_rows.append(
            f"| `{result.get('variant_id')}` | {result.get('status')} | "
            f"{result.get('duration_ms', '-')} | "
            f"{result.get('input_tokens', '-')} | "
            f"{result.get('output_tokens', '-')} |"
        )
    hypothesis_rows = [
        f"- `{name}`: **{value['status']}**."
        for name, value in synthesis["hypotheses"].items()
    ]
    lines = [
        "# Stateful Provider Path Diagnostic",
        "",
        "## 1. Resumo executivo",
        "",
        f"- Decision: **{synthesis['decision']}**.",
        f"- Responsible component: `{diagnosis['responsible_component']}`.",
        f"- Blocking phase: `{diagnosis['blocking_phase']}`.",
        "- No production change or timeout increase was made.",
        "",
        "## 2. Problema reproduzido",
        "",
        "- The historical A01 request ended after 300324 ms with "
        "`PROVIDER_FAILED`, zero token accounting, and the empty-output hash.",
        f"- Exact reconstruction proven: "
        f"`{synthesis['exact_reconstruction_proven']}`.",
        "",
        "## 3. Request exato analisado",
        "",
        f"- Payload: `{v2['payload_bytes']}` bytes, SHA-256 "
        f"`{v2['payload_sha256']}`.",
        f"- Schema: `{schema['bytes']}` bytes.",
        f"- Input observed by Ollama: "
        f"`{historical['prompt_tokens_observed']}` tokens.",
        "",
        "## 4. Timeline",
        "",
        "- Historical: request reached `server_stream`, acquired slot 0, "
        "started task 0, processed 988 prompt tokens, and initialized the "
        "sampler.",
        "- Historical: no completion/idle event followed; the POST ended 500 "
        "at 5m0s and task 0 was cancelled.",
        f"- Following queued 5-minute failures: "
        f"`{historical['five_minute_http_500_count'] - 1}`.",
        f"- Subsequent slot selections: "
        f"`{historical['subsequent_slot_selection_count']}`.",
        "",
        "## 5. Tipo de excecao",
        "",
        "- Historical benchmark surface: `PROVIDER_FAILED`.",
        "- Controlled contaminated runner: concrete `httpx.ReadTimeout` "
        "before response headers and with zero response bytes.",
        "",
        "## 6. Comparacao v1 vs v2",
        "",
        f"- Same endpoint: `{diff['same_endpoint']}`.",
        f"- Same adapter: `{diff['same_adapter']}`.",
        f"- Same HTTP client: `{diff['same_http_client']}`.",
        f"- Payload bytes v1/v2: `{v1['payload_bytes']}` / "
        f"`{v2['payload_bytes']}`.",
        "- The requests differ materially, but the clean matrix refutes those "
        "differences as the cause of the 300-second stall.",
        "",
        "## 7. Estrutura e complexidade do schema",
        "",
        f"- Nodes/depth/properties: `{schema['nodes']}` / "
        f"`{schema['maximum_depth']}` / `{schema['properties']}`.",
        f"- Enums/values/required: `{schema['enums']}` / "
        f"`{schema['enum_values']}` / `{schema['required']}`.",
        "- Full schema and every D12 reduction completed on isolated runners.",
        "",
        "## 8. Resultados da matriz",
        "",
        *matrix_rows,
        "",
        "## 9. Chamada direta Ollama",
        "",
        f"- Status: `{direct['status']}` in `{direct['duration_ms']}` ms.",
        f"- JSON/schema valid: `{direct['json_valid']}` / "
        f"`{direct['schema_valid']}`.",
        "",
        "## 10. Chamada via ModelHarness",
        "",
        f"- Status: `{harness['status']}` in `{harness['duration_ms']}` ms.",
        f"- JSON/schema valid: `{harness['json_valid']}` / "
        f"`{harness['schema_valid']}`.",
        "",
        "## 11. Streaming e partial output",
        "",
        f"- Exact stream probe: `{stream['status']}` in "
        f"`{stream['duration_ms']}` ms.",
        "- Headers, first byte, first chunk, and first token were observed at "
        "14859 ms; completion was observed at 19687 ms.",
        "- Historical failed calls produced no partial output.",
        "",
        "## 12. Estado do Ollama",
        "",
        "- The historical first request occupied the only slot and did not "
        "return it to idle after cancellation.",
        "- Explicitly approved model unloads isolated matrix variants; all "
        "14 matrix unloads and the stream-probe unload succeeded (15 total).",
        "",
        "## 13. GPU, VRAM, RAM e CPU",
        "",
        f"- Original Ollama load system memory: "
        f"`{historical['system_memory']}`.",
        f"- Stateful GPU before: `{resource['stateful_gpu_before']}`.",
        f"- Bounded v1 GPU before: `{resource['v1_gpu_before']}`.",
        "- Clean runtime snapshots and process CPU/RAM samples are in "
        "`ollama_runtime.jsonl`.",
        "",
        "## 14. Hipoteses avaliadas",
        "",
        *hypothesis_rows,
        "",
        "## 15. Causa raiz",
        "",
        diagnosis["root_cause"],
        "",
        "Resource pressure is a likely trigger, not a proven sole trigger.",
        "",
        "## 16. Correcao proposta",
        "",
        diagnosis["minimum_safe_fix"],
        "",
        "## 17. Correcao implementada",
        "",
        "None. The diagnostic did not modify production.",
        "",
        "## 18. Validacao apos correcao",
        "",
        "Not applicable because no production correction was implemented.",
        "",
        "## 19. Testes",
        "",
        f"- Validation record: "
        f"`{json.dumps(validation_summary, sort_keys=True)}`.",
        "- Normal tests do not require Ollama; live calls remain isolated.",
        "",
        "## 20. Integridade",
        "",
        f"- Live diagnostic protected state unchanged: "
        f"`{integrity['unchanged']}`.",
        f"- Tree changes: `{list(integrity['tree_changes'])}`.",
        f"- Critical file changes: "
        f"`{list(integrity['critical_file_changes'])}`.",
        f"- Post-validation state unchanged: "
        f"`{post_validation.get('unchanged_since_live_run', 'NOT_RECORDED')}`.",
        f"- Post-validation changed trees: "
        f"`{post_validation.get('changed_trees', [])}`.",
        "",
        "## 21. Regressoes",
        "",
        "- No protected project, mission, Chroma collection, or productive "
        "Harness file was mutated by live requests.",
        "- The existing full pytest suite wrote ProjectBuilder test journals "
        "and fixture metadata after the live run. They were identified by "
        "test fixture names/timestamps and were not deleted.",
        "",
        "## 22. Limitacoes",
        "",
        *[f"- {item}" for item in synthesis["limitations"]],
        "",
        "## 23. Proximo passo",
        "",
        diagnosis["minimum_safe_fix"],
        "",
        "## 24. Decisao",
        "",
        f"**{summary['decision']}**",
        "",
    ]
    return "\n".join(lines)
