import pytest

from backend.model_harness.benchmarking import provider_diagnostic as diagnostic
from backend.model_harness.benchmarking.provider_diagnostic_synthesis import (
    FINAL_DECISION,
    build_causal_synthesis,
    extract_cuda_load_failure,
    extract_historical_runner_evidence,
    render_synthesized_report,
)


pytestmark = pytest.mark.unit


def _historical_log() -> str:
    lines = [
        (
            'time=x level=INFO msg="system memory" total="15.7 GiB" '
            'free="659.2 MiB" free_swap="5.7 GiB"'
        ),
        (
            'time=x level=INFO msg="gpu memory" available="6.3 GiB" '
            'free="6.8 GiB" minimum="457.0 MiB"'
        ),
        "srv  llama_server: model loaded",
        "srv  update_slots: all slots are idle",
        "srv  server_strea: conv_id=",
        "slot get_availabl: selected slot by LRU",
        "slot launch_slot_: processing task",
        "slot operator(): task.n_tokens = 988",
        "slot init_sampler: init sampler",
        (
            '[GIN] 2026/07/25 - 21:53:01 | 500 | 5m0s | '
            '127.0.0.1 | POST "/api/chat"'
        ),
        "srv stop: cancel task, id_task = 0",
    ]
    for task in (16, 18, 20, 22, 24, 26, 28):
        lines.extend([
            "srv  server_strea: conv_id=",
            (
                f'[GIN] 2026/07/25 - 22:00:{task:02d} | 500 | '
                '5m0s | 127.0.0.1 | POST "/api/chat"'
            ),
            f"srv stop: cancel task, id_task = {task}",
        ])
    lines.append("srv  llama_server: model loaded")
    return "\n".join(lines)


def _result(variant_id, status="SUCCEEDED", **overrides):
    value = {
        "variant_id": variant_id,
        "status": status,
        "duration_ms": 100,
        "payload_sha256": "a" * 64,
        "json_valid": status == "SUCCEEDED",
        "schema_valid": status == "SUCCEEDED",
        "timeline": [],
    }
    value.update(overrides)
    return value


def _synthesis_inputs():
    clean_results = [
        _result("D02_STATEFUL_PROMPT_NO_SCHEMA"),
        _result("D06_FULL_SCHEMA_ALL_TOOLS"),
        _result("D07_DIRECT_OLLAMA_FULL_REQUEST"),
        _result("D08_HARNESS_FULL_REQUEST"),
        _result("D12_R1_WITHOUT_PLAN"),
        _result("D12_R2_WITHOUT_ARGUMENTS"),
        _result("D12_R3_CORE_DECISION"),
        _result("D12_R4_CORE_PLUS_ARGUMENTS"),
        _result("D12_R5_CORE_PLUS_ARRAYS"),
    ]
    partial_results = [
        _result(
            "D02_STATEFUL_PROMPT_NO_SCHEMA",
            "READ_TIMEOUT",
            exception={"classification": "READ_TIMEOUT"},
        ),
    ]
    stream = _result(
        "D07S_DIRECT_OLLAMA_FULL_REQUEST_STREAM",
        timeline=[{"stage": "T17", "status": "OBSERVED"}],
    )
    return {
        "clean_summary": {
            "reconstruction": {
                "context_hash_matches": True,
                "request_fingerprint_matches": True,
                "configuration_equivalent": {"equivalent": True},
            },
        },
        "clean_results": clean_results,
        "partial_results": partial_results,
        "stream_result": stream,
        "historical_trace": {
            "scenario_id": "A01_FIND_RELEVANT_FILE",
            "latency_ms": 300324,
            "input_tokens": None,
            "output_tokens": None,
            "model_output_hash": "e3b0",
            "validation_result": {
                "benchmark_semantic_issues": [
                    "model_response_status=PROVIDER_FAILED"
                ],
            },
        },
        "historical_runner": extract_historical_runner_evidence(
            _historical_log()
        ),
        "cuda_failure": {
            "status": "FOUND",
            "cuda_error": True,
        },
        "v1_assessment": {
            "status": "SUCCEEDED",
            "passed": True,
            "wall_latency_ms": 2817,
            "usage": {"input_tokens": 55, "output_tokens": 32},
        },
        "stateful_runtime": {
            "before": {"gpu_before": {"memory_free_mib": 3535}},
            "after": {"gpu": {"memory_free_mib": 166}},
        },
        "v1_runtime": {
            "before": {"gpu_before": {"memory_free_mib": 6682}},
        },
    }


