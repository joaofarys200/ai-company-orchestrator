import asyncio
import json
from dataclasses import replace

import pytest

from backend.model_harness import (
    ExpectedOutput,
    ModelRequest,
    ModelRoute,
    OutputFormat,
    ProviderResult,
)
from backend.model_harness.benchmarking.runner import decision_schema
from backend.model_harness.benchmarking import BenchmarkConfig, BenchmarkMode
from backend.model_harness.benchmarking.runner import StatefulBenchmarkRunner
from scripts.model_harness_stateful_sequence_diagnostic import (
    VARIANTS,
    SemanticVariantProvider,
    build_parser,
    conditioned_schema_request,
    decode_prompt_payload,
    diagnostic_conclusion,
    explicit_state_request,
    prompt_sequence_state,
    scenario_a01,
    semantic_retry_request,
    structured_prevalidation_events,
)


pytestmark = pytest.mark.unit


def _payload(*, completed=()):
    return {
        "scenario_id": "A01_FIND_RELEVANT_FILE",
        "step": len(completed) + 1,
        "objective": "Find normalize_invoice.",
        "active_constraints": [
            {"id": "C1", "text": "Use fixture evidence."},
            {"id": "C2", "text": "Do not invent paths."},
        ],
        "available_tools": [
            "list_files",
            "read_file",
            "search_text",
            "inspect_symbol",
            "query_fixture_index",
            "finish",
        ],
        "tools_already_called": list(completed),
        "required_tools_before_finish": [
            "list_files",
            "inspect_symbol",
            "read_file",
            "finish",
        ],
        "required_tools_remaining": [
            tool
            for tool in (
                "list_files",
                "inspect_symbol",
                "read_file",
                "finish",
            )
            if tool not in completed
        ],
        "known_references": (
            ["file:src/invoice.py"] if completed else []
        ),
        "minimum_evidence_references": 1,
        "expected_supported_stop": "COMPLETED",
        "planning_required": False,
    }


def _request(*, completed=()):
    allowed = tuple(_payload()["available_tools"])
    return ModelRequest(
        task_profile="TOOL_SELECTION",
        system_prompt="Current system prompt.",
        user_prompt=json.dumps(
            _payload(completed=completed),
            sort_keys=True,
            separators=(",", ":"),
        ),
        allowed_tools=allowed,
        expected_output=ExpectedOutput(
            format=OutputFormat.JSON_SCHEMA,
            schema=decision_schema(allowed),
        ),
        metadata={"repetition": 1, "step": len(completed) + 1},
    )


def _route():
    return ModelRoute(
        provider="ollama",
        model="test-model",
        mode="chat",
        streaming=False,
        thinking=False,
    )


def _decision(tool_name, arguments, *, finish=False):
    conclusion = (
        "normalize_invoice is defined in src/invoice.py at line 1."
        if finish
        else ""
    )
    stop_reason = "COMPLETED" if finish else ""
    return json.dumps({
        "decision": "FINISH" if finish else "CALL_TOOL",
        "tool_name": tool_name,
        "arguments": (
            {
                "conclusion": conclusion,
                "stop_reason": stop_reason,
            }
            if finish
            else arguments
        ),
        "conclusion": conclusion,
        "stop_reason": stop_reason,
        "evidence_refs": (
            ["file:src/invoice.py"] if finish else []
        ),
        "retained_constraint_ids": ["C1", "C2"],
        "plan": [],
    })


class _FakeProvider:
    name = "ollama"
    default_model = "test-model"

    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.requests = []
        self.runner_guard_events = []

    async def generate(self, request, _route, _progress):
        self.requests.append(request)
        return ProviderResult(raw_text=self.outputs.pop(0))


def test_matrix_has_only_s01_to_s05():
    assert [variant.variant_id for variant in VARIANTS] == [
        "S01_CURRENT",
        "S02_EXPLICIT_STATE",
        "S03_PREVALIDATION",
        "S04_CONDITIONED_SCHEMA",
        "S05_SEMANTIC_RETRY",
    ]


def test_cli_can_select_one_existing_variant():
    args = build_parser().parse_args([
        "--only",
        "S04_CONDITIONED_SCHEMA",
    ])

    assert args.only == ["S04_CONDITIONED_SCHEMA"]


