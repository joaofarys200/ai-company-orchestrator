import asyncio
import hashlib
import json
import uuid
from pathlib import Path

import httpx
import pytest

from backend.model_harness.benchmarking import provider_diagnostic as module
from backend.model_harness.benchmarking.provider_diagnostic import (
    DiagnosticConfig,
    MatrixVariant,
    StatefulProviderDiagnostic,
    Timeline,
    assert_output_location,
    build_matrix_variants,
    classify_exception,
    direct_ollama_call,
    exception_record,
    integrity_comparison,
    load_v1_payload,
    payload_diff,
    payload_structure,
    reconstruct_stateful_request,
    redact_mapping,
    redact_text,
    request_hashes,
    schema_analysis,
    wire_json_bytes,
)
from scripts.model_harness_stateful_provider_diagnostic import (
    build_parser,
    config_from_args,
)


pytestmark = pytest.mark.unit


def _config(
    output: Path | None = None,
    *,
    timeout: float = 5,
) -> DiagnosticConfig:
    return DiagnosticConfig(
        output_dir=output or (
            module.DIAGNOSTIC_ROOT
            / f"provider-diagnostic-test-{uuid.uuid4().hex}"
        ),
        timeout_seconds=timeout,
        mode="compare",
    )


def test_exact_request_reconstruction_matches_historical_trace():
    timeline = Timeline("correlation", "reconstruction")
    bundle = reconstruct_stateful_request(_config(), timeline)

    assert bundle.scenario_id == "A01_FIND_RELEVANT_FILE"
    assert bundle.reconstruction["context_hash_matches"] is True
    assert bundle.reconstruction["request_fingerprint_matches"] is True
    assert bundle.reconstruction["configuration_equivalent"]["equivalent"] is (
        False
    )
    differences = bundle.reconstruction[
        "configuration_equivalent"
    ]["differences"]
    assert set(differences) == {"timeout_seconds"}
    assert bundle.request.fingerprint() == (
        "91105c160dedcdb569fc4570e723aea3f55c778e9231d64e3b11816e8855b6b7"
    )


def test_exact_default_configuration_is_historically_equivalent():
    bundle = reconstruct_stateful_request(
        DiagnosticConfig(
            output_dir=(
                module.DIAGNOSTIC_ROOT
                / f"provider-diagnostic-test-{uuid.uuid4().hex}"
            ),
            mode="compare",
        )
    )

    assert bundle.reconstruction[
        "configuration_equivalent"
    ]["equivalent"] is True


def test_timeline_has_every_stage_and_marks_unavailable_explicitly():
    timeline = Timeline("cid-1", "D01")
    timeline.observe("T00")
    timeline.observe("payload_serialized", details={"bytes": 4})
    timeline.unavailable("T11", "not exposed")

    records = timeline.finalized()

    assert len(records) == 24
    assert {item["stage"] for item in records} == {
        f"T{index:02d}" for index in range(24)
    }
    assert all(item["correlation_id"] == "cid-1" for item in records)
    assert next(
        item for item in records if item["stage"] == "T11"
    )["status"] == "NOT_OBSERVABLE"


@pytest.mark.parametrize(
    ("exception", "classification"),
    [
        (httpx.ConnectTimeout("connect"), "CONNECT_TIMEOUT"),
        (httpx.ReadTimeout("read"), "READ_TIMEOUT"),
        (httpx.WriteTimeout("write"), "WRITE_TIMEOUT"),
        (httpx.PoolTimeout("pool"), "POOL_TIMEOUT"),
        (TimeoutError("total"), "TOTAL_TIMEOUT"),
        (httpx.RemoteProtocolError("bad"), "CLIENT_PROTOCOL_ERROR"),
        (json.JSONDecodeError("bad", "x", 0), "PARSING_ERROR"),
    ],
)
def test_exception_classification_is_concrete(exception, classification):
    assert classify_exception(exception) == classification


def test_exception_record_preserves_class_causes_and_redacted_trace():
    try:
        try:
            raise OSError(10054, "connection reset token=secret")
        except OSError as cause:
            raise httpx.ConnectError(
                "C:\\Users\\person\\repo token=secret"
            ) from cause
    except httpx.ConnectError as exc:
        record = exception_record(
            exc,
            stage="T11",
            correlation_id="cid",
            variant_id="D01",
        )

    assert record["class"] == "ConnectError"
    assert record["stage"] == "T11"
    assert len(record["message_sha256"]) == 64
    assert record["causes"][1]["class"] == "ConnectionResetError"
    serialized = json.dumps(record)
    assert "C:\\\\Users\\\\person" not in serialized
    assert "token=secret" not in serialized


