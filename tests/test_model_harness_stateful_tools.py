import os
from pathlib import Path

import pytest

from backend.model_harness.benchmarking import (
    BenchmarkPathError,
    FixtureFile,
    FixtureSandbox,
    FixtureSpec,
    ToolRequest,
    ToolStatus,
    create_read_only_tool_registry,
)


pytestmark = pytest.mark.unit


@pytest.fixture
def fixture_spec():
    return FixtureSpec(
        fixture_id="tools",
        files=(
            FixtureFile(
                "src/app.py",
                "def target():\n    return 'ready'\n",
            ),
            FixtureFile(
                "src/consumer.py",
                "from src.app import target\n",
            ),
        ),
        index_entries={
            "target": ("symbol:target@src/app.py:1",),
        },
    )


def test_registry_exposes_only_read_only_tools():
    registry = create_read_only_tool_registry()

    assert registry.names() == (
        "list_files",
        "read_file",
        "search_text",
        "inspect_symbol",
        "query_fixture_index",
        "finish",
    )
    assert all(item.read_only for item in registry.definitions())
    assert not {
        "write_file",
        "execute_command",
        "delete",
        "rename",
    }.intersection(registry.names())


@pytest.mark.parametrize(
    "path",
    (
        "../outside.txt",
        "..\\outside.txt",
        "/absolute.txt",
        "C:\\Windows\\system.ini",
        "\\\\server\\share\\file.txt",
    ),
)
def test_path_safety_blocks_external_paths(fixture_spec, path):
    with FixtureSandbox(fixture_spec) as sandbox:
        with pytest.raises(BenchmarkPathError):
            sandbox.resolve_path(path)


def test_sandbox_materializes_copy_and_normalizes_observations(fixture_spec):
    registry = create_read_only_tool_registry()
    with FixtureSandbox(fixture_spec) as sandbox:
        original_hash = fixture_spec.content_sha256
        observation = registry.execute(
            sandbox,
            ToolRequest(
                scenario_id="T",
                step_number=1,
                name="read_file",
                arguments={"path": "src/app.py"},
            ),
        )

        assert observation.status == ToolStatus.SUCCEEDED
        assert observation.references == ("file:src/app.py",)
        assert "content" not in observation.report_view()["result"]
        assert "def target" in observation.raw_context
        assert fixture_spec.content_sha256 == original_hash


def test_search_symbol_and_index_are_deterministic(fixture_spec):
    registry = create_read_only_tool_registry()
    with FixtureSandbox(fixture_spec) as sandbox:
        search = registry.execute(
            sandbox,
            ToolRequest("T", 1, "search_text", {"query": "target"}),
        )
        symbol = registry.execute(
            sandbox,
            ToolRequest("T", 2, "inspect_symbol", {"symbol": "target"}),
        )
        index = registry.execute(
            sandbox,
            ToolRequest("T", 3, "query_fixture_index", {"query": "target"}),
        )

        assert search.result["match_count"] == 2
        assert symbol.references == ("symbol:target@src/app.py:1",)
        assert index.references == ("symbol:target@src/app.py:1",)


def test_unknown_tool_and_invalid_arguments_fail_closed(fixture_spec):
    registry = create_read_only_tool_registry()
    with FixtureSandbox(fixture_spec) as sandbox:
        unavailable = registry.execute(
            sandbox,
            ToolRequest("T", 1, "shell", {"command": "whoami"}),
        )
        invalid = registry.execute(
            sandbox,
            ToolRequest("T", 2, "read_file", {}),
        )

        assert unavailable.status == ToolStatus.BLOCKED
        assert unavailable.error_code == "TOOL_UNAVAILABLE"
        assert invalid.status == ToolStatus.BLOCKED
        assert invalid.error_code == "TOOL_ARGUMENT_INVALID"


def test_external_symlink_is_blocked_when_supported(fixture_spec, tmp_path):
    with FixtureSandbox(fixture_spec) as sandbox:
        external = tmp_path / "external.txt"
        external.write_text("external", encoding="utf-8")
        link = Path(sandbox.root, "link.txt")
        try:
            os.symlink(external, link)
        except (OSError, NotImplementedError):
            pytest.skip("Symlink creation is unavailable on this host.")

        with pytest.raises(BenchmarkPathError):
            sandbox.resolve_path("link.txt")