def test_historical_log_isolates_stuck_single_slot_chain():
    evidence = extract_historical_runner_evidence(_historical_log())

    assert evidence["status"] == "FOUND"
    assert evidence["prompt_tokens_observed"] == 988
    assert evidence["slot_selected"] is True
    assert evidence["sampler_initialized"] is True
    assert evidence["generation_completion_observed"] is False
    assert evidence["slot_idle_after_task_observed"] is False
    assert evidence["five_minute_http_500_count"] == 8
    assert evidence["cancelled_task_ids"] == [
        0,
        16,
        18,
        20,
        22,
        24,
        26,
        28,
    ]
    assert evidence["subsequent_server_stream_count"] == 7
    assert evidence["subsequent_slot_selection_count"] == 0
    assert evidence["system_memory"]["free"] == "659.2 MiB"


def test_historical_log_without_matching_task_is_not_fabricated():
    evidence = extract_historical_runner_evidence("model loaded")

    assert evidence["status"] == "NOT_FOUND"
    assert evidence["expected_prompt_tokens"] == 988


def test_cuda_load_failure_preserves_concrete_runner_evidence():
    evidence = extract_cuda_load_failure("\n".join([
        "CUDA error: shared object initialization failed",
        "llama-server terminated exit status 0xc0000409",
        "Load failed",
    ]))

    assert evidence["status"] == "FOUND"
    assert evidence["cuda_error"] is True
    assert evidence["runner_exit_0xc0000409"] is True
    assert evidence["load_failed"] is True


def test_causal_synthesis_diagnoses_runner_not_request_or_harness():
    result = build_causal_synthesis(**_synthesis_inputs())

    assert result["decision"] == FINAL_DECISION
    assert result["diagnosis"]["request_or_harness_cause"] is False
    assert result["hypotheses"]["H1_SCHEMA_COMPLEXITY"]["status"] == (
        "NOT_SUPPORTED"
    )
    assert result["hypotheses"]["H3_STREAM_HANDLING"]["status"] == (
        "NOT_SUPPORTED"
    )
    assert result["hypotheses"]["H6_HTTP_TIMEOUT_LAYER"]["status"] == (
        "SUPPORTED"
    )
    assert result["hypotheses"]["H7_OLLAMA_RUNTIME"]["status"] == (
        "SUPPORTED"
    )


def test_causal_synthesis_stays_partial_without_exact_reconstruction():
    inputs = _synthesis_inputs()
    inputs["clean_summary"]["reconstruction"][
        "request_fingerprint_matches"
    ] = False

    result = build_causal_synthesis(**inputs)

    assert result["decision"] == (
        "MODEL_HARNESS_STATEFUL_PROVIDER_PATH_PARTIALLY_DIAGNOSED"
    )


def test_runtime_identity_uses_supported_ollama_ps_command(monkeypatch):
    commands = []

    def fake_command(command):
        commands.append(command)
        return "NAME ID SIZE PROCESSOR CONTEXT UNTIL"

    monkeypatch.setattr(diagnostic, "command_output", fake_command)
    monkeypatch.setattr(diagnostic, "nvidia_snapshot", lambda: {})
    monkeypatch.setattr(diagnostic, "_system_snapshot", lambda: {})

    result = diagnostic.runtime_identity(
        diagnostic.DiagnosticConfig(
            output_dir=diagnostic.DIAGNOSTIC_ROOT / "identity-test",
            mode="compare",
        )
    )

    assert ["ollama", "ps"] in commands
    assert ["ollama", "ps", "--json"] not in commands
    assert result["ollama_ps"]["command"] == "ollama ps"


def test_synthesized_report_has_all_required_numbered_sections():
    synthesis = build_causal_synthesis(**_synthesis_inputs())
    synthesis["validation_results"] = {
        "pytest": {"status": "PASSED"},
        "post_validation_integrity": {
            "unchanged_since_live_run": False,
            "changed_trees": ["mission_metadata"],
        },
    }
    matrix = {"results": _synthesis_inputs()["clean_results"]}
    report = render_synthesized_report(
        summary={"decision": synthesis["decision"]},
        synthesis=synthesis,
        matrix=matrix,
        v1={"payload_bytes": 716},
        v2={"payload_bytes": 6622, "payload_sha256": "b" * 64},
        diff={
            "same_endpoint": True,
            "same_adapter": True,
            "same_http_client": True,
        },
        schema={
            "bytes": 1341,
            "nodes": 22,
            "maximum_depth": 7,
            "properties": 13,
            "enums": 3,
            "enum_values": 20,
            "required": 13,
        },
        integrity={
            "unchanged": True,
            "tree_changes": {},
            "critical_file_changes": {},
        },
    )

    assert report.count("\n## ") == 24
    assert f"**{FINAL_DECISION}**" in report
    assert "No production change" in report
    assert '"pytest": {"status": "PASSED"}' in report
    assert "Post-validation state unchanged: `False`" in report
    assert "ProjectBuilder test journals" in report
