from __future__ import annotations

import ast
import hashlib
import json
import os
from dataclasses import replace
from pathlib import Path

import pytest

from agents.mission_state import MissionStateStore
from backend.capability_registry import (
    SUPPORTED_CAPABILITY_STATUSES,
    CapabilityRegistry,
)
from backend.semantic_context import (
    BuilderConfiguration,
    ContextItem,
    ContextKind,
    ContextSource,
    DeterministicContextCompressor,
    DeterministicContextRanker,
    RankingScore,
    SemanticContextBuilder,
    SemanticContextSerializer,
    SemanticContextTelemetry,
    SemanticContextValidationError,
    SemanticContextValidator,
    SemanticSnapshotExporter,
    WorkspaceInspector,
    canonical_json,
    sha256_text,
)
from tests.capability_registry_fixtures import (
    MODEL_NAME,
    create_bounded_run,
    create_stateful_run,
)


FIXED_MTIME_NS = 1_767_225_600_000_000_000


@pytest.fixture()
def semantic_fixture(tmp_path: Path) -> dict:
    project_root = tmp_path / "workspace" / "projects" / "semantic-demo"
    files = {
        "README.md": "# Fraud demo\nA bounded full-stack fixture.\n",
        "package.json": json.dumps(
            {
                "name": "semantic-demo",
                "main": "backend/server.js",
                "scripts": {
                    "test": "node tests/app.test.js",
                    "build": "node --check frontend/app.js",
                },
                "dependencies": {
                    "express": "4.21.0",
                    "react": "19.0.0",
                },
                "devDependencies": {"vite": "6.0.0"},
            },
            sort_keys=True,
        ),
        "package-lock.json": "{}\n",
        "frontend/index.html": "<main id=\"app\"></main>\n",
        "frontend/app.js": (
            "export function renderFraudScore(score) { return String(score); }\n"
        ),
        "backend/server.js": (
            "export function health() { return { status: 'ok' }; }\n"
        ),
        "tests/app.test.js": (
            "import { health } from '../backend/server.js';\n"
            "if (health().status !== 'ok') process.exit(1);\n"
        ),
        "docs/design.md": "# Design\nPersist fraud scores as JSON.\n",
        "src/score.py": (
            "def fraud_score(amount):\n"
            "    return 1 if amount > 1000 else 0\n"
        ),
        "requirements.txt": "fastapi==0.116.0\npytest==8.4.0\n",
        ".env": "API_KEY=never-read\n",
        "node_modules/ignored.js": "throw new Error('not context');\n",
        "dist/generated.js": "const generated = true;\n",
    }
    for relative, content in files.items():
        path = project_root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="")
        os.utime(path, ns=(FIXED_MTIME_NS, FIXED_MTIME_NS))
    (project_root / "data.sqlite").write_bytes(b"SQLite format 3\x00")
    os.utime(
        project_root / "data.sqlite",
        ns=(FIXED_MTIME_NS, FIXED_MTIME_NS),
    )

    store = MissionStateStore(str(tmp_path))
    store.create_mission(
        "semantic-demo",
        "Fraud detection study",
        "Validate the fraud score backend and supporting report",
        description="Use project evidence and keep the scope bounded.",
        current_phase="implementation",
        mission_id="fraud-mission",
    )
    store.create_work_package(
        "semantic-demo",
        "fraud-mission",
        "Implement fraud score",
        description="Update src/score.py and validate tests.",
        type="CODING",
        priority=90,
        work_package_id="wp-code",
    )
    store.create_deliverable(
        "semantic-demo",
        "fraud-mission",
        "wp-code",
        "Validated implementation",
        description="Code and test evidence.",
        kind="CODE",
        artifact_refs=["file:src/score.py"],
        deliverable_id="code-output",
    )
    store.attach_evidence(
        "semantic-demo",
        "fraud-mission",
        "wp-code",
        "SOURCE",
        "file:README.md",
        description="Project scope",
        evidence_id="scope-evidence",
    )
    store.create_criterion(
        "semantic-demo",
        "fraud-mission",
        "WORK_PACKAGE",
        "wp-code",
        "The source and tests remain consistent.",
        criterion_id="criterion-code",
    )

    diagnostics = tmp_path / "diagnostics"
    create_bounded_run(diagnostics)
    create_stateful_run(diagnostics)
    registry = CapabilityRegistry(diagnostics)
    registry.load()
    telemetry = SemanticContextTelemetry(
        clock=lambda: "2026-01-10T00:00:00+00:00"
    )
    configuration = BuilderConfiguration(
        workspace_root=str(tmp_path),
        project_id="semantic-demo",
        mission_id="fraud-mission",
        model_name=MODEL_NAME,
        task_profile_name="CODE_REASONING",
        benchmark_configuration={
            "context_tokens": 8192,
            "temperature": 0.0,
        },
        compatibility_targets=("MISSION_PLANNER",),
        relevant_paths=("src/score.py",),
        max_workspace_files=100,
        max_content_files=16,
        max_file_bytes=64_000,
        max_total_file_bytes=256_000,
    )
    builder = SemanticContextBuilder(
        registry,
        mission_store=store,
        telemetry=telemetry,
    )
    return {
        "root": tmp_path,
        "project_root": project_root,
        "store": store,
        "registry": registry,
        "configuration": configuration,
        "builder": builder,
        "telemetry": telemetry,
    }


