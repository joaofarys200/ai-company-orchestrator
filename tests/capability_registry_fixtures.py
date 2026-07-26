from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from backend.capability_registry.contracts import sha256_json


MODEL_NAME = "qwen3.5:9b"
BOUNDED_VERSION = "model_harness_qwen35_capabilities_v1"
STATEFUL_VERSION = "model_harness_qwen35_stateful_v2"
DIAGNOSTIC_VERSION = "stateful_provider_path_diagnostic_v1"


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def create_bounded_run(
    root: Path,
    *,
    run_name: str = "bounded-run",
    completed_at: str = "2026-01-01T10:00:00+00:00",
    code_passed: bool = True,
    declared_artifact_hash: bool = False,
) -> Path:
    run_dir = root / "model_harness_benchmark" / run_name
    config = {
        "model": MODEL_NAME,
        "base_url": "http://127.0.0.1:11434",
        "context_tokens": 8192,
        "output_tokens": 768,
        "temperature": 0.0,
        "top_p": 0.8,
        "seed": 42,
        "think": False,
        "stream": False,
        "repetitions": 2,
        "keep_alive": "15m",
        "timeout_seconds": 300.0,
    }
    cases = [
        {
            "case_id": "B02_STRUCTURED_EXTRACTION",
            "capability": "structured_extraction",
            "passed": True,
            "passed_repetitions": 2,
            "total_repetitions": 2,
            "mean_latency_ms": 100.0,
        },
        {
            "case_id": "B05_CODE_REASONING",
            "capability": "code_reasoning",
            "passed": code_passed,
            "passed_repetitions": 2 if code_passed else 0,
            "total_repetitions": 2,
            "mean_latency_ms": 120.0,
        },
        {
            "case_id": "B07_TOOL_SELECTION",
            "capability": "tool_selection",
            "passed": True,
            "passed_repetitions": 2,
            "total_repetitions": 2,
            "mean_latency_ms": 80.0,
        },
    ]
    passed_cases = sum(1 for case in cases if case["passed"])
    summary = {
        "benchmark_version": BOUNDED_VERSION,
        "completed_at": completed_at,
        "model": MODEL_NAME,
        "config": config,
        "total_cases": len(cases),
        "passed_cases": passed_cases,
        "failed_cases": len(cases) - passed_cases,
        "total_calls": len(cases) * 2,
        "latency_ms": {"mean": 100.0, "p95": 120.0},
        "cases": cases,
        "capabilities_demonstrated": [
            case["capability"] for case in cases if case["passed"]
        ],
        "limitations_observed": [],
    }
    summary_path = run_dir / "summary.json"
    write_json(summary_path, summary)
    manifest = {
        "benchmark_version": BOUNDED_VERSION,
        "created_at": "2026-01-01T09:59:00+00:00",
        "config": config,
        "runtime": {
            "ollama_version": "ollama version is test",
            "model_list_entry": {
                "details": {
                    "family": "qwen35",
                    "parameter_size": "9.7B",
                    "quantization_level": "Q4_K_M",
                    "context_length": 262144,
                },
                "capabilities": [
                    "completion",
                    "tools",
                    "vision",
                    "thinking",
                ],
            },
            "model_info": {
                "general.architecture": "qwen35",
                "general.parameter_count": 9653104368,
                "qwen35.context_length": 262144,
            },
        },
        "cases": cases,
    }
    if declared_artifact_hash:
        manifest["artifact_hashes"] = {
            "summary.json": file_sha256(summary_path),
        }
    write_json(run_dir / "manifest.json", manifest)
    (run_dir / "REPORT.md").write_text(
        "# Bounded benchmark report\n",
        encoding="utf-8",
        newline="\n",
    )
    return run_dir


