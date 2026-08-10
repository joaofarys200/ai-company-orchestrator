import asyncio
import hashlib
import json
import shutil
import uuid
from dataclasses import replace
from pathlib import Path

import pytest

from backend.model_harness import (
    CallableModelProvider,
    ModelResponseStatus,
    ProgressCondition,
    ProgressTracker,
    ProviderResult,
)
from backend.model_harness.benchmarking import (
    BenchmarkConfig,
    BenchmarkMode,
    BenchmarkScenario,
    Constraint,
    FixtureFile,
    FixtureSpec,
    ScenarioGroup,
    ScenarioResult,
    ScenarioStatus,
    StopReason,
    benchmark_scenarios,
)
from backend.model_harness.benchmarking import runner as runner_module
from backend.model_harness.benchmarking.runner import (
    StatefulBenchmarkRunner,
    build_step_context,
    build_step_prompt,
    evaluate_scenario,
    render_report,
    validate_transition,
)
from backend.model_harness.benchmarking.tools import (
    create_read_only_tool_registry,
)
from scripts import model_harness_stateful_benchmark as stateful_cli
from scripts.model_harness_stateful_benchmark import (
    build_parser,
    config_from_args,
)


pytestmark = pytest.mark.unit


def _scenario() -> BenchmarkScenario:
    return BenchmarkScenario(
        scenario_id="T01_STATEFUL",
        title="Stateful fixture",
        group=ScenarioGroup.TOOL_LOOP,
        capability="stateful_tool_use",
        objective="Read facts.txt and report ready.",
        constraints=(
            Constraint("C1", "Use only fixture evidence."),
            Constraint("C2", "Do not invent values."),
        ),
        fixture=FixtureSpec(
            "stateful",
            (FixtureFile("facts.txt", "status=ready\n"),),
        ),
        available_tools=("read_file", "finish"),
        max_steps=3,
        expected_stop_reason=StopReason.COMPLETED,
        required_tools=("read_file", "finish"),
        required_references=("file:facts.txt",),
        required_terms=("ready",),
        minimum_evidence=1,
        smoke=True,
    )


def _config(output: str) -> BenchmarkConfig:
    return BenchmarkConfig(
        mode=BenchmarkMode.SMOKE,
        model="deterministic-model",
        output_dir=output,
        repetitions=1,
        seed=42,
        context_tokens=8192,
        max_steps=3,
        keep_alive="1m",
        timeout_seconds=30,
    )


def _provider():
    calls = 0

    async def callback(request, _route, _progress):
        nonlocal calls
        calls += 1
        prompt = json.loads(request.user_prompt)
        constraints = [
            item["id"] for item in prompt["active_constraints"]
        ]
        if "read_file" not in prompt["tools_already_called"]:
            payload = {
                "decision": "CALL_TOOL",
                "tool_name": "read_file",
                "arguments": {"path": "facts.txt"},
                "conclusion": "",
                "stop_reason": "",
                "evidence_refs": [],
                "retained_constraint_ids": constraints,
                "plan": [],
            }
        else:
            payload = {
                "decision": "FINISH",
                "tool_name": "finish",
                "arguments": {
                    "conclusion": "The status is ready.",
                    "stop_reason": "COMPLETED",
                },
                "conclusion": "The status is ready.",
                "stop_reason": "COMPLETED",
                "evidence_refs": ["file:facts.txt"],
                "retained_constraint_ids": constraints,
                "plan": [],
            }
        return ProviderResult(
            raw_text=json.dumps(payload),
        )

    return CallableModelProvider(
        "ollama",
        "deterministic-model",
        callback,
    )


def _failing_provider():
    async def callback(*_args):
        raise RuntimeError("sensitive provider detail")

    return CallableModelProvider(
        "ollama",
        "deterministic-model",
        callback,
    )


def test_context_builder_records_source_reason_hash_size_and_priority():
    scenario = _scenario()
    registry = create_read_only_tool_registry()
    state = runner_module.StatefulContext(
        scenario.objective,
        scenario.constraints,
    )

    context, context_hash = build_step_context(
        scenario,
        state,
        registry,
        max_chars=50_000,
    )

    assert len(context_hash) == 64
    assert context.items
    assert all(item.content_sha256 for item in context.items)
    assert all("priority" in item.metadata for item in context.items)
    assert all(item.inclusion_reason for item in context.items)


