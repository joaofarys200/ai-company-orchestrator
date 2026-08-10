from __future__ import annotations

import argparse
import asyncio
import difflib
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import uuid
from dataclasses import asdict, dataclass, field, fields
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.model_harness import (  # noqa: E402
    ExecutionConstraints,
    ExpectedOutput,
    ModelPreferences,
    ModelRequest,
    ModelResponseStatus,
    OllamaExecutionOptions,
    OutputFormat,
    get_model_harness,
)


MODEL = "qwen3.5:9b"
CONTEXT_TOKENS = 8_192
OUTPUT_TOKENS = 512
TEMPERATURE = 0.0
TOP_P = 0.8
SEED = 42
TASK_PROFILE = "TOOL_SELECTION"
RECOVERY_SCENARIO_ID = "S3_RECOVERY_AFTER_REAL_VALIDATION_FAILURE"
VALID_BASELINE_SCENARIO_IDS = (
    "S1_INSPECTION",
    "S2_SIMPLE_EDIT",
    "S4_STATEFUL_DISCIPLINE",
)
RECOVERY_REGRESSION_TYPE = "normalize_task_signature_syntax_error"
TOOL_NAMES = (
    "list_files",
    "inspect_symbol",
    "read_file",
    "apply_patch",
    "run_validation",
    "show_diff",
    "finish",
)
SOURCE_AREAS = (
    "agents",
    "backend",
    "intelligence",
    "frontend/src",
)


@dataclass(frozen=True)
class Scenario:
    scenario_id: str
    title: str
    objective: str
    required_sequence: tuple[str, ...]
    test_mode: str
    expects_edit: bool
    expects_failed_validation: bool = False
    regression_mode: str = ""
    strict_sequence: bool = True
    max_steps: int = 12


@dataclass
class StepRecord:
    step: int
    status: str
    action: str = ""
    tool_name: str = ""
    arguments: dict[str, Any] = field(default_factory=dict)
    raw_response: str = ""
    structured_valid: bool = False
    semantic_valid: bool = False
    validation_error: str = ""
    observation: dict[str, Any] = field(default_factory=dict)
    latency_ms: int = 0
    input_tokens: int | None = None
    output_tokens: int | None = None
    response_sha256: str = ""
    request_id: str = ""
    provider: str = ""
    model: str = ""
    task_profile: str = TASK_PROFILE
    schema_validation: str = "NOT_RUN"
    files_read: list[str] = field(default_factory=list)
    files_changed: list[str] = field(default_factory=list)


@dataclass
class RepetitionResult:
    scenario_id: str
    repetition: int
    status: str
    stop_reason: str
    duration_seconds: float
    steps_used: int
    tool_sequence: list[str]
    structurally_valid_responses: int
    response_count: int
    schema_failures: int
    invalid_tools: int
    repeated_calls: int
    premature_finish: int
    validation_runs: int
    failed_validations: int
    corrections_after_failure: int
    tests_executed: list[dict[str, Any]]
    false_success: bool
    fixture_integrity: bool
    unrelated_file_unchanged: bool
    input_tokens: int
    output_tokens: int
    latency_ms: int
    steps: list[dict[str, Any]]
    errors: list[str]
    recovery: dict[str, Any] = field(default_factory=dict)


SCENARIOS = (
    Scenario(
        scenario_id="S1_INSPECTION",
        title="Inspecao read-only",
        objective=(
            "Inspect the repository, locate normalizeTask, read its "
            "implementation, then explain whether empty input is rejected. "
            "Do not modify any file."
        ),
        required_sequence=(
            "list_files",
            "inspect_symbol",
            "read_file",
            "finish",
        ),
        test_mode="empty_task",
        expects_edit=False,
        max_steps=7,
    ),
    Scenario(
        scenario_id="S2_SIMPLE_EDIT",
        title="Alteracao simples validada",
        objective=(
            "Fix addTask in src/tasks.js so empty or whitespace-only input "
            "leaves the original list unchanged. Inspect before editing, "
            "apply a minimal patch, run validation, inspect the diff, and "
            "finish only after validation succeeds."
        ),
        required_sequence=(
            "list_files",
            "inspect_symbol",
            "read_file",
            "apply_patch",
            "run_validation",
            "show_diff",
            "finish",
        ),
        test_mode="empty_task",
        expects_edit=True,
        max_steps=10,
    ),
    Scenario(
        scenario_id=RECOVERY_SCENARIO_ID,
        title="Recuperacao apos falha real de validacao",
        objective=(
            "Fix addTask in src/tasks.js so empty or whitespace-only input "
            "leaves the original list unchanged. Inspect the implementation "
            "before editing, apply a minimal patch, run the project validation, "
            "use any real validation evidence to resolve remaining problems, "
            "retest, inspect the final diff, and finish only after validation "
            "succeeds."
        ),
        required_sequence=(
            "list_files",
            "inspect_symbol",
            "read_file",
            "apply_patch",
            "run_validation",
            "read_file",
            "apply_patch",
            "run_validation",
            "show_diff",
            "finish",
        ),
        test_mode="empty_task",
        expects_edit=True,
        expects_failed_validation=True,
        regression_mode=RECOVERY_REGRESSION_TYPE,
        max_steps=14,
    ),
    Scenario(
        scenario_id="S4_STATEFUL_DISCIPLINE",
        title="Disciplina stateful",
        objective=(
            "Update taskCountLabel in src/tasks.js so one item returns "
            "'1 task' and all other counts return '<n> tasks'. Read before "
            "writing, validate, inspect the diff, and do not repeat tools."
        ),
        required_sequence=(
            "list_files",
            "read_file",
            "apply_patch",
            "run_validation",
            "show_diff",
            "finish",
        ),
        test_mode="singular_label",
        expects_edit=True,
        max_steps=10,
    ),
)


class BenchmarkHarnessError(RuntimeError):
    pass