def test_workspace_inspector_is_bounded_read_only_and_detects_project(
    semantic_fixture: dict,
) -> None:
    project_root = semantic_fixture["project_root"]
    before = _tree_hash(project_root)
    result = WorkspaceInspector().inspect(
        semantic_fixture["configuration"],
        mission_terms=("fraud score",),
    )
    after = _tree_hash(project_root)

    assert before == after
    assert result.workspace.stack == ("HTML/JavaScript", "Node", "Python")
    assert result.workspace.frameworks == ("Express", "FastAPI", "React", "Vite")
    assert result.workspace.package_managers == ("npm", "pip")
    assert "frontend/index.html" in result.workspace.entrypoints
    assert "backend/server.js" in result.workspace.entrypoints
    assert "src" in result.workspace.source_roots
    assert "tests/app.test.js" in result.workspace.tests
    assert "docs/design.md" in {
        item.path for item in result.documents.documents
    }
    all_paths = {item.path for item in result.workspace.file_tree}
    assert ".env" not in all_paths
    assert "node_modules/ignored.js" not in all_paths
    assert "dist/generated.js" not in all_paths
    assert "data.sqlite" not in all_paths
    assert len(result.contents) <= 16


def test_workspace_inspector_enforces_file_depth_and_count_limits(
    semantic_fixture: dict,
) -> None:
    configuration = replace(
        semantic_fixture["configuration"],
        max_workspace_files=3,
        max_workspace_depth=2,
    )
    result = WorkspaceInspector().inspect(configuration)

    assert result.workspace.files_considered == 3
    assert result.workspace.traversal_truncated is True


def test_capability_context_contains_only_benchmark_demonstrated_capabilities(
    semantic_fixture: dict,
) -> None:
    snapshot = semantic_fixture["builder"].build(
        semantic_fixture["configuration"]
    )
    profile = semantic_fixture["registry"].get_model(MODEL_NAME)
    expected = {
        item.id.value
        for item in profile.capabilities
        if item.status in SUPPORTED_CAPABILITY_STATUSES
    }
    actual = {
        item.capability_id for item in snapshot.capabilities.capabilities
    }

    assert actual == expected
    assert "stateful_tool_use" not in actual
    assert "vision" not in actual
    assert snapshot.capabilities.compatibility[0].target == "MISSION_PLANNER"


def test_capability_reader_imports_only_registry_public_api() -> None:
    path = (
        Path(__file__).parents[1]
        / "backend"
        / "semantic_context"
        / "capabilities.py"
    )
    tree = ast.parse(path.read_text(encoding="utf-8"))
    registry_imports = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and node.module
        and node.module.startswith("backend.capability_registry")
    }

    assert registry_imports == {"backend.capability_registry"}


def test_builder_is_deterministic_and_excludes_dynamic_resume_time(
    semantic_fixture: dict,
) -> None:
    first = semantic_fixture["builder"].build(
        semantic_fixture["configuration"]
    )
    second = semantic_fixture["builder"].build(
        semantic_fixture["configuration"]
    )
    serializer = SemanticContextSerializer()

    assert first == second
    assert serializer.serialize(first) == serializer.serialize(second)
    assert first.content_sha256 == second.content_sha256
    assert first.snapshot_version == second.snapshot_version
    assert "resumed_at" not in serializer.serialize(first)


def test_context_package_has_all_sections_and_valid_hashes(
    semantic_fixture: dict,
) -> None:
    snapshot = semantic_fixture["builder"].build(
        semantic_fixture["configuration"]
    )
    serializer = SemanticContextSerializer()
    package = serializer.to_package(snapshot)

    assert set(package) == {
        "version",
        "snapshot_version",
        "generated_at",
        "mission",
        "workspace",
        "capabilities",
        "documents",
        "context_items",
        "metadata",
        "ranking",
        "compression",
        "statistics",
        "hashes",
    }
    assert snapshot.content_sha256 == snapshot.computed_content_sha256()
    assert all(len(value) == 64 for value in snapshot.source_hashes.values())
    assert serializer.serialized_sha256(snapshot) == hashlib.sha256(
        serializer.serialize(snapshot).encode("utf-8")
    ).hexdigest()