def test_prompt_does_not_include_full_history_and_requires_constraints():
    scenario = _scenario()
    state = runner_module.StatefulContext(
        scenario.objective,
        scenario.constraints,
    )

    system, user = build_step_prompt(scenario, state, 1)

    assert "retained_constraint_ids" in system
    assert "full_history" not in system + user
    assert json.loads(user)["required_tools_remaining"] == [
        "read_file",
        "finish",
    ]


def test_stateful_runner_enables_selected_model_runner_recycle():
    runner = StatefulBenchmarkRunner(
        _config(
            "diagnostics/model_harness_benchmark/"
            "stateful-runner-guard-config-test"
        ),
        live_provider=_provider(),
    )

    assert (
        runner.ollama_config.recycle_loaded_model_before_first_request
        is True
    )


def test_contract_driven_runner_enforces_each_legal_transition():
    requests = []

    async def callback(request, _route, _progress):
        requests.append(request)
        prompt = json.loads(request.user_prompt)
        tool_name = request.expected_output.schema["properties"][
            "tool_name"
        ]["enum"][0]
        constraints = [
            item["id"] for item in prompt["active_constraints"]
        ]
        if tool_name == "read_file":
            decision = {
                "decision": "CALL_TOOL",
                "tool_name": tool_name,
                "arguments": {"path": "facts.txt"},
                "conclusion": "",
                "stop_reason": "",
                "evidence_refs": [],
                "retained_constraint_ids": constraints,
                "plan": [],
            }
        else:
            conclusion = "The status is ready."
            decision = {
                "decision": "FINISH",
                "tool_name": "finish",
                "arguments": {
                    "conclusion": conclusion,
                    "stop_reason": "COMPLETED",
                },
                "conclusion": conclusion,
                "stop_reason": "COMPLETED",
                "evidence_refs": ["file:facts.txt"],
                "retained_constraint_ids": constraints,
                "plan": [],
            }
        return ProviderResult(raw_text=json.dumps(decision))

    provider = CallableModelProvider(
        "ollama",
        "deterministic-model",
        callback,
    )
    runner = StatefulBenchmarkRunner(
        replace(
            _config(
                "diagnostics/model_harness_benchmark/"
                "stateful-contract-driven-test"
            ),
            transition_policy="contract_driven",
        ),
        live_provider=provider,
    )

    result, _steps = asyncio.run(
        runner._run_live_scenario(_scenario(), 1)
    )

    assert result.status == ScenarioStatus.PASS
    assert result.tools_called == ("read_file", "finish")
    assert [
        request.expected_output.schema["properties"]["tool_name"]["enum"]
        for request in requests
    ] == [["read_file"], ["finish"]]
    assert all(
        json.loads(request.user_prompt)["transition_contract"][
            "next_required_tool"
        ] == expected
        for request, expected in zip(
            requests,
            ("read_file", "finish"),
            strict=True,
        )
    )
    assert requests[0].expected_output.schema["properties"][
        "evidence_refs"
    ]["maxItems"] == 0
    assert requests[1].expected_output.schema["properties"][
        "evidence_refs"
    ]["items"]["enum"] == ["file:facts.txt"]


def test_benchmark_config_rejects_unknown_transition_policy():
    with pytest.raises(ValueError, match="transition_policy"):
        replace(_config("diagnostics/invalid-policy"), transition_policy="x")


@pytest.mark.integration
def test_stateful_loop_uses_model_harness_and_finishes():
    runner = StatefulBenchmarkRunner(
        _config(
            "diagnostics/model_harness_benchmark/"
            "stateful-loop-definition-test"
        ),
        live_provider=_provider(),
    )

    result, steps = asyncio.run(
        runner._run_live_scenario(_scenario(), 1)
    )

    assert result.status == ScenarioStatus.PASS
    assert result.stop_reason == StopReason.COMPLETED
    assert result.tools_called == ("read_file", "finish")
    assert len(steps) == 2
    assert all(
        step.validation_result["status"] == "PASSED"
        for step in steps
    )
    assert steps[0].normalized_observation["result"]["path"] == "facts.txt"


@pytest.mark.integration
def test_provider_failure_is_counted_and_safely_described():
    runner = StatefulBenchmarkRunner(
        _config(
            "diagnostics/model_harness_benchmark/"
            "stateful-provider-failure-test"
        ),
        live_provider=_failing_provider(),
    )

    result, steps = asyncio.run(
        runner._run_live_scenario(_scenario(), 1)
    )

    assert result.status == ScenarioStatus.FAIL
    assert result.stop_reason == StopReason.RECOVERY_EXHAUSTED
    assert steps[0].validation_result["provider_errors"] == [{
        "stage": "PROVIDER",
        "type": "RuntimeError",
        "message_sha256": hashlib.sha256(
            b"sensitive provider detail"
        ).hexdigest(),
    }]
    serialized = json.dumps(steps[0].validation_result)
    assert "sensitive provider detail" not in serialized