class IsolatedProject:
    def __init__(
        self,
        root: Path,
        test_mode: str,
        regression_mode: str = "",
    ):
        self.root = root
        self.test_mode = test_mode
        self.regression_mode = regression_mode
        self.initial_bytes: dict[str, bytes] = {}
        self.read_paths: set[str] = set()
        self.tool_calls: list[tuple[str, str]] = []
        self.validation_runs: list[dict[str, Any]] = []
        self.known_references: set[str] = set()
        self.patch_since_validation = False
        self.latest_validation_passed: bool | None = None
        self.failed_validation_observed = False
        self.success_after_failure = False
        self.diff_observed = False
        self.patch_history: list[dict[str, Any]] = []
        self.regression_injection_count = 0
        self.regression_metadata: dict[str, Any] = {}
        self.validation_state = "NOT_RUN"
        self.validation_state_history: list[dict[str, Any]] = []
        self._record_validation_state("NOT_RUN")

    def create(self) -> None:
        self.root.mkdir(parents=True, exist_ok=False)
        files = {
            "src/tasks.js": (
                "export function normalizeTask(value) {\n"
                "  return String(value ?? '').trim();\n"
                "}\n\n"
                "export function addTask(tasks, value) {\n"
                "  const normalized = normalizeTask(value);\n"
                "  return [...tasks, normalized];\n"
                "}\n\n"
                "export function taskCountLabel(tasks) {\n"
                "  return `${tasks.length} tasks`;\n"
                "}\n"
            ),
            "src/app.js": (
                "import { addTask, taskCountLabel } from './tasks.js';\n\n"
                "export function createTaskState(values) {\n"
                "  const tasks = values.reduce(addTask, []);\n"
                "  return { tasks, label: taskCountLabel(tasks) };\n"
                "}\n"
            ),
            "tests/tasks.test.js": self._test_source(),
            "package.json": (
                "{\n"
                '  "name": "jarvis-model-harness-fixture",\n'
                '  "private": true,\n'
                '  "type": "module",\n'
                '  "scripts": {\n'
                '    "check": "node --check src/tasks.js && '
                'node --check src/app.js && '
                'node --check tests/tasks.test.js",\n'
                '    "test": "node tests/tasks.test.js"\n'
                "  }\n"
                "}\n"
            ),
            "README.md": (
                "# ModelHarness isolated fixture\n\n"
                "This file is unrelated to benchmark edits.\n"
            ),
        }
        for relative, content in files.items():
            target = self.root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8", newline="\n")
            self.initial_bytes[relative] = target.read_bytes()

    def _test_source(self) -> str:
        common = (
            "import assert from 'node:assert/strict';\n"
            "import { addTask, taskCountLabel } from "
            "'../src/tasks.js';\n\n"
            "assert.deepEqual(addTask([], ' buy milk '), ['buy milk']);\n"
        )
        if self.test_mode == "singular_label":
            checks = (
                "assert.equal(taskCountLabel([]), '0 tasks');\n"
                "assert.equal(taskCountLabel(['one']), '1 task');\n"
                "assert.equal(taskCountLabel(['one', 'two']), '2 tasks');\n"
            )
        else:
            checks = (
                "assert.deepEqual(addTask(['existing'], '   '), "
                "['existing']);\n"
                "assert.equal(taskCountLabel([]), '0 tasks');\n"
            )
        return common + checks + "console.log('fixture tests passed');\n"

    def _record_validation_state(
        self,
        state: str,
        **metadata: Any,
    ) -> None:
        self.validation_state = state
        self.validation_state_history.append({
            "state": state,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metadata": dict(metadata),
        })

    def execute(
        self,
        tool_name: str,
        arguments: Mapping[str, Any],
    ) -> dict[str, Any]:
        normalized_args = json.dumps(
            dict(arguments),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        self.tool_calls.append((tool_name, normalized_args))
        if tool_name == "list_files":
            result = self._list_files(arguments)
        elif tool_name == "inspect_symbol":
            result = self._inspect_symbol(arguments)
        elif tool_name == "read_file":
            result = self._read_file(arguments)
        elif tool_name == "apply_patch":
            result = self._apply_patch(arguments)
        elif tool_name == "run_validation":
            result = self._run_validation()
        elif tool_name == "show_diff":
            result = self._show_diff()
        else:
            raise ValueError(f"Unsupported evidence tool: {tool_name}")
        self.known_references.update(collect_references(result))
        return result

    def _list_files(self, arguments: Mapping[str, Any]) -> dict[str, Any]:
        requested = str(arguments.get("path") or ".")
        if requested not in {".", ""}:
            raise ValueError("list_files.path must be '.'")
        paths = sorted(
            path.relative_to(self.root).as_posix()
            for path in self.root.rglob("*")
            if path.is_file()
        )
        return {"files": paths, "reference": "project:file-list"}

    def _inspect_symbol(
        self,
        arguments: Mapping[str, Any],
    ) -> dict[str, Any]:
        name = str(arguments.get("name") or "").strip()
        if not name:
            raise ValueError("inspect_symbol.name is required")
        matches = []
        pattern = re.compile(
            rf"\bfunction\s+{re.escape(name)}\s*\("
        )
        for path in self.root.rglob("*.js"):
            relative = path.relative_to(self.root).as_posix()
            for line_number, line in enumerate(
                path.read_text(encoding="utf-8").splitlines(),
                start=1,
            ):
                if pattern.search(line):
                    matches.append({
                        "path": relative,
                        "line": line_number,
                        "signature": line.strip(),
                        "reference": f"{relative}:L{line_number}",
                    })
        if not matches:
            raise ValueError(f"Symbol not found: {name}")
        return {"symbol": name, "definitions": matches}

    def _read_file(self, arguments: Mapping[str, Any]) -> dict[str, Any]:
        relative, target = self._safe_target(arguments.get("path"))
        content = target.read_text(encoding="utf-8")
        self.read_paths.add(relative)
        if (
            self.failed_validation_observed
            and self.latest_validation_passed is False
            and self.validation_state != "FAILURE_EVIDENCE_READ"
        ):
            self._record_validation_state(
                "FAILURE_EVIDENCE_READ",
                path=relative,
            )
        return {
            "path": relative,
            "content": content,
            "sha256": sha256_bytes(target.read_bytes()),
            "reference": f"{relative}:full",
        }

    def _apply_patch(self, arguments: Mapping[str, Any]) -> dict[str, Any]:
        relative, target = self._safe_target(arguments.get("path"))
        if relative not in self.read_paths:
            raise ValueError("read_file is required before apply_patch")
        old_text = arguments.get("old_text")
        new_text = arguments.get("new_text")
        if not isinstance(old_text, str) or not old_text:
            raise ValueError("apply_patch.old_text must be non-empty text")
        if not isinstance(new_text, str):
            raise ValueError("apply_patch.new_text must be text")
        content = target.read_text(encoding="utf-8")
        occurrences = content.count(old_text)
        if occurrences != 1:
            raise ValueError(
                "apply_patch.old_text must match exactly once; "
                f"found {occurrences}"
            )
        result = content.replace(old_text, new_text, 1)
        if result == content:
            raise ValueError("apply_patch must materially change the file")
        target.write_text(result, encoding="utf-8", newline="\n")
        patch_record = {
            "ordinal": len(self.patch_history) + 1,
            "phase": (
                "CORRECTIVE_CHANGE"
                if self.failed_validation_observed
                else "FIRST_CHANGE"
            ),
            "path": relative,
            "before_sha256": sha256_text(content),
            "after_sha256": sha256_text(result),
            "old_text_sha256": sha256_text(old_text),
            "new_text_sha256": sha256_text(new_text),
            "patch_sha256": sha256_text(
                relative + "\0" + old_text + "\0" + new_text
            ),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self.patch_history.append(patch_record)
        self.patch_since_validation = True
        self.latest_validation_passed = None
        self._record_validation_state(
            (
                "CORRECTION_APPLIED"
                if self.failed_validation_observed
                else "FIRST_CHANGE_APPLIED"
            ),
            path=relative,
            patch_sha256=patch_record["patch_sha256"],
        )
        return {
            "path": relative,
            "changed": True,
            "before_sha256": sha256_text(content),
            "after_sha256": sha256_text(result),
        }

    def _inject_regression_once(self) -> None:
        if not self.regression_mode or self.regression_injection_count:
            return
        if self.regression_mode != RECOVERY_REGRESSION_TYPE:
            raise BenchmarkHarnessError(
                f"Unsupported regression mode: {self.regression_mode}"
            )
        if not self.patch_history:
            raise BenchmarkHarnessError(
                "Regression injection requires a model-authored first change"
            )
        relative = "src/tasks.js"
        target = (self.root / relative).resolve()
        try:
            target.relative_to(self.root.resolve())
        except ValueError as exc:
            raise BenchmarkHarnessError(
                "Regression target escaped the fixture"
            ) from exc
        before = target.read_text(encoding="utf-8")
        expected = "export function normalizeTask(value) {"
        injected = "export function normalizeTask(value {"
        occurrences = before.count(expected)
        if occurrences != 1:
            raise BenchmarkHarnessError(
                "Deterministic regression target is unavailable; "
                f"expected one signature, found {occurrences}"
            )
        after = before.replace(expected, injected, 1)
        target.write_text(after, encoding="utf-8", newline="\n")
        self.regression_injection_count = 1
        self.regression_metadata = {
            "type": self.regression_mode,
            "path": relative,
            "injected_at": datetime.now(timezone.utc).isoformat(),
            "before_sha256": sha256_text(before),
            "after_sha256": sha256_text(after),
            "expected_failure_command": "node --check src/tasks.js",
            "injection_count": self.regression_injection_count,
        }
        self._record_validation_state(
            "REGRESSION_INJECTED",
            regression_type=self.regression_mode,
            path=relative,
        )

    def _run_validation(self) -> dict[str, Any]:
        if not self.patch_since_validation:
            raise ValueError(
                "run_validation requires a new patch since the last run"
            )
        if not self.validation_runs:
            self._inject_regression_once()
        commands = (
            ("node --check src/tasks.js", ["node", "--check", "src/tasks.js"]),
            ("node tests/tasks.test.js", ["node", "tests/tasks.test.js"]),
        )
        results = []
        for display, command in commands:
            started = time.perf_counter()
            completed = subprocess.run(
                command,
                cwd=self.root,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=20,
                check=False,
            )
            results.append({
                "command": display,
                "exit_code": completed.returncode,
                "stdout": completed.stdout[-2_000:],
                "stderr": completed.stderr[-2_000:],
                "duration_ms": round(
                    (time.perf_counter() - started) * 1_000
                ),
            })
        passed = all(item["exit_code"] == 0 for item in results)
        if not passed:
            self.failed_validation_observed = True
            self._record_validation_state(
                "FAILED_VALIDATION",
                run_number=len(self.validation_runs) + 1,
                exit_codes=[
                    item["exit_code"] for item in results
                ],
            )
        elif self.failed_validation_observed:
            self.success_after_failure = True
            self._record_validation_state(
                "RECOVERED",
                run_number=len(self.validation_runs) + 1,
                exit_codes=[
                    item["exit_code"] for item in results
                ],
            )
        else:
            self._record_validation_state(
                "PASSED",
                run_number=len(self.validation_runs) + 1,
                exit_codes=[
                    item["exit_code"] for item in results
                ],
            )
        self.latest_validation_passed = passed
        self.patch_since_validation = False
        run = {
            "passed": passed,
            "commands": results,
            "run_number": len(self.validation_runs) + 1,
        }
        self.validation_runs.append(run)
        return run

    def materially_distinct_recovery_patch(self) -> bool:
        if len(self.patch_history) < 2:
            return False
        first = self.patch_history[0]
        second = self.patch_history[1]
        return (
            first["patch_sha256"] != second["patch_sha256"]
            and first["before_sha256"] != first["after_sha256"]
            and second["before_sha256"] != second["after_sha256"]
        )

    def recovery_contract_satisfied(self) -> bool:
        if not self.regression_mode:
            return True
        return (
            self.regression_injection_count == 1
            and len(self.validation_runs) >= 2
            and any(
                command["exit_code"] != 0
                for command in self.validation_runs[0]["commands"]
            )
            and self.failed_validation_observed
            and self.materially_distinct_recovery_patch()
            and self.validation_runs[-1]["passed"]
            and self.success_after_failure
            and self.validation_state == "RECOVERED"
        )

    def _show_diff(self) -> dict[str, Any]:
        if self.latest_validation_passed is not True:
            raise ValueError(
                "show_diff requires the latest validation to pass"
            )
        diffs = []
        changed_paths = []
        for relative, before_bytes in self.initial_bytes.items():
            target = self.root / relative
            after_bytes = target.read_bytes()
            if after_bytes == before_bytes:
                continue
            changed_paths.append(relative)
            before = before_bytes.decode("utf-8").splitlines(keepends=True)
            after = after_bytes.decode("utf-8").splitlines(keepends=True)
            diffs.extend(difflib.unified_diff(
                before,
                after,
                fromfile=f"a/{relative}",
                tofile=f"b/{relative}",
            ))
        self.diff_observed = True
        return {
            "changed_paths": changed_paths,
            "unified_diff": "".join(diffs),
            "reference": "project:final-diff",
        }

    def _safe_target(self, raw_path: Any) -> tuple[str, Path]:
        relative = str(raw_path or "").replace("\\", "/").strip("/")
        if not relative:
            raise ValueError("path is required")
        target = (self.root / relative).resolve()
        root = self.root.resolve()
        try:
            target.relative_to(root)
        except ValueError as exc:
            raise ValueError("path escapes the fixture") from exc
        if not target.is_file():
            raise ValueError(f"file does not exist: {relative}")
        return target.relative_to(root).as_posix(), target

    def changed_paths(self) -> list[str]:
        return sorted(
            relative
            for relative, before in self.initial_bytes.items()
            if (self.root / relative).read_bytes() != before
        )

    def final_diff(self) -> str:
        diffs: list[str] = []
        for relative, before_bytes in self.initial_bytes.items():
            after_bytes = (self.root / relative).read_bytes()
            if after_bytes == before_bytes:
                continue
            before = before_bytes.decode("utf-8").splitlines(keepends=True)
            after = after_bytes.decode("utf-8").splitlines(keepends=True)
            diffs.extend(difflib.unified_diff(
                before,
                after,
                fromfile=f"a/{relative}",
                tofile=f"b/{relative}",
            ))
        return "".join(diffs)


def response_schema(finish_allowed: bool) -> dict[str, Any]:
    tools = list(TOOL_NAMES)
    if not finish_allowed:
        tools.remove("finish")
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "action",
            "tool_name",
            "arguments",
            "conclusion",
            "evidence_refs",
        ],
        "properties": {
            "action": {
                "type": "string",
                "enum": (
                    ["CALL_TOOL", "FINISH"]
                    if finish_allowed
                    else ["CALL_TOOL"]
                ),
            },
            "tool_name": {
                "type": "string",
                "enum": tools,
            },
            "arguments": {
                "type": "object",
            },
            "conclusion": {
                "type": "string",
            },
            "evidence_refs": {
                "type": "array",
                "items": {"type": "string"},
            },
        },
    }