def test_ranking_is_deterministic_and_uses_explicit_path_proximity(
    semantic_fixture: dict,
) -> None:
    snapshot = semantic_fixture["builder"].build(
        semantic_fixture["configuration"]
    )
    score_by_id = {item.item_id: item for item in snapshot.ranking}
    source_item = next(
        item for item in snapshot.items if item.source_path == "src/score.py"
    )

    assert score_by_id[source_item.item_id].proximity == 1.0
    assert tuple(item.total for item in snapshot.ranking) == tuple(
        sorted(
            (item.total for item in snapshot.ranking),
            reverse=True,
        )
    )
    assert tuple(item.rank for item in snapshot.ranking) == tuple(
        range(1, len(snapshot.ranking) + 1)
    )


def test_compression_deduplicates_and_merges_references_without_rewriting(
    semantic_fixture: dict,
) -> None:
    first = _context_item("first", "same", ("file:a.py",))
    duplicate = _context_item("duplicate", "same", ("file:b.py",))
    empty = _context_item("empty", "", ("file:empty.py",))
    scores = (
        _score(first.item_id, 0.9, 1),
        _score(duplicate.item_id, 0.8, 2),
        _score(empty.item_id, 0.7, 3),
    )
    result = DeterministicContextCompressor().compress(
        (first, duplicate, empty),
        scores,
        semantic_fixture["configuration"],
    )

    assert len(result.items) == 1
    assert result.items[0].content == "same"
    assert result.items[0].references == ("file:a.py", "file:b.py")
    assert result.result.duplicate_items == 1
    assert {item.reason for item in result.result.rejected} == {
        "duplicate_content",
        "empty_content",
    }


def test_compression_enforces_item_and_total_budgets(
    semantic_fixture: dict,
) -> None:
    items = (
        _context_item("a", "12345", ("file:a.py",)),
        _context_item("b", "67890", ("file:b.py",)),
    )
    scores = (
        _score(items[0].item_id, 0.9, 1),
        _score(items[1].item_id, 0.8, 2),
    )
    configuration = replace(
        semantic_fixture["configuration"],
        max_chars=6,
        max_item_chars=6,
        max_items=2,
    )
    result = DeterministicContextCompressor().compress(
        items,
        scores,
        configuration,
    )

    assert result.result.final_chars == 5
    assert result.result.rejected[0].reason == "total_char_limit"


def test_validator_fails_closed_on_content_hash_and_invalid_reference(
    semantic_fixture: dict,
) -> None:
    snapshot = semantic_fixture["builder"].build(
        semantic_fixture["configuration"]
    )
    item = snapshot.items[0]
    tampered_item = replace(
        item,
        content=f"{item.content}tampered",
        references=("https://invalid.example",),
    )
    tampered = replace(
        snapshot,
        items=(tampered_item, *snapshot.items[1:]),
    )
    result = SemanticContextValidator().validate(tampered)
    codes = {issue.code for issue in result.issues}

    assert result.valid is False
    assert "ITEM_HASH_MISMATCH" in codes
    assert "REFERENCE_INVALID" in codes
    assert "SNAPSHOT_HASH_MISMATCH" in codes
    with pytest.raises(SemanticContextValidationError):
        SemanticContextValidator().validate_or_raise(tampered)


def test_validator_rejects_ranking_and_source_hash_tampering(
    semantic_fixture: dict,
) -> None:
    snapshot = semantic_fixture["builder"].build(
        semantic_fixture["configuration"]
    )
    reversed_ranking = tuple(reversed(snapshot.ranking))
    tampered_sources = dict(snapshot.source_hashes)
    tampered_sources["workspace"] = "a" * 64
    tampered = replace(
        snapshot,
        ranking=reversed_ranking,
        source_hashes=tampered_sources,
    )
    codes = {
        issue.code
        for issue in SemanticContextValidator().validate(tampered).issues
    }

    assert "RANKING_ITEM_ORDER_MISMATCH" in codes
    assert "RANK_ORDER_INVALID" in codes
    assert "SOURCE_HASH_MISMATCH" in codes


def test_validator_rejects_snapshot_version_tampering(
    semantic_fixture: dict,
) -> None:
    snapshot = semantic_fixture["builder"].build(
        semantic_fixture["configuration"]
    )
    tampered = replace(
        snapshot,
        snapshot_version="semantic_context_builder_v1-0000000000000000",
    )
    codes = {
        issue.code
        for issue in SemanticContextValidator().validate(tampered).issues
    }

    assert "SNAPSHOT_VERSION_INVALID" in codes
    assert "SNAPSHOT_HASH_MISMATCH" in codes