def test_real_progress_tracker_detects_repeat_and_no_progress():
    tracker = ProgressTracker()
    tracker.record_input("same")
    tracker.record_output("same")
    tracker.record_tool_call("read_file", {"path": "a"})
    tracker.record_input("same")
    tracker.record_output("same")
    snapshot = tracker.record_tool_call("read_file", {"path": "a"})

    assert ProgressCondition.NO_PROGRESS in snapshot.conditions
    assert ProgressCondition.REPEATED_REASONING in snapshot.conditions
    assert ProgressCondition.REPEATED_TOOL_CALLS in snapshot.conditions


@pytest.mark.fault_injection
def test_fault_injection_exercises_recovery_without_identical_retry():
    scenario = next(
        item for item in benchmark_scenarios(BenchmarkMode.STANDARD)
        if item.scenario_id == "E02_TRUNCATED_JSON"
    )
    runner = StatefulBenchmarkRunner(
        _config(
            "diagnostics/model_harness_benchmark/"
            "stateful-fault-definition-test"
        ),
        live_provider=_provider(),
    )

    result, _steps, report = asyncio.run(
        runner._run_fault_scenario(
            scenario,
            1,
        )
    )

    assert result.status == ScenarioStatus.PASS
    assert result.recovery_used
    assert report["calls"] == 2
    assert report["unique_request_fingerprints"] == 2
    assert report["identical_retry"] is False


@pytest.mark.parametrize(
    ("scenario_id", "expected"),
    (
        ("E05_EMPTY_TOOL_RESULT", StopReason.NEEDS_MORE_EVIDENCE),
        ("E06_TOOL_TIMEOUT", StopReason.TOOL_FAILED),
        ("E07_REPEATED_TOOL_CALL", StopReason.REPEATED_TOOL_CALL),
        ("E08_CONTRADICTORY_OBSERVATION", StopReason.UNSUPPORTED_CONCLUSION),
    ),
)
def test_fault_injection_has_explicit_fail_closed_stop(
    scenario_id,
    expected,
):
    scenario = next(
        item for item in benchmark_scenarios(BenchmarkMode.STANDARD)
        if item.scenario_id == scenario_id
    )
    runner = StatefulBenchmarkRunner(
        _config(
            "diagnostics/model_harness_benchmark/"
            "stateful-tool-fault-definition-test"
        ),
        live_provider=_provider(),
    )

    result, _steps, report = runner._run_tool_fault(scenario, 1)

    assert result.status == ScenarioStatus.PASS
    assert result.stop_reason == expected
    assert report["actual_stop_reason"] == expected.value


@pytest.mark.integration
def test_runner_generates_required_artifacts_without_prompts(monkeypatch):
    run_name = f"test-stateful-{uuid.uuid4().hex}"
    relative = (
        f"diagnostics/model_harness_benchmark/{run_name}"
    )
    output = Path(relative)
    integrity = {
        "trees": {},
        "critical_files": {},
        "fixture_catalog_sha256": "fixture-hash",
    }

    async def fake_runtime(_config):
        return {"runtime": "deterministic"}

    monkeypatch.setattr(
        runner_module,
        "benchmark_scenarios",
        lambda *_args, **_kwargs: (_scenario(),),
    )
    monkeypatch.setattr(
        runner_module,
        "runtime_metadata",
        fake_runtime,
    )
    monkeypatch.setattr(
        runner_module,
        "runtime_after_metadata",
        fake_runtime,
    )
    monkeypatch.setattr(
        runner_module,
        "integrity_snapshot",
        lambda: integrity,
    )
    try:
        runner = StatefulBenchmarkRunner(
            _config(relative),
            live_provider=_provider(),
        )
        summary = asyncio.run(runner.run())

        expected = {
            "REPORT.md",
            "summary.json",
            "manifest.json",
            "capability_profile.json",
            "scenario_results.json",
            "step_trace.jsonl",
            "integrity.json",
            "telemetry.jsonl",
            "fault_injection_report.json",
        }
        assert expected.issubset({
            item.name for item in output.iterdir()
        })
        manifest = json.loads(
            (output / "manifest.json").read_text(encoding="utf-8")
        )
        assert manifest["prompts_stored"] is False
        assert not (output / "debug_prompts").exists()
        assert summary["integrity"]["unchanged"] is True
        assert summary["model_calls"] == 2
        assert summary["fault_injection_steps"] == 0
        assert any(
            "benchmark-only" in item
            and "production Provider and ModelHarness are unchanged" in item
            for item in summary["limitations"]
        )
    finally:
        if output.exists():
            shutil.rmtree(output)