def system_prompt() -> str:
    return (
        "You are the decision component of a controlled IDE agent. Return one "
        "JSON decision matching the schema. Select tools yourself; the runner "
        "will execute them. Use CALL_TOOL for every evidence or editing step. "
        "Use FINISH only when it is represented by the current schema and all "
        "acceptance conditions are proven. Never claim a command passed "
        "without its observation. Read a file before changing it. apply_patch "
        "requires path, old_text, and new_text copied exactly from observed "
        "content. list_files uses {\"path\":\".\"}; inspect_symbol uses "
        "{\"name\":\"...\"}; read_file uses {\"path\":\"...\"}. "
        "run_validation and show_diff use {}. On CALL_TOOL, conclusion must be "
        "empty. On FINISH, conclusion must be non-empty and evidence_refs must "
        "cite one or more entries from known_references. Do not repeat an "
        "identical tool call."
    )


def build_state(
    scenario: Scenario,
    project: IsolatedProject,
    decisions: list[dict[str, Any]],
    observations: list[dict[str, Any]],
) -> dict[str, Any]:
    sequence = [item["tool_name"] for item in decisions]
    next_required = expected_next_tool(scenario, project, sequence)
    finish_allowed = completion_ready(scenario, project, sequence)
    remaining_tools = dynamic_remaining_tools(
        scenario,
        project,
        sequence,
    )
    return {
        "scenario_id": scenario.scenario_id,
        "objective": scenario.objective,
        "step": len(decisions) + 1,
        "available_tools": list(TOOL_NAMES),
        "required_sequence": list(scenario.required_sequence),
        "completed_tools": sequence,
        "remaining_tools": remaining_tools,
        "next_required_tool": next_required,
        "finish_allowed": finish_allowed,
        "files_read": sorted(project.read_paths),
        "latest_validation_passed": project.latest_validation_passed,
        "validation_state": project.validation_state,
        "failed_validation_observed": (
            project.failed_validation_observed
        ),
        "success_after_failure": project.success_after_failure,
        "diff_observed": project.diff_observed,
        "known_references": sorted(project.known_references),
        "recent_decisions": decisions[-4:],
        "observations": observations[-3:],
    }


def completion_ready(
    scenario: Scenario,
    project: IsolatedProject,
    sequence: list[str],
) -> bool:
    if scenario.regression_mode:
        return (
            bool(sequence)
            and sequence[-1] == "show_diff"
            and project.latest_validation_passed is True
            and project.diff_observed
            and project.recovery_contract_satisfied()
        )
    before_finish = list(scenario.required_sequence[:-1])
    if sequence != before_finish:
        return False
    if not scenario.expects_edit:
        return not project.changed_paths()
    if project.latest_validation_passed is not True:
        return False
    if not project.diff_observed:
        return False
    if scenario.expects_failed_validation:
        return project.recovery_contract_satisfied()
    return True


def expected_next_tool(
    scenario: Scenario,
    project: IsolatedProject,
    sequence: list[str],
) -> str | None:
    if not scenario.regression_mode:
        return (
            scenario.required_sequence[len(sequence)]
            if len(sequence) < len(scenario.required_sequence)
            else None
        )
    initial = list(scenario.required_sequence[:5])
    if len(sequence) < len(initial):
        return initial[len(sequence)]
    if project.latest_validation_passed is True:
        return "finish" if project.diff_observed else "show_diff"
    last_tool = sequence[-1] if sequence else ""
    if last_tool == "run_validation":
        return "read_file"
    if last_tool == "read_file":
        return "apply_patch"
    if last_tool == "apply_patch":
        return "run_validation"
    return "read_file"


def dynamic_remaining_tools(
    scenario: Scenario,
    project: IsolatedProject,
    sequence: list[str],
) -> list[str]:
    if not scenario.regression_mode:
        return list(scenario.required_sequence[len(sequence):])
    initial = list(scenario.required_sequence[:5])
    if len(sequence) < len(initial):
        return list(scenario.required_sequence[len(sequence):])
    next_tool = expected_next_tool(scenario, project, sequence)
    if next_tool is None:
        return []
    if next_tool == "finish":
        return ["finish"]
    if next_tool == "show_diff":
        return ["show_diff", "finish"]
    cycle = ["read_file", "apply_patch", "run_validation"]
    start = cycle.index(next_tool)
    return cycle[start:] + ["show_diff", "finish"]


