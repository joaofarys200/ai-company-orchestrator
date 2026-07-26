from dataclasses import replace

import pytest

from backend.model_harness.benchmarking import (
    BenchmarkConfig,
    BenchmarkMode,
    BenchmarkScenario,
    CapabilityStatus,
    Constraint,
    FixtureFile,
    FixtureSpec,
    ModelDecision,
    ScenarioGroup,
    ScenarioResult,
    ScenarioStatus,
    StopReason,
    benchmark_scenarios,
    fixture_catalog_hash,
)
from backend.model_harness.benchmarking.runner import (
    build_capability_profile,
    decision_schema,
    scenario_reproducibility,
)


pytestmark = pytest.mark.unit


def _result(
    scenario_id: str,
    repetition: int,
    *,
    capability: str = "capability",
    status: ScenarioStatus = ScenarioStatus.PASS,
    response_hashes: tuple[str, ...] = ("a", "b"),
) -> ScenarioResult:
    return ScenarioResult(
        scenario_id=scenario_id,
        repetition=repetition,
        group="A",
        capability=capability,
        status=status,
        stop_reason=StopReason.COMPLETED,
        step_count=2,
        final_conclusion="supported",
        evidence_refs=("file:a.py",),
        tools_called=("read_file", "finish"),
        retained_constraints=("C1",),
        plan_steps=0,
        criteria=(),
        total_latency_ms=10,
        input_tokens=10,
        output_tokens=5,
        response_hashes=response_hashes,
        context_range_chars=(100, 200),
        recovery_used=False,
    )


def _config() -> BenchmarkConfig:
    return BenchmarkConfig(
        mode=BenchmarkMode.STANDARD,
        model="test-model",
        output_dir=(
            "diagnostics/model_harness_benchmark/stateful-contract-test"
        ),
        repetitions=2,
        seed=42,
        context_tokens=8192,
        max_steps=6,
        keep_alive="1m",
        timeout_seconds=30,
    )


def test_scenario_loader_has_required_groups_and_counts():
    smoke = benchmark_scenarios(BenchmarkMode.SMOKE)
    standard = benchmark_scenarios(BenchmarkMode.STANDARD)
    full = benchmark_scenarios(BenchmarkMode.FULL)

    assert len(smoke) == 10
    assert len(standard) == 36
    assert len(full) == 92
    assert {item.group for item in smoke} == set(ScenarioGroup)
    assert len({item.scenario_id for item in standard}) == 36
    assert fixture_catalog_hash() == fixture_catalog_hash()


def test_full_mode_has_three_distinct_fixture_variants():
    variants = [
        item
        for item in benchmark_scenarios(BenchmarkMode.FULL)
        if item.scenario_id.startswith("A01_FIND_RELEVANT_FILE_")
    ]

    assert [item.variant for item in variants] == [1, 2, 3]
    assert len({item.fixture.content_sha256 for item in variants}) == 3
    assert variants[1].fixture.files != variants[2].fixture.files
    assert any(
        constraint.constraint_id == "V2"
        for constraint in variants[1].constraints
    )


def test_model_decision_is_strongly_parsed():
    decision = ModelDecision.from_mapping({
        "decision": "FINISH",
        "tool_name": "finish",
        "arguments": {
            "conclusion": "done",
            "stop_reason": "COMPLETED",
        },
        "conclusion": "done",
        "stop_reason": "COMPLETED",
        "evidence_refs": ["file:a.py"],
        "retained_constraint_ids": ["C1"],
        "plan": [],
    })

    assert decision.decision == "FINISH"
    assert decision.evidence_refs == ("file:a.py",)
    assert len(decision.output_sha256) == 64


def test_decision_schema_is_closed_and_tool_bounded():
    schema = decision_schema(("read_file", "finish"))

    assert schema["additionalProperties"] is False
    assert schema["properties"]["tool_name"]["enum"] == [
        "read_file",
        "finish",
    ]
    assert "retained_constraint_ids" in schema["required"]


def test_capability_requires_three_cases_and_two_repetitions():
    preliminary = [
        _result("A01", 1),
        _result("A01", 2),
    ]
    demonstrated = [
        _result(case, repetition)
        for case in ("A01", "A02", "A03")
        for repetition in (1, 2)
    ]

    preliminary_profile = build_capability_profile(
        preliminary,
        [],
        _config(),
    )[0]
    demonstrated_profile = build_capability_profile(
        demonstrated,
        [],
        _config(),
    )[0]

    assert (
        preliminary_profile.status
        == CapabilityStatus.DEMONSTRATED_PRELIMINARY
    )
    assert demonstrated_profile.status == CapabilityStatus.DEMONSTRATED
    assert demonstrated_profile.confidence == 1.0


def test_reproducibility_compares_full_step_hash_sequence():
    results = [
        _result("A01", 1, response_hashes=("x", "y")),
        _result("A01", 2, response_hashes=("x", "y")),
        _result("A02", 1, response_hashes=("x",)),
        _result("A02", 2, response_hashes=("z",)),
    ]

    reproducibility = scenario_reproducibility(results)

    assert reproducibility["eligible_cases"] == 2
    assert reproducibility["exact_cases"] == 1
    assert reproducibility["cases"] == {
        "A01": True,
        "A02": False,
    }


def test_contracts_reject_invalid_scenario_and_config():
    fixture = FixtureSpec(
        "fixture",
        (FixtureFile("a.txt", "a"),),
    )
    with pytest.raises(ValueError, match="finish"):
        BenchmarkScenario(
            scenario_id="X",
            title="x",
            group=ScenarioGroup.TOOL_LOOP,
            capability="x",
            objective="x",
            constraints=(Constraint("C1", "read only"),),
            fixture=fixture,
            available_tools=("read_file",),
            max_steps=1,
            expected_stop_reason=StopReason.COMPLETED,
        )
    with pytest.raises(ValueError, match="repetitions"):
        replace(_config(), repetitions=0)