def test_cli_supports_required_modes_and_flags():
    parser = build_parser()
    args = parser.parse_args([
        "--mode",
        "standard",
        "--model",
        "qwen3.5:9b",
        "--output",
        "diagnostics/model_harness_benchmark/cli-test",
        "--repetitions",
        "2",
        "--seed",
        "7",
        "--context-tokens",
        "16000",
        "--max-steps",
        "5",
        "--keep-alive",
        "10m",
        "--timeout",
        "90",
        "--no-fault-injection",
        "--debug-prompts",
        "--transition-policy",
        "contract_driven",
    ])
    config = config_from_args(args)

    assert config.mode == BenchmarkMode.STANDARD
    assert config.repetitions == 2
    assert config.seed == 7
    assert config.context_tokens == 16000
    assert config.max_steps == 5
    assert config.fault_injection is False
    assert config.debug_prompts is True
    assert config.transition_policy == "contract_driven"


def test_cli_presentation_serializes_complete_scenario_result(
    monkeypatch,
    capsys,
):
    scenario_result = ScenarioResult(
        scenario_id="T01_PRESENTATION",
        repetition=1,
        group="A",
        capability="stateful_tool_use",
        status=ScenarioStatus.PASS,
        stop_reason=StopReason.COMPLETED,
        step_count=1,
        final_conclusion="done",
        evidence_refs=("file:facts.txt",),
        tools_called=("finish",),
        retained_constraints=("C1",),
        plan_steps=0,
        criteria=(),
        total_latency_ms=10,
        input_tokens=5,
        output_tokens=2,
        response_hashes=("response-hash",),
        context_range_chars=(10, 10),
        recovery_used=False,
    )
    summary = {
        "scenario_repetitions": 1,
        "passed_repetitions": 1,
        "failed_repetitions": 0,
        "model_calls": 1,
        "integrity": {"unchanged": True},
        "decision": "MODEL_HARNESS_STATEFUL_CAPABILITIES_VALIDATED",
        "infrastructure_errors": [],
    }

    class FakeRunner:
        def __init__(self, _config):
            self.scenario_results = [scenario_result]

        async def run(self):
            return summary

    monkeypatch.setattr(
        stateful_cli,
        "StatefulBenchmarkRunner",
        FakeRunner,
    )

    exit_code = asyncio.run(stateful_cli.async_main([
        "--output",
        (
            "diagnostics/model_harness_benchmark/"
            "stateful-presentation-test"
        ),
        "--no-fault-injection",
    ]))
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["scenario_results"] == [{
        "scenario_id": "T01_PRESENTATION",
        "repetition": 1,
        "group": "A",
        "capability": "stateful_tool_use",
        "status": "PASS",
        "stop_reason": "COMPLETED",
        "step_count": 1,
        "final_conclusion": "done",
        "evidence_refs": ["file:facts.txt"],
        "tools_called": ["finish"],
        "retained_constraints": ["C1"],
        "plan_steps": 0,
        "criteria": [],
        "total_latency_ms": 10,
        "input_tokens": 5,
        "output_tokens": 2,
        "response_hashes": ["response-hash"],
        "context_range_chars": [10, 10],
        "recovery_used": False,
        "errors": [],
    }]


def test_report_has_all_required_sections():
    summary = {
        "mode": "smoke",
        "model": "test",
        "passed_repetitions": 1,
        "scenario_repetitions": 1,
        "decision": (
            "MODEL_HARNESS_STATEFUL_CAPABILITIES_PARTIALLY_VALIDATED"
        ),
        "scenario_definitions": 1,
        "total_steps": 2,
        "model_calls": 2,
        "performance": {
            "context_chars": {"min": 10, "max": 100},
            "latency_ms": {"median": 1, "p95": 2},
            "tokens_per_second": {"mean": 3},
        },
        "stop_reasons": {"COMPLETED": 1},
        "recovery_used_repetitions": 0,
        "capability_statuses": {},
        "reproducibility": {
            "exact_cases": 0,
            "eligible_cases": 0,
        },
        "integrity": {
            "unchanged": True,
            "integrity_failed": False,
        },
        "infrastructure_errors": [],
        "limitations": [],
    }

    report = render_report(summary, ())

    for section in range(1, 24):
        assert f"## {section}." in report