def sequence_satisfies_scenario(
    scenario: Scenario,
    sequence: list[str],
    project: IsolatedProject,
) -> bool:
    if not scenario.regression_mode:
        return sequence == list(scenario.required_sequence)
    initial = list(scenario.required_sequence[:5])
    return (
        sequence[:len(initial)] == initial
        and sequence[-2:] == ["show_diff", "finish"]
        and project.recovery_contract_satisfied()
    )


def validate_decision(
    decision: Mapping[str, Any],
    scenario: Scenario,
    project: IsolatedProject,
    sequence: list[str],
) -> str:
    action = str(decision.get("action") or "")
    tool_name = str(decision.get("tool_name") or "")
    arguments = decision.get("arguments")
    if action not in {"CALL_TOOL", "FINISH"}:
        return "action is invalid"
    if tool_name not in TOOL_NAMES:
        return f"unknown tool: {tool_name}"
    if not isinstance(arguments, Mapping):
        return "arguments must be an object"
    if action == "FINISH" and tool_name != "finish":
        return "FINISH requires tool_name=finish"
    if action == "CALL_TOOL" and tool_name == "finish":
        return "finish requires action=FINISH"
    if scenario.strict_sequence:
        expected = expected_next_tool(scenario, project, sequence)
        if tool_name != expected:
            return (
                f"expected next tool {expected!r}, received "
                f"{tool_name!r}"
            )
    if tool_name == "finish" and not completion_ready(
        scenario,
        project,
        sequence,
    ):
        return "finish attempted before acceptance conditions"
    if tool_name == "finish":
        conclusion = str(decision.get("conclusion") or "").strip()
        references = {
            str(item)
            for item in decision.get("evidence_refs") or []
            if str(item)
        }
        if not conclusion:
            return "finish requires a non-empty conclusion"
        if not references:
            return "finish requires at least one evidence reference"
        unknown = references - project.known_references
        if unknown:
            return (
                "finish cited unknown references: "
                + ", ".join(sorted(unknown))
            )
    if tool_name == "apply_patch" and not project.read_paths:
        return "apply_patch attempted before read_file"
    if tool_name == "run_validation" and not project.patch_since_validation:
        return "run_validation attempted without a new patch"
    if (
        tool_name == "show_diff"
        and project.latest_validation_passed is not True
    ):
        return "show_diff attempted before successful validation"
    return ""


def classify_recovery_outcome(
    project: IsolatedProject,
    proposed_status: str,
) -> tuple[str, str]:
    if not project.regression_mode:
        return proposed_status, ""
    if project.regression_injection_count != 1:
        return (
            "INCONCLUSIVE",
            "the deterministic regression was not injected exactly once",
        )
    if not project.validation_runs:
        return (
            "INCONCLUSIVE",
            "no real validation ran after regression injection",
        )
    first_commands = project.validation_runs[0]["commands"]
    if not any(item["exit_code"] != 0 for item in first_commands):
        return (
            "INCONCLUSIVE",
            "the injected regression did not produce a non-zero exit code",
        )
    if proposed_status == "PASS" and project.recovery_contract_satisfied():
        return "PASS", ""
    return (
        "FAIL",
        "a real validation failure occurred but the model did not recover correctly",
    )


async def execute_model_step(
    *,
    model: str,
    scenario: Scenario,
    state: Mapping[str, Any],
    repetition: int,
    run_id: str,
    mission_id: str,
    agent_id: str,
    executor: str,
) -> tuple[Any, float]:
    finish_allowed = bool(state["finish_allowed"])
    request = ModelRequest(
        task_profile=TASK_PROFILE,
        system_prompt=system_prompt(),
        user_prompt=json.dumps(
            state,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ),
        allowed_tools=TOOL_NAMES,
        expected_output=ExpectedOutput(
            format=OutputFormat.JSON_SCHEMA,
            schema=response_schema(finish_allowed),
        ),
        temperature=TEMPERATURE,
        max_context_tokens=CONTEXT_TOKENS,
        max_output_tokens=OUTPUT_TOKENS,
        metadata={
            "consumer": "productive_model_benchmark",
            "scenario_id": scenario.scenario_id,
            "repetition": repetition,
            "step": state["step"],
            "run_id": run_id,
            "mission_id": mission_id,
            "agent_id": agent_id,
            "executor": executor,
            "top_p": TOP_P,
            "seed": SEED,
            "progress_key": (
                f"productive:{run_id}"
            ),
        },
        model_preferences=ModelPreferences(
            providers=("ollama",),
            models=(model,),
            mode="chat",
        ),
        execution_constraints=ExecutionConstraints(
            max_attempts=1,
            timeout_seconds=180.0,
            streaming=False,
            thinking=False,
            allow_recovery=False,
            stop_on_no_progress=False,
            provider_payload=OllamaExecutionOptions(
                read_timeout=180.0,
                keep_alive="15m",
                require_done=True,
            ),
        ),
    )
    started = time.perf_counter()
    response = await get_model_harness().execute(request)
    return response, time.perf_counter() - started