def test_explicit_state_has_required_completed_remaining_and_finish_flag():
    request = explicit_state_request(
        _request(completed=("list_files",))
    )
    payload = json.loads(request.user_prompt)

    assert prompt_sequence_state(payload) == {
        "required_tools": [
            "list_files",
            "inspect_symbol",
            "read_file",
            "finish",
        ],
        "completed_tools": ["list_files"],
        "remaining_tools": ["inspect_symbol", "read_file"],
        "finish_allowed": False,
    }
    assert "tools_already_called" not in payload
    assert "required_tools_before_finish" not in payload
    assert "required_tools_remaining" not in payload


def test_explicit_state_preserves_model_harness_recovery_suffix():
    correction = (
        "\nVALIDATION_CORRECTION: Return a new complete JSON decision."
    )
    original = _request()
    recovered_request = replace(
        original,
        user_prompt=original.user_prompt + correction,
    )

    explicit = explicit_state_request(recovered_request)
    payload, suffix = decode_prompt_payload(explicit.user_prompt)

    assert payload["remaining_tools"] == [
        "list_files",
        "inspect_symbol",
        "read_file",
    ]
    assert suffix == correction


def test_conditioned_schema_allows_only_next_required_tool():
    explicit = explicit_state_request(
        _request(completed=("list_files",))
    )
    conditioned = conditioned_schema_request(explicit)
    properties = conditioned.expected_output.schema["properties"]
    payload = json.loads(conditioned.user_prompt)

    assert properties["decision"]["enum"] == ["CALL_TOOL"]
    assert properties["tool_name"]["enum"] == ["inspect_symbol"]
    assert properties["arguments"]["required"] == ["symbol"]
    assert properties["evidence_refs"]["maxItems"] == 0
    assert payload["transition_contract"] == {
        "next_required_tool": "inspect_symbol",
        "allowed_tools_this_step": ["inspect_symbol"],
        "finish_allowed": False,
        "authorized_evidence_refs": ["file:src/invoice.py"],
        "evidence_refs_policy": "must_be_empty",
    }


def test_conditioned_schema_allows_only_finish_after_obligations():
    explicit = explicit_state_request(_request(completed=(
        "list_files",
        "inspect_symbol",
        "read_file",
    )))
    conditioned = conditioned_schema_request(explicit)
    properties = conditioned.expected_output.schema["properties"]

    assert properties["decision"]["enum"] == ["FINISH"]
    assert properties["tool_name"]["enum"] == ["finish"]
    assert properties["stop_reason"]["enum"] == ["COMPLETED"]
    assert properties["arguments"]["required"] == [
        "conclusion",
        "stop_reason",
    ]
    assert properties["evidence_refs"]["items"]["enum"] == [
        "file:src/invoice.py"
    ]
    assert properties["evidence_refs"]["minItems"] == 1
    assert properties["evidence_refs"]["maxItems"] == 1


def test_conditioned_schema_rejects_internal_context_source_as_reference():
    explicit = explicit_state_request(_request(completed=(
        "list_files",
        "inspect_symbol",
        "read_file",
    )))
    conditioned = conditioned_schema_request(explicit)
    allowed = conditioned.expected_output.schema["properties"][
        "evidence_refs"
    ]["items"]["enum"]

    assert allowed == ["file:src/invoice.py"]
    assert "observation:inspect_symbol:deadbeef" not in allowed


def test_s01_forwards_current_request_without_transformation():
    output = json.dumps({
        "decision": "CALL_TOOL",
        "tool_name": "list_files",
        "arguments": {"path": ""},
    })
    delegate = _FakeProvider([output])
    provider = SemanticVariantProvider(VARIANTS[0], delegate)
    original = _request()

    result = asyncio.run(provider.generate(
        original,
        _route(),
        None,
    ))

    assert result.raw_text == output
    assert len(delegate.requests) == 1
    assert delegate.requests[0].system_prompt == original.system_prompt
    assert delegate.requests[0].user_prompt == original.user_prompt
    assert (
        delegate.requests[0].expected_output.schema
        == original.expected_output.schema
    )