def test_payload_hash_uses_httpx_wire_serialization():
    payload = {"model": "m", "messages": [], "stream": False}
    expected = httpx.Request(
        "POST",
        "http://localhost/api/chat",
        json=payload,
    ).content

    assert wire_json_bytes(
        payload,
        url="http://localhost/api/chat",
    ) == expected
    assert hashlib.sha256(expected).hexdigest() == hashlib.sha256(
        wire_json_bytes(payload)
    ).hexdigest()


def test_payload_structure_contains_hashes_not_prompt_content():
    payload = {
        "model": "m",
        "messages": [
            {"role": "system", "content": "PRIVATE SYSTEM"},
            {"role": "user", "content": "PRIVATE USER"},
        ],
        "stream": False,
        "format": {"type": "object"},
        "options": {"num_ctx": 8192},
    }

    structure = payload_structure(
        payload,
        source="test",
        adapter="adapter",
        client="client",
    )
    serialized = json.dumps(structure)

    assert "PRIVATE SYSTEM" not in serialized
    assert "PRIVATE USER" not in serialized
    assert structure["messages"][0]["content_chars"] == 14
    assert len(structure["payload_sha256"]) == 64


def test_payload_diff_proves_shared_adapter_and_material_differences():
    v1_payload, _ = load_v1_payload()
    v2_bundle = reconstruct_stateful_request(_config())
    v1 = payload_structure(
        v1_payload,
        source="v1",
        adapter="OllamaBenchmarkProvider",
        client="httpx",
    )
    v2 = payload_structure(
        v2_bundle.payload,
        source="v2",
        adapter="OllamaBenchmarkProvider",
        client="httpx",
    )

    result = payload_diff(v1, v2)

    assert result["same_adapter"] is True
    assert result["same_endpoint"] is True
    assert "schema" in result["material_differences"]
    assert "payload_bytes" in result["material_differences"]


def test_schema_analysis_measures_refs_complexity_and_recursion():
    schema = {
        "$defs": {
            "node": {
                "type": "object",
                "properties": {
                    "next": {"$ref": "#/$defs/node"},
                },
            },
        },
        "$ref": "#/$defs/node",
    }

    result = schema_analysis(schema)

    assert result["refs"] == 2
    assert result["refs_resolved"] == 2
    assert result["objects"] == 1
    assert result["properties"] == 1
    assert result["maximum_depth"] >= 4
    assert result["cycles_or_recursion"]


def test_stateful_schema_reports_unconstrained_arguments_as_heuristic():
    bundle = reconstruct_stateful_request(_config())

    result = schema_analysis(bundle.schema)

    assert result["bytes"] > 1_000
    assert result["enums"] == 3
    assert {
        item["path"] for item in result["potentially_problematic"]
    } == {"#/properties/arguments"}
    assert result["compatibility_conclusion"] == (
        "HEURISTIC_ONLY_REQUIRES_MATRIX_CONFIRMATION"
    )


def test_matrix_contains_all_required_variants_and_exact_payload_aliases():
    config = _config()
    bundle = reconstruct_stateful_request(config)
    v1_payload, _ = load_v1_payload()

    variants = build_matrix_variants(
        bundle,
        config,
        v1_payload=v1_payload,
    )
    by_id = {item.variant_id: item for item in variants}

    assert list(by_id) == [
        "D01_BASELINE_SIMPLE",
        "D02_STATEFUL_PROMPT_NO_SCHEMA",
        "D03_STATEFUL_PROMPT_MINIMAL_SCHEMA",
        "D04_FULL_SCHEMA_NO_TOOLS",
        "D05_FULL_SCHEMA_ONE_TOOL",
        "D06_FULL_SCHEMA_ALL_TOOLS",
        "D07_DIRECT_OLLAMA_FULL_REQUEST",
        "D08_HARNESS_FULL_REQUEST",
        "D09_V1_PROVIDER_WITH_V2_PAYLOAD",
        "D10_V2_PROVIDER_WITH_V1_PAYLOAD",
        "D11_SCHEMA_AS_PROMPT_ONLY",
        "D12_SCHEMA_COMPLEXITY_REDUCTION",
    ]
    assert wire_json_bytes(by_id["D06_FULL_SCHEMA_ALL_TOOLS"].payload) == (
        wire_json_bytes(
            by_id["D07_DIRECT_OLLAMA_FULL_REQUEST"].payload
        )
    )
    assert by_id["D09_V1_PROVIDER_WITH_V2_PAYLOAD"].execution_path == (
        "alias"
    )
    assert by_id["D10_V2_PROVIDER_WITH_V1_PAYLOAD"].execution_path == (
        "not_applicable"
    )