async def run_repetition(
    scenario: Scenario,
    repetition: int,
    root: Path,
    model: str,
    artifact_dir: Path | None = None,
) -> RepetitionResult:
    started = time.perf_counter()
    run_id = f"run-{repetition:02d}-{uuid.uuid4().hex[:12]}"
    mission_id = f"mission-{run_id}"
    agent_id = "qwen-productive-benchmark-agent"
    executor = "ModelHarnessControlledIDEExecutor"
    provider = "ollama"
    journal_path = (
        artifact_dir / "logs" / f"run-{repetition:02d}.jsonl"
        if artifact_dir is not None
        else None
    )

    def journal(event: str, **payload: Any) -> bool:
        if journal_path is None:
            return False
        append_jsonl(journal_path, {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": event,
            "run_id": run_id,
            "mission_id": mission_id,
            "agent_id": agent_id,
            "executor": executor,
            "provider": provider,
            "model": model,
            "task_profile": TASK_PROFILE,
            **payload,
        })
        return True

    repository_before = source_integrity_snapshot()
    project = IsolatedProject(
        root,
        scenario.test_mode,
        scenario.regression_mode,
    )
    project.create()
    fixture_before = snapshot_directory(root)
    unrelated_before = sha256_file(root / "README.md")
    decisions: list[dict[str, Any]] = []
    observations: list[dict[str, Any]] = []
    records: list[StepRecord] = []
    errors: list[str] = []
    seen_calls: set[tuple[str, str]] = set()
    schema_failures = 0
    invalid_tools = 0
    repeated_calls = 0
    premature_finish = 0
    structurally_valid = 0
    stop_reason = "MAX_STEPS"
    final_status = "FAIL"
    false_success = False
    harness_error = ""
    injection_logged = False
    failure_persisted = False
    recovery_persisted = False
    journal(
        "run_started",
        scenario_id=scenario.scenario_id,
        objective_sha256=sha256_text(scenario.objective),
        fixture_root=root.as_posix(),
    )

    for step_number in range(1, scenario.max_steps + 1):
        state = build_state(
            scenario,
            project,
            decisions,
            observations,
        )
        record = StepRecord(step=step_number, status="STARTED")
        response, elapsed = await execute_model_step(
            model=model,
            scenario=scenario,
            state=state,
            repetition=repetition,
            run_id=run_id,
            mission_id=mission_id,
            agent_id=agent_id,
            executor=executor,
        )
        record.latency_ms = round(elapsed * 1_000)
        record.raw_response = response.raw_text
        record.response_sha256 = sha256_text(response.raw_text)
        record.input_tokens = response.usage.input_tokens
        record.output_tokens = response.usage.output_tokens
        record.request_id = response.request_id
        record.provider = response.provider
        record.model = response.model
        record.task_profile = TASK_PROFILE
        record.schema_validation = response.validation.status.value
        journal(
            "model_response_received",
            step_number=step_number,
            request_id=response.request_id,
            result_status=response.status.value,
            schema_validation=response.validation.status.value,
            response_sha256=record.response_sha256,
            latency_ms=record.latency_ms,
            input_tokens=record.input_tokens,
            output_tokens=record.output_tokens,
        )
        if response.status != ModelResponseStatus.SUCCEEDED:
            schema_failures += 1
            record.status = response.status.value
            record.validation_error = "; ".join(
                f"{issue.code}: {issue.message}"
                for issue in response.validation.issues
            ) or json.dumps(list(response.errors), ensure_ascii=False)
            errors.append(
                f"step {step_number}: {record.validation_error}"
            )
            records.append(record)
            stop_reason = "STRUCTURED_RESPONSE_FAILED"
            journal(
                "step_rejected",
                step_number=step_number,
                request_id=response.request_id,
                reason=record.validation_error,
            )
            break

        decision = response.structured_output
        if not isinstance(decision, Mapping):
            try:
                decision = json.loads(response.raw_text)
            except (TypeError, ValueError):
                decision = None
        if not isinstance(decision, Mapping):
            schema_failures += 1
            record.status = "INVALID_JSON"
            record.validation_error = "response is not a JSON object"
            errors.append(
                f"step {step_number}: response is not a JSON object"
            )
            records.append(record)
            stop_reason = "STRUCTURED_RESPONSE_FAILED"
            journal(
                "step_rejected",
                step_number=step_number,
                request_id=response.request_id,
                reason=record.validation_error,
            )
            break

        structurally_valid += 1
        record.structured_valid = True
        record.action = str(decision.get("action") or "")
        record.tool_name = str(decision.get("tool_name") or "")
        record.arguments = dict(decision.get("arguments") or {})
        sequence = [item["tool_name"] for item in decisions]
        semantic_error = validate_decision(
            decision,
            scenario,
            project,
            sequence,
        )
        if semantic_error:
            invalid_tools += 1
            if record.action == "FINISH" or record.tool_name == "finish":
                premature_finish += 1
            record.status = "SEMANTICALLY_INVALID"
            record.validation_error = semantic_error
            errors.append(f"step {step_number}: {semantic_error}")
            records.append(record)
            stop_reason = "SEMANTIC_VALIDATION_FAILED"
            journal(
                "step_rejected",
                step_number=step_number,
                request_id=response.request_id,
                tool=record.tool_name,
                reason=semantic_error,
            )
            break

        record.semantic_valid = True
        call_key = (
            record.tool_name,
            json.dumps(
                record.arguments,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ),
        )
        if (
            call_key in seen_calls
            and record.tool_name not in {
                "read_file",
                "run_validation",
            }
        ):
            repeated_calls += 1
            record.status = "REPEATED_TOOL_CALL"
            record.validation_error = "identical tool call repeated"
            errors.append(
                f"step {step_number}: identical tool call repeated"
            )
            records.append(record)
            stop_reason = "REPEATED_TOOL_CALL"
            journal(
                "step_rejected",
                step_number=step_number,
                request_id=response.request_id,
                tool=record.tool_name,
                reason=record.validation_error,
            )
            break
        seen_calls.add(call_key)

        normalized_decision = {
            "action": record.action,
            "tool_name": record.tool_name,
            "arguments": record.arguments,
            "conclusion": str(decision.get("conclusion") or ""),
            "evidence_refs": list(
                decision.get("evidence_refs") or []
            ),
        }
        if record.tool_name == "finish":
            decisions.append(normalized_decision)
            record.status = "FINISHED"
            records.append(record)
            stop_reason = "COMPLETED"
            final_status = "PASS"
            journal(
                "finish_accepted",
                step_number=step_number,
                request_id=response.request_id,
                evidence_refs=normalized_decision["evidence_refs"],
            )
            break

        try:
            observation = project.execute(
                record.tool_name,
                record.arguments,
            )
        except Exception as exc:
            if isinstance(exc, BenchmarkHarnessError):
                harness_error = f"{type(exc).__name__}: {exc}"
                record.status = "BENCHMARK_HARNESS_FAILED"
                stop_reason = "BENCHMARK_HARNESS_FAILED"
            else:
                invalid_tools += 1
                record.status = "TOOL_FAILED"
                stop_reason = "TOOL_FAILED"
            record.validation_error = f"{type(exc).__name__}: {exc}"
            errors.append(
                f"step {step_number}: {record.validation_error}"
            )
            records.append(record)
            journal(
                "tool_failed",
                step_number=step_number,
                request_id=response.request_id,
                tool=record.tool_name,
                error_type=type(exc).__name__,
                error_message=str(exc),
                harness_error=bool(harness_error),
            )
            break
        decisions.append(normalized_decision)
        normalized_observation = {
            "tool": record.tool_name,
            "result": observation,
        }
        observations.append(normalized_observation)
        record.observation = observation
        record.files_read = sorted(project.read_paths)
        record.files_changed = project.changed_paths()
        record.status = "TOOL_SUCCEEDED"
        records.append(record)
        journal(
            "tool_completed",
            step_number=step_number,
            request_id=response.request_id,
            tool=record.tool_name,
            files_read=record.files_read,
            files_changed=record.files_changed,
            validation_state=project.validation_state,
            validation_exit_codes=(
                [
                    item["exit_code"]
                    for item in observation.get("commands", [])
                ]
                if record.tool_name == "run_validation"
                else []
            ),
        )
        if project.regression_injection_count and not injection_logged:
            injection_logged = journal(
                "regression_injected",
                step_number=step_number,
                regression=dict(project.regression_metadata),
            )
        if (
            record.tool_name == "run_validation"
            and observation.get("passed") is False
        ):
            failure_persisted = journal(
                "validation_failed",
                step_number=step_number,
                request_id=response.request_id,
                run_number=observation["run_number"],
                commands=observation["commands"],
            )
        elif (
            record.tool_name == "run_validation"
            and observation.get("passed") is True
            and project.success_after_failure
        ):
            recovery_persisted = journal(
                "validation_recovered",
                step_number=step_number,
                request_id=response.request_id,
                run_number=observation["run_number"],
                commands=observation["commands"],
            )

    sequence = [item["tool_name"] for item in decisions]
    if final_status == "PASS":
        if not sequence_satisfies_scenario(
            scenario,
            sequence,
            project,
        ):
            final_status = "FAIL"
            stop_reason = "SEQUENCE_MISMATCH"
            errors.append(
                f"expected {scenario.required_sequence}, got {sequence}"
            )
        elif scenario.expects_edit and not project.changed_paths():
            final_status = "FAIL"
            stop_reason = "NO_EXPECTED_CHANGE"
            errors.append("no project file was changed")
        elif not scenario.expects_edit and project.changed_paths():
            final_status = "FAIL"
            stop_reason = "READ_ONLY_VIOLATION"
            errors.append(
                f"read-only scenario changed {project.changed_paths()}"
            )
        elif (
            scenario.expects_failed_validation
            and not project.success_after_failure
        ):
            final_status = "FAIL"
            stop_reason = "RECOVERY_NOT_DEMONSTRATED"
            errors.append(
                "a failed validation followed by success was not observed"
            )
        elif scenario.expects_edit and (
            project.latest_validation_passed is not True
        ):
            false_success = True
            final_status = "FAIL"
            stop_reason = "FALSE_SUCCESS"
            errors.append("finished without a passing validation")

    if scenario.regression_mode:
        classified, classification_reason = classify_recovery_outcome(
            project,
            final_status,
        )
        if classified != final_status:
            final_status = classified
            stop_reason = (
                "BENCHMARK_INCONCLUSIVE"
                if classified == "INCONCLUSIVE"
                else "RECOVERY_NOT_DEMONSTRATED"
            )
        if classification_reason and classification_reason not in errors:
            errors.append(classification_reason)
    if harness_error:
        final_status = "INCONCLUSIVE"
        stop_reason = "BENCHMARK_HARNESS_FAILED"

    unrelated_after = sha256_file(root / "README.md")
    fixture_after = snapshot_directory(root)
    expected_fixture_change = scenario.expects_edit and final_status == "PASS"
    fixture_integrity = (
        fixture_before == fixture_after
        if not expected_fixture_change
        else set(project.changed_paths()).issubset({"src/tasks.js"})
    )
    validation_runs = len(project.validation_runs)
    failed_validations = sum(
        1 for item in project.validation_runs if not item["passed"]
    )
    repository_after = source_integrity_snapshot()
    outside_fixture_unchanged = repository_before == repository_after
    first_validation = (
        project.validation_runs[0]
        if project.validation_runs
        else {}
    )
    retest = (
        project.validation_runs[-1]
        if len(project.validation_runs) >= 2
        else {}
    )
    failed_step_index = next(
        (
            index
            for index, item in enumerate(records)
            if item.tool_name == "run_validation"
            and item.observation.get("passed") is False
        ),
        None,
    )
    post_failure_action = (
        {
            "tool": records[failed_step_index + 1].tool_name,
            "arguments": records[failed_step_index + 1].arguments,
        }
        if (
            failed_step_index is not None
            and failed_step_index + 1 < len(records)
        )
        else {}
    )
    recovery_details = {
        "run_id": run_id,
        "mission_id": mission_id,
        "agent_id": agent_id,
        "executor": executor,
        "provider": provider,
        "model": model,
        "task_profile": TASK_PROFILE,
        "fixture_root": root.as_posix(),
        "files_read": sorted(project.read_paths),
        "files_changed": project.changed_paths(),
        "first_change": (
            project.patch_history[0]
            if project.patch_history
            else {}
        ),
        "regression": dict(project.regression_metadata),
        "regression_injection_count": (
            project.regression_injection_count
        ),
        "first_validation": first_validation,
        "failure_persisted": failure_persisted,
        "post_failure_action": post_failure_action,
        "second_change": (
            project.patch_history[1]
            if len(project.patch_history) >= 2
            else {}
        ),
        "materially_distinct_second_change": (
            project.materially_distinct_recovery_patch()
        ),
        "retest": retest,
        "recovery_persisted": recovery_persisted,
        "validation_state": project.validation_state,
        "validation_state_history": project.validation_state_history,
        "finish_attempts": sum(
            item.action == "FINISH" or item.tool_name == "finish"
            for item in records
        ),
        "repeated_tool_calls": repeated_calls,
        "fixture_hashes_before": fixture_before,
        "fixture_hashes_after": fixture_after,
        "unrelated_sha256_before": unrelated_before,
        "unrelated_sha256_after": unrelated_after,
        "outside_fixture_unchanged": outside_fixture_unchanged,
        "harness_error": harness_error,
    }
    if artifact_dir is not None:
        diff_path = (
            artifact_dir / "diffs" / f"run-{repetition:02d}.patch"
        )
        diff_path.parent.mkdir(parents=True, exist_ok=True)
        diff_path.write_text(
            project.final_diff(),
            encoding="utf-8",
            newline="\n",
        )
    journal(
        "run_completed",
        status=final_status,
        stop_reason=stop_reason,
        validation_state=project.validation_state,
        fixture_integrity=fixture_integrity,
        outside_fixture_unchanged=outside_fixture_unchanged,
        latency_ms=round((time.perf_counter() - started) * 1_000),
    )
    return RepetitionResult(
        scenario_id=scenario.scenario_id,
        repetition=repetition,
        status=final_status,
        stop_reason=stop_reason,
        duration_seconds=round(time.perf_counter() - started, 3),
        steps_used=len(records),
        tool_sequence=sequence,
        structurally_valid_responses=structurally_valid,
        response_count=len(records),
        schema_failures=schema_failures,
        invalid_tools=invalid_tools,
        repeated_calls=repeated_calls,
        premature_finish=premature_finish,
        validation_runs=validation_runs,
        failed_validations=failed_validations,
        corrections_after_failure=(
            1 if project.success_after_failure else 0
        ),
        tests_executed=[
            command
            for run in project.validation_runs
            for command in run["commands"]
        ],
        false_success=false_success,
        fixture_integrity=fixture_integrity,
        unrelated_file_unchanged=unrelated_before == unrelated_after,
        input_tokens=sum(
            item.input_tokens or 0 for item in records
        ),
        output_tokens=sum(
            item.output_tokens or 0 for item in records
        ),
        latency_ms=sum(item.latency_ms for item in records),
        steps=[asdict(item) for item in records],
        errors=errors,
        recovery=recovery_details,
    )