def create_stateful_run(
    root: Path,
    *,
    run_name: str = "stateful-run",
    completed_at: str = "2026-01-02T10:00:00+00:00",
) -> Path:
    run_dir = root / "model_harness_benchmark" / run_name
    config = {
        "mode": "smoke",
        "model": MODEL_NAME,
        "output_dir": str(run_dir),
        "repetitions": 1,
        "seed": 42,
        "context_tokens": 8192,
        "max_steps": 6,
        "keep_alive": "15m",
        "timeout_seconds": 300.0,
        "temperature": 0.0,
        "top_p": 0.8,
        "think": False,
        "stream": False,
        "max_output_tokens": 1024,
        "base_url": "http://127.0.0.1:11434",
        "fault_injection": True,
        "debug_prompts": False,
    }
    hash_payload = dict(config)
    hash_payload.pop("output_dir")
    hash_payload.pop("debug_prompts")
    configuration_hash = sha256_json(hash_payload)
    scenarios = [
        {
            "scenario_id": "A01_FIND_RELEVANT_FILE",
            "capability": "stateful_tool_use",
        },
        {
            "scenario_id": "E02_TRUNCATED_JSON",
            "capability": "recovery_after_failure",
        },
    ]
    manifest = {
        "benchmark_version": STATEFUL_VERSION,
        "created_at": "2026-01-02T09:00:00+00:00",
        "configuration": config,
        "configuration_hash": configuration_hash,
        "scenarios": scenarios,
        "runtime_before": {
            "ollama_version": "ollama version is test",
            "model_list_entry": {
                "details": {
                    "family": "qwen35",
                    "quantization_level": "Q4_K_M",
                    "context_length": 262144,
                },
                "capabilities": ["completion", "vision", "thinking"],
            },
            "model_info": {
                "general.architecture": "qwen35",
                "general.parameter_count": 9653104368,
                "qwen35.context_length": 262144,
            },
        },
    }
    summary = {
        "benchmark_version": STATEFUL_VERSION,
        "completed_at": completed_at,
        "mode": "smoke",
        "model": MODEL_NAME,
        "configuration": config,
        "configuration_hash": configuration_hash,
        "scenario_repetitions": 2,
        "passed_repetitions": 1,
        "failed_repetitions": 1,
        "model_calls": 1,
        "performance": {
            "latency_ms": {"mean": 300.0, "p95": 400.0},
        },
        "decision": "MODEL_HARNESS_STATEFUL_BENCHMARK_IMPLEMENTED_NOT_VALIDATED",
        "limitations": [
            "Read-only tool execution does not demonstrate productive tools.",
        ],
    }
    profile = {
        "benchmark_version": STATEFUL_VERSION,
        "configuration_hash": configuration_hash,
        "capabilities": [
            {
                "capability": "stateful_tool_use",
                "status": "FAILED",
                "confidence": 0.0,
                "passed_cases": 0,
                "failed_cases": 1,
                "total_cases": 1,
                "total_calls": 1,
                "repetitions": 1,
                "mean_latency_ms": 300.0,
                "p95_latency_ms": 300.0,
                "context_range": [1000, 1000],
                "limitations": ["One stateful scenario failed."],
            },
            {
                "capability": "recovery_after_failure",
                "status": "DEMONSTRATED_PRELIMINARY",
                "confidence": 0.333,
                "passed_cases": 1,
                "failed_cases": 0,
                "total_cases": 1,
                "total_calls": 0,
                "repetitions": 1,
                "mean_latency_ms": 2.0,
                "p95_latency_ms": 2.0,
                "context_range": [0, 0],
                "limitations": ["One deterministic fault case passed."],
            },
        ],
    }
    write_json(run_dir / "manifest.json", manifest)
    write_json(run_dir / "summary.json", summary)
    write_json(run_dir / "capability_profile.json", profile)
    (run_dir / "REPORT.md").write_text(
        "# Stateful benchmark report\n",
        encoding="utf-8",
        newline="\n",
    )
    return run_dir


def create_provider_diagnostic(
    root: Path,
    *,
    run_name: str = "provider-run",
) -> Path:
    run_dir = root / "model_harness_provider_diagnostic" / run_name
    config = {
        "model": MODEL_NAME,
        "context_tokens": 8192,
        "max_output_tokens": 1024,
        "temperature": 0.0,
        "top_p": 0.8,
        "think": False,
        "stream": False,
        "timeout_seconds": 300.0,
    }
    manifest = {
        "diagnostic_version": DIAGNOSTIC_VERSION,
        "started_at": "2026-01-03T09:00:00+00:00",
        "configuration": config,
    }
    summary = {
        "diagnostic_version": DIAGNOSTIC_VERSION,
        "completed_at": "2026-01-03T10:00:00+00:00",
        "model": MODEL_NAME,
        "matrix_statuses": {
            "D01_BASELINE_SIMPLE": "SUCCEEDED",
            "D08_HARNESS_FULL_REQUEST": "SUCCEEDED",
        },
        "decision": "MODEL_HARNESS_STATEFUL_PROVIDER_PATH_DIAGNOSED",
    }
    write_json(run_dir / "manifest.json", manifest)
    write_json(run_dir / "summary.json", summary)
    (run_dir / "REPORT.md").write_text(
        "# Provider diagnostic report\n",
        encoding="utf-8",
        newline="\n",
    )
    return run_dir