def test_matrix_changes_tool_representation_deterministically():
    config = _config()
    bundle = reconstruct_stateful_request(config)
    variants = {
        item.variant_id: item
        for item in build_matrix_variants(bundle, config)
    }

    no_tools = variants["D04_FULL_SCHEMA_NO_TOOLS"]
    one_tool = variants["D05_FULL_SCHEMA_ONE_TOOL"]
    all_tools = variants["D06_FULL_SCHEMA_ALL_TOOLS"]

    assert no_tools.request.allowed_tools == ()
    assert one_tool.request.allowed_tools == ("list_files", "finish")
    assert len(all_tools.request.allowed_tools) == 6
    assert no_tools.payload["format"]["properties"]["tool_name"] == {
        "type": "string"
    }


def test_redaction_removes_secrets_and_local_paths():
    value = {
        "Authorization": "Bearer abc",
        "nested": "C:\\Users\\person\\repo api_key=abc",
    }

    redacted = redact_mapping(value)

    assert redacted["Authorization"] == "[REDACTED]"
    assert "[LOCAL_PATH]" in redacted["nested"]
    assert "abc" not in json.dumps(redacted)
    assert "Bearer [REDACTED]" == redact_text("Bearer abc")


@pytest.mark.integration
def test_direct_stream_capture_observes_first_byte_token_and_validation():
    body = (
        b'{"message":{"content":"{\\"action\\":\\"continue\\"}"},"done":false}\n'
        b'{"message":{"content":""},"done":true,"done_reason":"stop",'
        b'"prompt_eval_count":4,"eval_count":3}\n'
    )

    async def handler(request):
        assert request.url.path == "/api/chat"
        return httpx.Response(200, content=body)

    transport = httpx.MockTransport(handler)
    variant = MatrixVariant(
        "TEST_STREAM",
        "stream",
        {
            "model": "test",
            "messages": [],
            "stream": True,
        },
        {
            "type": "object",
            "required": ["action"],
            "properties": {"action": {"type": "string"}},
        },
        "direct_ollama",
        "test",
    )

    result = asyncio.run(direct_ollama_call(
        variant,
        _config(),
        transport=transport,
    ))

    assert result.status == "SUCCEEDED"
    assert result.done is True
    assert result.input_tokens == 4
    assert result.output_tokens == 3
    assert result.model_content_chars == len('{"action":"continue"}')
    assert next(
        item for item in result.timeline if item["stage"] == "T15"
    )["status"] == "OBSERVED"
    assert next(
        item for item in result.timeline if item["stage"] == "T17"
    )["status"] == "OBSERVED"


@pytest.mark.integration
def test_direct_timeout_keeps_concrete_type_and_no_fabricated_headers():
    async def handler(request):
        raise httpx.ReadTimeout("timed out", request=request)

    variant = MatrixVariant(
        "TEST_TIMEOUT",
        "timeout",
        {"model": "test", "messages": [], "stream": False},
        None,
        "direct_ollama",
        "test",
    )

    result = asyncio.run(direct_ollama_call(
        variant,
        _config(),
        transport=httpx.MockTransport(handler),
    ))

    assert result.status == "READ_TIMEOUT"
    assert result.exception["class"] == "ReadTimeout"
    assert result.exception["timeout_type"] == "read"
    assert next(
        item for item in result.timeline if item["stage"] == "T14"
    )["status"] == "NOT_OBSERVABLE"


def test_manifest_defaults_to_hash_only_and_debug_is_opt_in(tmp_path, monkeypatch):
    root = tmp_path / "diagnostic"
    monkeypatch.setattr(module, "DIAGNOSTIC_ROOT", root)
    output = root / "run"
    config = DiagnosticConfig(output_dir=output, mode="compare")
    diagnostic = StatefulProviderDiagnostic(config)
    bundle = reconstruct_stateful_request(config)
    manifest = diagnostic._manifest(
        "now",
        bundle,
        {"case_id": "v1"},
        {},
    )

    assert manifest["prompts_stored"] is False
    assert manifest["payload_content_stored"] is False
    assert manifest["execution_classification"] == "offline"
    serialized = json.dumps(manifest)
    assert bundle.request.system_prompt not in serialized

    debug_config = DiagnosticConfig(
        output_dir=root / "debug",
        mode="compare",
        debug_payload=True,
    )
    debug_manifest = StatefulProviderDiagnostic(debug_config)._manifest(
        "now",
        bundle,
        {"case_id": "v1"},
        {},
    )
    assert debug_manifest["prompts_stored"] is True

    live_config = DiagnosticConfig(
        output_dir=root / "live",
        mode="exact",
    )
    live_bundle = reconstruct_stateful_request(live_config)
    live_manifest = StatefulProviderDiagnostic(live_config)._manifest(
        "now",
        live_bundle,
        {"case_id": "v1"},
        {},
    )
    assert live_manifest["execution_classification"] == "live_model"