def test_s05_retries_once_with_reason_and_next_tool_without_execution():
    premature = json.dumps({
        "decision": "FINISH",
        "tool_name": "finish",
        "arguments": {
            "conclusion": "src/invoice.py",
            "stop_reason": "COMPLETED",
        },
        "conclusion": "src/invoice.py",
        "stop_reason": "COMPLETED",
        "evidence_refs": ["file:src/invoice.py"],
        "retained_constraint_ids": ["C1", "C2"],
        "plan": [],
    })
    corrected = json.dumps({
        "decision": "CALL_TOOL",
        "tool_name": "inspect_symbol",
        "arguments": {"symbol": "normalize_invoice"},
        "conclusion": "",
        "stop_reason": "",
        "evidence_refs": [],
        "retained_constraint_ids": ["C1", "C2"],
        "plan": [],
    })
    delegate = _FakeProvider([premature, corrected])
    provider = SemanticVariantProvider(VARIANTS[4], delegate)

    result = asyncio.run(provider.generate(
        _request(completed=("list_files",)),
        _route(),
        None,
    ))
    retry_payload = json.loads(delegate.requests[1].user_prompt)

    assert result.raw_text == corrected
    assert len(delegate.requests) == 2
    assert retry_payload["semantic_rejection"]["code"] == (
        "PREMATURE_FINISH"
    )
    assert retry_payload["semantic_rejection"][
        "next_required_tool"
    ] == "inspect_symbol"
    assert provider.attempts[0]["premature_finish"] is True
    assert provider.attempts[1]["semantic_retry"] is True


def test_structured_prevalidation_records_no_tool_execution():
    events = structured_prevalidation_events(
        VARIANTS[2],
        [{
            "premature_finish": True,
            "state": {
                "remaining_tools": ["inspect_symbol", "read_file"],
            },
        }],
    )

    assert events == [{
        "code": "PREMATURE_FINISH",
        "stage": "PRE_TOOL",
        "remaining_tools": ["inspect_symbol", "read_file"],
        "next_required_tool": "inspect_symbol",
        "tool_executed": False,
    }]


def test_semantic_retry_preserves_model_responsibility_for_arguments():
    request = explicit_state_request(
        _request(completed=("list_files",))
    )
    corrected = semantic_retry_request(request, {
        "code": "PREMATURE_FINISH",
        "reason": "Required tools remain.",
        "next_required_tool": "inspect_symbol",
        "remaining_tools": ["inspect_symbol", "read_file"],
    })
    payload = json.loads(corrected.user_prompt)

    assert payload["semantic_rejection"]["next_required_tool"] == (
        "inspect_symbol"
    )
    assert "arguments" not in payload["semantic_rejection"]


def test_conditioned_variant_completes_existing_runner_tool_loop_twice():
    outputs = [
        _decision("list_files", {"path": ""}),
        _decision(
            "inspect_symbol",
            {"symbol": "normalize_invoice"},
        ),
        _decision("read_file", {"path": "src/invoice.py"}),
        _decision("finish", {}, finish=True),
    ] * 2
    delegate = _FakeProvider(outputs)
    provider = SemanticVariantProvider(VARIANTS[3], delegate)
    runner = StatefulBenchmarkRunner(
        BenchmarkConfig(
            mode=BenchmarkMode.STANDARD,
            model="test-model",
            output_dir=(
                "diagnostics/model_harness_benchmark/"
                "stateful-sequence-deterministic-test"
            ),
            repetitions=2,
            seed=42,
            context_tokens=8192,
            max_steps=6,
            keep_alive="1m",
            timeout_seconds=30,
            fault_injection=False,
            transition_policy="contract_driven",
        ),
        live_provider=provider,
    )
    scenario = scenario_a01()

    async def run_twice():
        return [
            await runner._run_live_scenario(scenario, repetition)
            for repetition in (1, 2)
        ]

    executions = asyncio.run(run_twice())

    assert [result.status.value for result, _ in executions] == [
        "PASS",
        "PASS",
    ]
    assert [
        list(result.tools_called) for result, _ in executions
    ] == [list(scenario.required_tools)] * 2
    assert len(delegate.requests) == 8


def test_conclusion_selects_first_strict_successful_mechanism():
    variants = [
        {
            "variant": {"variant_id": variant.variant_id},
            "strict_consecutive_success": (
                variant.variant_id == "S04_CONDITIONED_SCHEMA"
            ),
            "recovered_consecutive_sequence": False,
        }
        for variant in VARIANTS
    ]

    decision, conclusion = diagnostic_conclusion(
        variants,
        integrity_unchanged=True,
    )

    assert decision == "STATEFUL_TOOL_SEQUENCE_SEMANTICS_VALIDATED"
    assert "contract-conditioned transition schema" in conclusion