def test_snapshot_export_is_atomic_and_byte_deterministic(
    semantic_fixture: dict,
) -> None:
    snapshot = semantic_fixture["builder"].build(
        semantic_fixture["configuration"]
    )
    first_path = semantic_fixture["root"] / "exports" / "first.json"
    second_path = semantic_fixture["root"] / "exports" / "second.json"
    exporter = SemanticSnapshotExporter()
    first = exporter.export(snapshot, first_path)
    second = exporter.export(snapshot, second_path)

    assert first_path.read_bytes() == second_path.read_bytes()
    assert first.sha256 == second.sha256
    assert first.size_bytes == second.size_bytes
    assert not list(first_path.parent.glob("*.tmp"))


def test_telemetry_contains_metrics_but_no_context_or_prompt(
    semantic_fixture: dict,
) -> None:
    semantic_fixture["builder"].build(semantic_fixture["configuration"])
    records = semantic_fixture["telemetry"].snapshot()
    payload = canonical_json(records)

    assert len(records) == 1
    assert records[0]["event"] == "semantic_context_built"
    assert records[0]["items_considered"] >= records[0]["ranked_items"]
    assert records[0]["final_bytes"] > 0
    assert "prompt" not in payload.lower()
    assert "fraud detection study" not in payload.lower()


def test_build_does_not_mutate_mission_workspace_registry_or_sources(
    semantic_fixture: dict,
) -> None:
    tracked_roots = (
        semantic_fixture["project_root"],
        semantic_fixture["root"] / "workspace" / ".jarvis",
        semantic_fixture["root"] / "diagnostics",
    )
    before = tuple(_tree_hash(path) for path in tracked_roots)
    semantic_fixture["builder"].build(semantic_fixture["configuration"])
    after = tuple(_tree_hash(path) for path in tracked_roots)

    assert before == after


def test_semantic_context_package_contains_no_execution_or_model_call_path() -> None:
    package_root = (
        Path(__file__).parents[1] / "backend" / "semantic_context"
    )
    forbidden_imports = {
        "httpx",
        "requests",
        "subprocess",
        "backend.model_harness.harness",
        "backend.model_harness.provider",
        "backend.model_harness.router",
    }
    imported: set[str] = set()
    forbidden_calls: list[str] = []
    for path in package_root.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
            elif (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "os"
                and node.func.attr in {"system", "popen", "spawnl", "spawnv"}
            ):
                forbidden_calls.append(f"{path.name}:{node.lineno}")

    assert forbidden_imports.isdisjoint(imported)
    assert forbidden_calls == []


def test_immutable_contracts_freeze_nested_configuration(
    semantic_fixture: dict,
) -> None:
    configuration = semantic_fixture["configuration"]
    with pytest.raises(TypeError):
        configuration.benchmark_configuration["temperature"] = 1.0

    snapshot = semantic_fixture["builder"].build(configuration)
    with pytest.raises(TypeError):
        snapshot.statistics["selected_items"] = 0
    with pytest.raises(TypeError):
        snapshot.mission.work_packages[0]["title"] = "changed"


def test_ranker_has_stable_tie_breaking(
    semantic_fixture: dict,
) -> None:
    mission = semantic_fixture["builder"].build(
        semantic_fixture["configuration"]
    ).mission
    first = _context_item("z-item", "neutral", ("file:z.py",))
    second = _context_item("a-item", "neutral", ("file:a.py",))
    profile = semantic_fixture["builder"].task_profiles.get("CODE_REASONING")
    ranker = DeterministicContextRanker()

    one = ranker.rank((first, second), mission=mission, task_profile=profile)
    two = ranker.rank((second, first), mission=mission, task_profile=profile)

    assert tuple(item.item_id for item in one) == tuple(
        item.item_id for item in two
    )


def _context_item(
    item_id: str,
    content: str,
    references: tuple[str, ...],
) -> ContextItem:
    return ContextItem(
        item_id=item_id,
        source=ContextSource.WORKSPACE,
        kind=ContextKind.SOURCE_FILE,
        title=item_id,
        content=content,
        source_path=f"{item_id}.py",
        references=references,
        observed_at="2026-01-01T00:00:00+00:00",
        priority=50,
    )


def _score(item_id: str, total: float, rank: int) -> RankingScore:
    return RankingScore(
        item_id=item_id,
        recency=total,
        proximity=total,
        relevance=total,
        type_score=total,
        priority=total,
        task_profile=total,
        mission=total,
        total=total,
        rank=rank,
    )


def _tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    if not root.exists():
        return digest.hexdigest()
    for path in sorted(
        (item for item in root.rglob("*") if item.is_file()),
        key=lambda item: item.relative_to(root).as_posix(),
    ):
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()