async def run_benchmark(
    *,
    model: str,
    repetitions: int,
    output_dir: Path,
    scenarios: tuple[Scenario, ...] = SCENARIOS,
    baseline_results: list[RepetitionResult] | None = None,
    baseline_source: str = "",
) -> dict[str, Any]:
    if output_dir.exists():
        raise FileExistsError(f"Output already exists: {output_dir}")
    output_dir.mkdir(parents=True)
    source_before = source_integrity_snapshot()
    started = datetime.now(timezone.utc)
    results: list[RepetitionResult] = []
    for scenario in scenarios:
        for repetition in range(1, repetitions + 1):
            fixture_root = (
                output_dir
                / "fixtures"
                / scenario.scenario_id
                / f"rep-{repetition}"
                / "project"
            )
            result = await run_repetition(
                scenario,
                repetition,
                fixture_root,
                model,
                artifact_dir=output_dir,
            )
            results.append(result)
            run_path = (
                output_dir / f"run-{repetition:02d}.json"
                if len(scenarios) == 1
                else (
                    output_dir
                    / "runs"
                    / scenario.scenario_id
                    / f"rep-{repetition}.json"
                )
            )
            write_json(run_path, asdict(result))
            print(
                f"{scenario.scenario_id} rep-{repetition}: "
                f"{result.status} ({result.stop_reason}) "
                f"{result.duration_seconds}s"
            )
    source_after = source_integrity_snapshot()
    combined_results = [
        *(baseline_results or []),
        *results,
    ]
    summary = summarize(
        model=model,
        repetitions=repetitions,
        results=combined_results,
        source_unchanged=source_before == source_after,
        started=started,
    )
    summary["execution"] = {
        "selected_scenarios": [
            scenario.scenario_id for scenario in scenarios
        ],
        "new_run_count": len(results),
        "baseline_source": baseline_source,
        "baseline_run_count": len(baseline_results or []),
    }
    write_json(output_dir / "summary.json", summary)
    (output_dir / "REPORT.md").write_text(
        render_report(summary),
        encoding="utf-8",
        newline="\n",
    )
    return summary


def load_valid_baseline_results(
    path: Path,
    *,
    model: str,
    repetitions: int,
) -> list[RepetitionResult]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("model") != model:
        raise ValueError(
            "Baseline model differs from the selected benchmark model"
        )
    configuration = payload.get("configuration") or {}
    expected_configuration = {
        "context_tokens": CONTEXT_TOKENS,
        "output_tokens": OUTPUT_TOKENS,
        "temperature": TEMPERATURE,
        "top_p": TOP_P,
        "think": False,
        "seed": SEED,
        "repetitions_per_scenario": repetitions,
    }
    for key, expected in expected_configuration.items():
        if configuration.get(key) != expected:
            raise ValueError(
                f"Baseline configuration mismatch for {key}: "
                f"{configuration.get(key)!r} != {expected!r}"
            )
    if payload.get("source_integrity_unchanged") is not True:
        raise ValueError("Baseline source integrity was not preserved")
    selected = [
        item
        for item in payload.get("results") or []
        if item.get("scenario_id") in VALID_BASELINE_SCENARIO_IDS
    ]
    for scenario_id in VALID_BASELINE_SCENARIO_IDS:
        scenario_results = [
            item for item in selected
            if item.get("scenario_id") == scenario_id
        ]
        if len(scenario_results) != repetitions:
            raise ValueError(
                f"Baseline must contain {repetitions} runs for "
                f"{scenario_id}"
            )
        if any(item.get("status") != "PASS" for item in scenario_results):
            raise ValueError(
                f"Baseline scenario {scenario_id} is not fully valid"
            )
    allowed = {item.name for item in fields(RepetitionResult)}
    return [
        RepetitionResult(**{
            key: value
            for key, value in item.items()
            if key in allowed
        })
        for item in selected
    ]


def persisted_result_satisfies_contract(
    result: RepetitionResult,
) -> bool:
    scenario = next(
        item
        for item in SCENARIOS
        if item.scenario_id == result.scenario_id
    )
    if not scenario.regression_mode:
        return result.tool_sequence == list(
            scenario.required_sequence
        )
    recovery = result.recovery
    return (
        result.tool_sequence[:5]
        == list(scenario.required_sequence[:5])
        and result.tool_sequence[-2:] == ["show_diff", "finish"]
        and recovery.get("validation_state") == "RECOVERED"
        and recovery.get("retest", {}).get("passed") is True
        and recovery.get("materially_distinct_second_change") is True
    )