def test_artifact_writers_stay_in_diagnostic_directory(tmp_path, monkeypatch):
    root = tmp_path / "diagnostic"
    monkeypatch.setattr(module, "DIAGNOSTIC_ROOT", root)
    output = root / "run"
    diagnostic = StatefulProviderDiagnostic(
        DiagnosticConfig(output_dir=output, mode="compare")
    )
    output.mkdir(parents=True)

    diagnostic._write_json("a/value.json", {"ok": True})
    diagnostic._write_jsonl("events.jsonl", [{"event": 1}])

    assert json.loads(
        (output / "a" / "value.json").read_text(encoding="utf-8")
    ) == {"ok": True}
    assert json.loads(
        (output / "events.jsonl").read_text(encoding="utf-8")
    ) == {"event": 1}


def test_integrity_comparison_identifies_changes_without_mutating_values():
    before = {
        "trees": {"projects": {"tree_sha256": "a"}},
        "critical_files": {"x.py": {"sha256": "b"}},
        "fixture_catalog_sha256": "c",
    }
    after = json.loads(json.dumps(before))

    unchanged = integrity_comparison(before, after)
    after["critical_files"]["x.py"]["sha256"] = "changed"
    changed = integrity_comparison(before, after)

    assert unchanged["unchanged"] is True
    assert changed["unchanged"] is False
    assert set(changed["critical_file_changes"]) == {"x.py"}


def test_request_hashes_cover_every_required_input():
    bundle = reconstruct_stateful_request(_config())

    hashes = request_hashes(bundle)

    assert set(hashes) == {
        "system_prompt",
        "user_prompt",
        "effective_user_prompt",
        "context",
        "schema",
        "messages",
        "tools",
        "options",
        "payload",
    }
    assert hashes["tools"]["top_level_count"] == 0
    assert hashes["tools"]["context_representation_count"] == 1


def test_cli_exposes_required_modes_and_flags():
    parser = build_parser()
    args = parser.parse_args([
        "--scenario",
        "A01_FIND_RELEVANT_FILE",
        "--model",
        "qwen3.5:9b",
        "--base-url",
        "http://127.0.0.1:11434",
        "--timeout",
        "42",
        "--output",
        str(module.DIAGNOSTIC_ROOT / "cli-test"),
        "--mode",
        "matrix",
        "--keep-alive",
        "5m",
        "--debug-payload",
        "--capture-ollama-logs",
        "--compare-v1",
        "--direct-ollama",
        "--reset-model-between-variants",
        "--stream-probe-only",
    ])

    config = config_from_args(args)

    assert config.mode == "matrix"
    assert config.timeout_seconds == 42
    assert config.debug_payload is True
    assert config.capture_ollama_logs is True
    assert config.compare_v1 is True
    assert config.direct_ollama is True
    assert config.reset_model_between_variants is True
    assert config.stream_probe_only is True


def test_model_reset_requires_explicit_flag(tmp_path, monkeypatch):
    root = tmp_path / "diagnostic"
    monkeypatch.setattr(module, "DIAGNOSTIC_ROOT", root)
    calls = []

    def fake_reset(model, base_url):
        calls.append((model, base_url))
        return {
            "status": "SUCCEEDED",
            "exit_code": 0,
            "model_unloaded": True,
        }

    monkeypatch.setattr(module, "reset_ollama_model", fake_reset)
    disabled = StatefulProviderDiagnostic(DiagnosticConfig(
        output_dir=root / "disabled",
        mode="matrix",
    ))
    enabled = StatefulProviderDiagnostic(DiagnosticConfig(
        output_dir=root / "enabled",
        mode="matrix",
        reset_model_between_variants=True,
    ))
    enabled.output_dir.mkdir(parents=True)

    asyncio.run(disabled._reset_model_after_variant("D01"))
    asyncio.run(enabled._reset_model_after_variant("D01"))

    assert calls == [("qwen3.5:9b", "http://127.0.0.1:11434")]
    assert enabled.runtime_records[0]["event"] == (
        "model_reset_between_variants"
    )


def test_output_policy_rejects_parent_and_outside_paths(tmp_path):
    with pytest.raises(ValueError):
        assert_output_location(module.DIAGNOSTIC_ROOT)
    with pytest.raises(ValueError):
        assert_output_location(tmp_path / "outside")