def summarize(
    *,
    model: str,
    repetitions: int,
    results: list[RepetitionResult],
    source_unchanged: bool,
    started: datetime,
) -> dict[str, Any]:
    total = len(results)
    passed = sum(item.status == "PASS" for item in results)
    responses = sum(item.response_count for item in results)
    structurally_valid = sum(
        item.structurally_valid_responses for item in results
    )
    false_successes = sum(item.false_success for item in results)
    recovery_results = [
        item for item in results
        if item.scenario_id == RECOVERY_SCENARIO_ID
    ]
    recovery_passes = sum(
        item.status == "PASS" for item in recovery_results
    )
    inconclusive_runs = sum(
        item.status == "INCONCLUSIVE" for item in recovery_results
    )
    incomplete_successes = sum(
        item.status == "PASS"
        and not persisted_result_satisfies_contract(item)
        for item in results
    )
    scenario_summaries = {}
    for scenario in SCENARIOS:
        selected = [
            item for item in results
            if item.scenario_id == scenario.scenario_id
        ]
        scenario_summaries[scenario.scenario_id] = {
            "title": scenario.title,
            "passed": sum(item.status == "PASS" for item in selected),
            "failed": sum(item.status == "FAIL" for item in selected),
            "inconclusive": sum(
                item.status == "INCONCLUSIVE" for item in selected
            ),
            "total": len(selected),
            "completion_rate": percentage(
                sum(item.status == "PASS" for item in selected),
                len(selected),
            ),
            "premature_finish": sum(
                item.premature_finish for item in selected
            ),
            "invalid_tools": sum(
                item.invalid_tools for item in selected
            ),
            "repeated_calls": sum(
                item.repeated_calls for item in selected
            ),
            "schema_failures": sum(
                item.schema_failures for item in selected
            ),
            "real_validation_failures": sum(
                item.failed_validations for item in selected
            ),
            "complete_recoveries": sum(
                item.corrections_after_failure for item in selected
            ),
            "average_steps": round(
                sum(item.steps_used for item in selected)
                / max(1, len(selected)),
                2,
            ),
            "average_latency_seconds": round(
                sum(item.duration_seconds for item in selected)
                / max(1, len(selected)),
                3,
            ),
        }
    promotion = {
        "completion_rate_at_least_80": passed / max(1, total) >= 0.8,
        "recovery_at_least_4_of_5": (
            len(recovery_results) == 5
            and recovery_passes >= 4
        ),
        "all_responses_structurally_valid": (
            responses > 0 and structurally_valid == responses
        ),
        "zero_false_successes": false_successes == 0,
        "zero_incomplete_successes": incomplete_successes == 0,
        "zero_finish_accepted_with_failed_validation": all(
            not (
                item.status == "PASS"
                and (
                    not item.recovery.get("retest")
                    or not item.recovery["retest"].get("passed")
                )
            )
            for item in recovery_results
        ),
        "all_real_failures_persisted": (
            len(recovery_results) == 5
            and all(
                item.recovery.get("failure_persisted") is True
                for item in recovery_results
            )
        ),
        "all_successes_have_passing_retest": all(
            item.status != "PASS"
            or (
                item.recovery.get("retest", {}).get("passed") is True
                and any(
                    command.get("exit_code") == 0
                    for command in item.recovery.get(
                        "retest", {}
                    ).get("commands", [])
                )
            )
            for item in recovery_results
        ),
        "zero_inconclusive_runs": inconclusive_runs == 0,
        "outside_fixtures_unchanged": all(
            item.recovery.get("outside_fixture_unchanged") is True
            for item in recovery_results
        ),
        "source_integrity_unchanged": source_unchanged,
    }
    promotion["promoted"] = all(promotion.values())
    decision = (
        "BENCHMARK_INCONCLUSIVE"
        if inconclusive_runs
        else (
            "QWEN_PROMOTED"
            if promotion["promoted"]
            else "QWEN_NOT_PROMOTED"
        )
    )
    return {
        "benchmark": "model_harness_productive_qwen_v1",
        "model": model,
        "configuration": {
            "context_tokens": CONTEXT_TOKENS,
            "output_tokens": OUTPUT_TOKENS,
            "temperature": TEMPERATURE,
            "top_p": TOP_P,
            "think": False,
            "seed": SEED,
            "repetitions_per_scenario": repetitions,
        },
        "started_at": started.isoformat(),
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "missions": {
            "passed": passed,
            "total": total,
            "completion_rate": percentage(passed, total),
        },
        "responses": {
            "structurally_valid": structurally_valid,
            "total": responses,
            "valid_rate": percentage(structurally_valid, responses),
        },
        "metrics": {
            "premature_finish": sum(
                item.premature_finish for item in results
            ),
            "invalid_tools": sum(item.invalid_tools for item in results),
            "repeated_calls": sum(
                item.repeated_calls for item in results
            ),
            "schema_failures": sum(
                item.schema_failures for item in results
            ),
            "validation_runs": sum(
                item.validation_runs for item in results
            ),
            "failed_validations": sum(
                item.failed_validations for item in results
            ),
            "corrections_after_failure": sum(
                item.corrections_after_failure for item in results
            ),
            "recovery_regressions_injected": sum(
                int(item.recovery.get("regression_injection_count") or 0)
                for item in recovery_results
            ),
            "recovery_failures_persisted": sum(
                item.recovery.get("failure_persisted") is True
                for item in recovery_results
            ),
            "recovery_successes_persisted": sum(
                item.recovery.get("recovery_persisted") is True
                for item in recovery_results
            ),
            "inconclusive_runs": inconclusive_runs,
            "false_successes": false_successes,
            "total_steps": sum(item.steps_used for item in results),
            "total_latency_ms": sum(item.latency_ms for item in results),
            "input_tokens": sum(item.input_tokens for item in results),
            "output_tokens": sum(item.output_tokens for item in results),
        },
        "source_integrity_unchanged": source_unchanged,
        "scenarios": scenario_summaries,
        "promotion": promotion,
        "decision": decision,
        "results": [asdict(item) for item in results],
    }


def render_report(summary: Mapping[str, Any]) -> str:
    recovery_results = [
        item
        for item in summary.get("results") or []
        if item.get("scenario_id") == RECOVERY_SCENARIO_ID
    ]
    lines = [
        "# Qwen3.5 9B Productive ModelHarness Benchmark",
        "",
        "## 1. Problema do cenário anterior",
        "",
        (
            "O cenário anterior pedia ao modelo que introduzisse "
            "deliberadamente uma falha sintática. O Qwen aplicou uma solução "
            "válida à primeira tentativa nas cinco execuções."
        ),
        "",
        (
            "O antigo resultado 0/5 é inconclusivo para recuperação: nenhuma "
            "validação realmente falhou, portanto o ciclo de diagnóstico e "
            "reteste nunca foi exercitado."
        ),
        "",
        "## 2. Novo desenho",
        "",
        (
            "A missão é uma alteração normal em `addTask`. Depois da primeira "
            "alteração real do modelo e imediatamente antes da primeira "
            "validação, o controlador altera apenas a cópia temporária de "
            "`src/tasks.js`:"
        ),
        "",
        "- Original: `export function normalizeTask(value) {`",
        "- Regressão: `export function normalizeTask(value {`",
        "",
        (
            "O comando real `node --check src/tasks.js` deve devolver código "
            "diferente de zero. A injeção ocorre uma única vez e os seus "
            "metadados nunca entram no estado apresentado ao modelo."
        ),
        "",
        "## 3. Garantias de isolamento",
        "",
        "- Diretório temporário novo por run.",
        "- Paths resolvidos e confinados à fixture.",
        "- Snapshot SHA-256 do código produtivo antes e depois de cada run.",
        "- Hash independente do ficheiro `README.md` não relacionado.",
        "- Sem rede, dependências ou tools fora da fixture.",
        "- Decisões obtidas pelo ModelHarness e provider Ollama produtivos.",
        "",
        "## 4. Resumo executivo",
        "",
        f"- Modelo: `{summary['model']}`",
        (
            "- Missoes completas: "
            f"{summary['missions']['passed']}/"
            f"{summary['missions']['total']} "
            f"({summary['missions']['completion_rate']}%)"
        ),
        (
            "- Respostas estruturais validas: "
            f"{summary['responses']['structurally_valid']}/"
            f"{summary['responses']['total']} "
            f"({summary['responses']['valid_rate']}%)"
        ),
        (
            "- Integridade do codigo fonte: "
            f"{'inalterada' if summary['source_integrity_unchanged'] else 'ALTERADA'}"
        ),
        (
            "- Promocao: "
            f"{'PASS' if summary['promotion']['promoted'] else 'FAIL'}"
        ),
        f"- Decisão: `{summary['decision']}`",
        (
            "- Baseline válido: `"
            f"{summary.get('execution', {}).get('baseline_source') or 'none'}`"
        ),
        "",
        "## 5. Cinco execuções de recuperação",
        "",
        (
            "| Run | Falha real | Falha persistida | Correção posterior | "
            "Reteste | Resultado |"
        ),
        "|---:|:---:|:---:|:---:|:---:|:---:|",
    ]
    for item in recovery_results:
        recovery = item.get("recovery") or {}
        first_validation = recovery.get("first_validation") or {}
        real_failure = any(
            command.get("exit_code") != 0
            for command in first_validation.get("commands") or []
        )
        second_change = bool(recovery.get("second_change"))
        retest_passed = (
            (recovery.get("retest") or {}).get("passed") is True
        )
        lines.append(
            f"| {item['repetition']} "
            f"| {'Sim' if real_failure else 'Não'} "
            f"| {'Sim' if recovery.get('failure_persisted') else 'Não'} "
            f"| {'Sim' if second_change else 'Não'} "
            f"| {'Passou' if retest_passed else 'Não passou'} "
            f"| {item['status']} |"
        )
    lines.extend([
        "",
        "## 6. Evidência por execução",
        "",
    ])
    for item in recovery_results:
        recovery = item.get("recovery") or {}
        first_validation = recovery.get("first_validation") or {}
        failed_commands = [
            command
            for command in first_validation.get("commands") or []
            if command.get("exit_code") != 0
        ]
        first_failure = failed_commands[0] if failed_commands else {}
        post_failure = recovery.get("post_failure_action") or {}
        retest = recovery.get("retest") or {}
        lines.extend([
            f"### Run {item['repetition']}",
            "",
            f"- Run ID: `{recovery.get('run_id', '')}`",
            f"- Mission ID: `{recovery.get('mission_id', '')}`",
            (
                "- Primeira falha: `"
                f"{first_failure.get('command', 'não observada')}` "
                f"exit `{first_failure.get('exit_code', 'n/a')}`"
            ),
            (
                "- Evidência relevante: "
                f"`{compact_error_output(first_failure)}`"
            ),
            (
                "- Ação posterior: `"
                f"{post_failure.get('tool', 'nenhuma')}`"
            ),
            (
                "- Segunda alteração distinta: "
                f"{bool(recovery.get('materially_distinct_second_change'))}"
            ),
            (
                "- Reteste: "
                f"{'PASS' if retest.get('passed') is True else 'FAIL/ausente'}"
            ),
            f"- Estado final: `{item['status']}`",
            f"- Latência: `{item['latency_ms']} ms`",
            (
                f"- Tokens: entrada `{item['input_tokens']}`, "
                f"saída `{item['output_tokens']}`"
            ),
            "",
        ])
    lines.extend([
        "## 7. Cenários e resultado global recalculado",
        "",
    ])
    for scenario_id, item in summary["scenarios"].items():
        lines.extend([
            f"### {scenario_id} - {item['title']}",
            "",
            (
                f"- Conclusao: {item['passed']}/{item['total']} "
                f"({item['completion_rate']}%)"
            ),
            f"- Finish prematuro: {item['premature_finish']}",
            f"- Tools invalidas: {item['invalid_tools']}",
            f"- Repeticoes: {item['repeated_calls']}",
            f"- Falhas de schema: {item['schema_failures']}",
            f"- Falhas reais de validação: {item['real_validation_failures']}",
            f"- Recuperações completas: {item['complete_recoveries']}",
            f"- Passos medios: {item['average_steps']}",
            f"- Latencia media: {item['average_latency_seconds']}s",
            "",
        ])
    lines.extend([
        "## 8. Métricas globais",
        "",
    ])
    for key, value in summary["metrics"].items():
        lines.append(f"- {key}: {value}")
    lines.extend([
        "",
        "## 9. Comandos de validação executados",
        "",
    ])
    commands = []
    for item in recovery_results:
        for command in item.get("tests_executed") or []:
            display = str(command.get("command") or "")
            if display and display not in commands:
                commands.append(display)
    lines.extend(f"- `{command}`" for command in commands)
    lines.extend([
        "",
        "## 10. Critérios de promoção",
        "",
    ])
    for key, value in summary["promotion"].items():
        lines.append(f"- {key}: {value}")
    lines.extend([
        "",
        "## 11. Limitações restantes",
        "",
        (
            "- Este cenário mede a fronteira stateful do ModelHarness com "
            "tools isoladas; não afirma que a execução atravessou o "
            "MissionExecutor ou a CodingSession produtivos."
        ),
        "- A regressão é específica da fixture JavaScript controlada.",
        "- A amostra contém cinco execuções com parâmetros idênticos.",
        "",
        "## 12. Decisão final",
        "",
        summary["decision"],
        "",
    ])
    return "\n".join(lines)


def source_integrity_snapshot() -> dict[str, str]:
    snapshot = {}
    for area in SOURCE_AREAS:
        root = ROOT / area
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if any(
                part in {
                    "__pycache__",
                    "node_modules",
                    "dist",
                    "build",
                }
                for part in path.parts
            ):
                continue
            snapshot[path.relative_to(ROOT).as_posix()] = sha256_file(path)
    for relative in ("server.py",):
        path = ROOT / relative
        if path.is_file():
            snapshot[relative] = sha256_file(path)
    return snapshot


def snapshot_directory(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): sha256_file(path)
        for path in root.rglob("*")
        if path.is_file()
    }


def collect_references(value: Any) -> set[str]:
    references: set[str] = set()
    if isinstance(value, Mapping):
        for key, item in value.items():
            if key == "reference" and isinstance(item, str) and item:
                references.add(item)
            else:
                references.update(collect_references(item))
    elif isinstance(value, list):
        for item in value:
            references.update(collect_references(item))
    return references


def compact_error_output(command: Mapping[str, Any]) -> str:
    raw = str(command.get("stderr") or command.get("stdout") or "")
    compact = " ".join(raw.split())
    return compact[:300].replace("`", "'") or "sem output"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def append_jsonl(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (
        json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n"
    )
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())


def percentage(value: int, total: int) -> float:
    return round((value / total) * 100, 2) if total else 0.0


def default_output_dir() -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return (
        ROOT
        / "diagnostics"
        / "model_harness_productive_benchmark"
        / f"{stamp}-qwen35-9b"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run isolated productive IDE scenarios through ModelHarness."
        )
    )
    parser.add_argument("--model", default=MODEL)
    parser.add_argument("--repetitions", type=int, default=5)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument(
        "--only",
        choices=[scenario.scenario_id for scenario in SCENARIOS],
        default=None,
    )
    parser.add_argument(
        "--baseline-summary",
        type=Path,
        default=None,
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.repetitions < 1:
        raise ValueError("--repetitions must be positive")
    output_dir = (
        args.output.resolve()
        if args.output is not None
        else default_output_dir()
    )
    selected_scenarios = tuple(
        scenario
        for scenario in SCENARIOS
        if args.only is None or scenario.scenario_id == args.only
    )
    baseline_results: list[RepetitionResult] = []
    baseline_source = ""
    if args.baseline_summary is not None:
        baseline_path = args.baseline_summary.resolve()
        baseline_results = load_valid_baseline_results(
            baseline_path,
            model=args.model,
            repetitions=args.repetitions,
        )
        baseline_source = baseline_path.as_posix()
    if (
        args.only == RECOVERY_SCENARIO_ID
        and not baseline_results
    ):
        raise ValueError(
            "--baseline-summary is required when running only recovery"
        )
    summary = asyncio.run(run_benchmark(
        model=args.model,
        repetitions=args.repetitions,
        output_dir=output_dir,
        scenarios=selected_scenarios,
        baseline_results=baseline_results,
        baseline_source=baseline_source,
    ))
    print(f"OUTPUT={output_dir}")
    print(
        "PROMOTED="
        + ("true" if summary["promotion"]["promoted"] else "false")
    )
    print(f"DECISION={summary['decision']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
