from __future__ import annotations

import asyncio
import hashlib
import json
import os
import statistics
import time
import uuid
from collections import defaultdict
from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from backend.model_harness import (
    CallableModelProvider,
    ContextBuildRequest,
    ContextBuilder,
    ContextCandidate,
    EnumConstraint,
    ExecutionConstraints,
    ExpectedOutput,
    ModelHarness,
    ModelPreferences,
    ModelRequest,
    ModelResponse,
    ModelResponseStatus,
    ModelUsage,
    OutputFormat,
    ProgressCondition,
    ProgressTracker,
    ProviderRegistry,
    ProviderResult,
    RecoveryCoordinator,
    ReferenceConstraint,
)
from backend.model_harness.benchmarking.contracts import (
    BenchmarkConfig,
    BenchmarkMode,
    BenchmarkScenario,
    BenchmarkStep,
    CapabilityResult,
    CapabilityStatus,
    ExpectedTransition,
    ModelDecision,
    ScenarioGroup,
    ScenarioResult,
    ScenarioStatus,
    StatefulContext,
    StepResult,
    StopReason,
    ToolObservation,
    ToolRequest,
    ToolStatus,
    sha256_json,
    to_jsonable,
)
from backend.model_harness.benchmarking.scenarios import (
    BENCHMARK_VERSION,
    benchmark_scenarios,
    fixture_catalog_hash,
)
from backend.model_harness.benchmarking.tools import (
    BenchmarkToolRegistry,
    FixtureSandbox,
    create_read_only_tool_registry,
)
from scripts.model_harness_benchmark import (
    BenchmarkConfig as OllamaConfig,
    OllamaBenchmarkProvider,
    _assert_output_location,
    runtime_after_metadata,
    runtime_metadata,
    sha256_file,
    tree_integrity,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
DECISION_VALUES = ("CALL_TOOL", "FINISH")
STOP_VALUES = ("",) + tuple(item.value for item in StopReason)
CRITICAL_FILES = (
    "agents/orchestrator/project_builder.py",
    "agents/mission_state.py",
    "agents/mission_executor.py",
    "agents/mission_autonomy.py",
    "agents/executors/registry.py",
    "intelligence/coding_session.py",
    "server.py",
)
INTEGRITY_TREES = {
    "workspace_projects": "workspace/projects",
    "mission_metadata": "workspace/.jarvis",
    "chroma_collections": "chroma_db",
    "frontend_source": "frontend/src",
}


def decision_schema(allowed_tools: tuple[str, ...]) -> dict[str, Any]:
    return {
        "type": "object",
        "required": [
            "decision",
            "tool_name",
            "arguments",
            "conclusion",
            "stop_reason",
            "evidence_refs",
            "retained_constraint_ids",
            "plan",
        ],
        "properties": {
            "decision": {"type": "string", "enum": list(DECISION_VALUES)},
            "tool_name": {
                "type": "string",
                "enum": list(allowed_tools),
            },
            "arguments": {"type": "object"},
            "conclusion": {"type": "string"},
            "stop_reason": {
                "type": "string",
                "enum": list(STOP_VALUES),
            },
            "evidence_refs": {
                "type": "array",
                "items": {"type": "string"},
                "uniqueItems": True,
            },
            "retained_constraint_ids": {
                "type": "array",
                "items": {"type": "string"},
                "uniqueItems": True,
            },
            "plan": {
                "type": "array",
                "maxItems": 5,
                "items": {
                    "type": "object",
                    "required": [
                        "step",
                        "required_evidence",
                        "dependencies",
                        "completion_condition",
                        "negative_constraints",
                    ],
                    "properties": {
                        "step": {"type": "string", "minLength": 1},
                        "required_evidence": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "dependencies": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "completion_condition": {
                            "type": "string",
                            "minLength": 1,
                        },
                        "negative_constraints": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                    "additionalProperties": False,
                },
            },
        },
        "additionalProperties": False,
    }


def build_step_context(
    scenario: BenchmarkScenario,
    state: StatefulContext,
    registry: BenchmarkToolRegistry,
    *,
    max_chars: int,
) -> tuple[Any, str]:
    tool_contracts = [
        item.public_contract()
        for item in registry.definitions(scenario.available_tools)
    ]
    candidates: list[ContextCandidate] = [
        ContextCandidate(
            source=f"scenario:{scenario.scenario_id}:objective",
            kind="objective",
            content=scenario.objective,
            relevance_score=1.0,
            explicitly_requested=True,
            metadata={"priority": 100, "reason": "current_objective"},
        ),
        ContextCandidate(
            source=f"scenario:{scenario.scenario_id}:tools",
            kind="tools",
            content=json.dumps(
                tool_contracts,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ),
            relevance_score=0.95,
            explicitly_requested=True,
            metadata={"priority": 95, "reason": "allowed_tools"},
        ),
    ]
    for constraint in scenario.constraints:
        candidates.append(ContextCandidate(
            source=(
                f"scenario:{scenario.scenario_id}:constraint:"
                f"{constraint.constraint_id}"
            ),
            kind="constraint",
            content=f"{constraint.constraint_id}: {constraint.text}",
            relevance_score=1.0,
            explicitly_requested=True,
            metadata={"priority": 100, "reason": "active_constraint"},
        ))
    unique_observations: dict[str, ToolObservation] = {}
    for observation in state.observations:
        unique_observations[observation.result_sha256] = observation
    for index, observation in enumerate(
        reversed(tuple(unique_observations.values()))
    ):
        candidates.append(ContextCandidate(
            source=(
                f"observation:{observation.tool_name}:"
                f"{observation.result_sha256[:16]}"
            ),
            kind="evidence",
            content=observation.raw_context,
            relevance_score=max(0.5, 0.9 - index * 0.03),
            explicitly_requested=index < 2,
            metadata={
                "priority": max(50, 90 - index),
                "reason": "normalized_tool_observation",
                "result_sha256": observation.result_sha256,
            },
        ))
    if state.decisions:
        previous = [
            {
                "step": index + 1,
                "decision": item.decision,
                "tool_name": item.tool_name,
                "evidence_refs": list(item.evidence_refs),
            }
            for index, item in enumerate(state.decisions[-3:])
        ]
        candidates.append(ContextCandidate(
            source=f"scenario:{scenario.scenario_id}:recent-decisions",
            kind="decision",
            content=json.dumps(
                previous,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ),
            relevance_score=0.8,
            explicitly_requested=False,
            metadata={
                "priority": 60,
                "reason": "minimal_transition_history",
            },
        ))
    context = ContextBuilder().build(ContextBuildRequest(
        task_summary=scenario.objective,
        candidates=tuple(candidates),
        allowed_kinds=(
            "objective",
            "constraint",
            "tools",
            "evidence",
            "decision",
        ),
        max_items=32,
        max_chars=max_chars,
    ))
    context_hash = sha256_json({
        "items": [
            {
                "source": item.source,
                "kind": item.kind,
                "hash": item.content_sha256,
                "reason": item.inclusion_reason,
            }
            for item in context.items
        ],
        "decisions": [
            {
                "source": item.source,
                "included": item.included,
                "reason": item.reason,
                "hash": item.content_sha256,
            }
            for item in context.decisions
        ],
    })
    return context, context_hash


def build_step_prompt(
    scenario: BenchmarkScenario,
    state: StatefulContext,
    step_number: int,
) -> tuple[str, str]:
    required_remaining = [
        name
        for name in scenario.required_tools
        if name not in [item.tool_name for item in state.decisions]
    ]
    known_references = sorted(state.known_references)
    system_prompt = (
        "You control a deterministic read-only benchmark. Return exactly one "
        "JSON object matching the supplied schema. Never execute a tool: you "
        "only select one tool and arguments. Use CALL_TOOL for evidence tools. "
        "Use FINISH with tool_name=finish only after sufficient evidence. For "
        "FINISH, arguments must contain the same conclusion and stop_reason as "
        "the top-level fields. On non-finish steps conclusion and stop_reason "
        "must be empty and plan must be empty. Cite only KNOWN_REFERENCES. "
        "retained_constraint_ids must contain every active constraint ID on "
        "every step. Do not repeat a tool with identical arguments unless new "
        "evidence makes repetition necessary. A short plan, when requested, "
        "must have 3-5 necessary ordered steps and every step must declare "
        "required_evidence, dependencies, completion_condition, and "
        "negative_constraints."
    )
    user_prompt = json.dumps(
        {
            "scenario_id": scenario.scenario_id,
            "step": step_number,
            "objective": scenario.objective,
            "active_constraints": [
                {
                    "id": item.constraint_id,
                    "text": item.text,
                }
                for item in scenario.constraints
            ],
            "available_tools": list(scenario.available_tools),
            "tools_already_called": [
                item.tool_name for item in state.decisions
            ],
            "required_tools_before_finish": list(
                scenario.required_tools
            ),
            "required_tools_remaining": required_remaining,
            "known_references": known_references,
            "minimum_evidence_references": scenario.minimum_evidence,
            "expected_supported_stop": (
                scenario.expected_stop_reason.value
            ),
            "planning_required": scenario.evaluator == "short_plan",
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return system_prompt, user_prompt


def stateful_recovery_transformer(
    request: ModelRequest,
    response: ModelResponse,
    decision: Any,
) -> ModelRequest:
    issue = (
        response.validation.issues[0]
        if response.validation.issues
        else None
    )
    code = issue.code if issue is not None else decision.reason
    correction = (
        "\nVALIDATION_CORRECTION: The previous decision failed "
        f"{code}. Return a new complete JSON decision satisfying the same "
        "objective, constraints and schema. Do not repeat the invalid output."
    )
    return replace(
        request,
        user_prompt=request.user_prompt + correction,
        request_id=uuid.uuid4().hex,
    )


class StatefulBenchmarkRunner:
    def __init__(
        self,
        config: BenchmarkConfig,
        *,
        registry: BenchmarkToolRegistry | None = None,
        live_provider: Any | None = None,
    ):
        self.config = config
        self.registry = registry or create_read_only_tool_registry()
        self.output_dir = Path(config.output_dir)
        _assert_output_location(self.output_dir)
        self.ollama_config = OllamaConfig(
            model=config.model,
            base_url=config.base_url,
            context_tokens=config.context_tokens,
            output_tokens=config.max_output_tokens,
            temperature=config.temperature,
            top_p=config.top_p,
            seed=config.seed,
            think=config.think,
            stream=config.stream,
            repetitions=config.repetitions,
            keep_alive=config.keep_alive,
            timeout_seconds=config.timeout_seconds,
            # Benchmark-only isolation; production calls may be concurrent.
            recycle_loaded_model_before_first_request=True,
        )
        self.live_provider = (
            live_provider
            if live_provider is not None
            else OllamaBenchmarkProvider(self.ollama_config)
        )
        self.harness = ModelHarness(
            ProviderRegistry([self.live_provider]),
            recovery=RecoveryCoordinator(
                transformer=stateful_recovery_transformer
            ),
        )
        self.step_results: list[StepResult] = []
        self.scenario_results: list[ScenarioResult] = []
        self.fault_results: list[dict[str, Any]] = []
        self.telemetry_records: list[dict[str, Any]] = []
        self._infrastructure_errors: list[str] = []

    async def run(self) -> dict[str, Any]:
        if self.output_dir.exists():
            raise FileExistsError(
                f"Benchmark output already exists: {self.output_dir}"
            )
        self.output_dir.mkdir(parents=True)
        started_at = utc_now()
        before = integrity_snapshot()
        scenarios = benchmark_scenarios(
            self.config.mode,
            include_fault_injection=self.config.fault_injection,
            seed=self.config.seed,
        )
        runtime_before = await runtime_metadata(self.ollama_config)
        manifest = self._manifest(
            started_at,
            scenarios,
            runtime_before,
            before,
        )
        write_json(self.output_dir / "manifest.json", manifest)

        for scenario in scenarios:
            repetitions = repetitions_for(
                self.config.mode,
                self.config.repetitions,
            )
            for repetition in range(1, repetitions + 1):
                try:
                    if scenario.fault_injection:
                        result, steps, fault = await self._run_fault_scenario(
                            scenario,
                            repetition,
                        )
                        self.fault_results.append(fault)
                    else:
                        result, steps = await self._run_live_scenario(
                            scenario,
                            repetition,
                        )
                    self.scenario_results.append(result)
                    self.step_results.extend(steps)
                except Exception as exc:
                    self._infrastructure_errors.append(
                        f"{scenario.scenario_id}/rep-{repetition}: "
                        f"{type(exc).__name__}: {exc}"
                    )
                    self.scenario_results.append(ScenarioResult(
                        scenario_id=scenario.scenario_id,
                        repetition=repetition,
                        group=scenario.group.value,
                        capability=scenario.capability,
                        status=ScenarioStatus.INVALID,
                        stop_reason=StopReason.VALIDATION_FAILED,
                        step_count=0,
                        final_conclusion="",
                        evidence_refs=(),
                        tools_called=(),
                        retained_constraints=(),
                        plan_steps=0,
                        criteria=({
                            "criterion": "infrastructure_execution",
                            "passed": False,
                            "evidence": (
                                f"{type(exc).__name__}: {exc}"
                            ),
                        },),
                        total_latency_ms=0,
                        input_tokens=0,
                        output_tokens=0,
                        response_hashes=(),
                        context_range_chars=(0, 0),
                        recovery_used=False,
                        errors=(f"{type(exc).__name__}: {exc}",),
                    ))

        runtime_after = await runtime_after_metadata(self.ollama_config)
        after = integrity_snapshot()
        integrity = {
            "before": before,
            "after": after,
            "unchanged": before == after,
            "integrity_failed": before != after,
        }
        write_json(self.output_dir / "integrity.json", integrity)
        profiles = build_capability_profile(
            self.scenario_results,
            self.step_results,
            self.config,
        )
        summary = build_summary(
            self.config,
            scenarios,
            self.scenario_results,
            self.step_results,
            profiles,
            integrity,
            runtime_before,
            runtime_after,
            self._infrastructure_errors,
            started_at,
        )
        write_json(
            self.output_dir / "scenario_results.json",
            [to_jsonable(item) for item in self.scenario_results],
        )
        write_json(
            self.output_dir / "capability_profile.json",
            {
                "benchmark_version": BENCHMARK_VERSION,
                "configuration_hash": self.config.configuration_hash,
                "capabilities": [to_jsonable(item) for item in profiles],
            },
        )
        write_json(self.output_dir / "summary.json", summary)
        write_json_lines(
            self.output_dir / "step_trace.jsonl",
            [to_jsonable(item) for item in self.step_results],
        )
        write_json_lines(
            self.output_dir / "telemetry.jsonl",
            self.telemetry_records,
        )
        if self.config.fault_injection:
            write_json(
                self.output_dir / "fault_injection_report.json",
                {
                    "benchmark_version": BENCHMARK_VERSION,
                    "cases": self.fault_results,
                    "all_passed": all(
                        item["passed"] for item in self.fault_results
                    ),
                },
            )
        (self.output_dir / "REPORT.md").write_text(
            render_report(summary, profiles),
            encoding="utf-8",
            newline="\n",
        )
        return summary

    async def _run_live_scenario(
        self,
        scenario: BenchmarkScenario,
        repetition: int,
    ) -> tuple[ScenarioResult, list[StepResult]]:
        state = StatefulContext(
            objective=scenario.objective,
            constraints=scenario.constraints,
        )
        tracker = ProgressTracker()
        steps: list[StepResult] = []
        tools_called: list[str] = []
        stop_reason = StopReason.MAX_STEPS_REACHED
        final_decision: ModelDecision | None = None
        errors: list[str] = []
        max_steps = min(scenario.max_steps, self.config.max_steps)
        context_limit = max(
            self.config.context_tokens,
            (
                scenario.context_target_tokens + 4_096
                if scenario.context_target_tokens
                else self.config.context_tokens
            ),
        )
        context_chars_limit = context_limit * 8

        with FixtureSandbox(scenario.fixture) as sandbox:
            for step_number in range(1, max_steps + 1):
                benchmark_step = BenchmarkStep(
                    scenario_id=scenario.scenario_id,
                    step_number=step_number,
                    objective=scenario.objective,
                    constraints=scenario.constraints,
                    available_tools=scenario.available_tools,
                    transition=ExpectedTransition(
                        allowed_tools=scenario.available_tools,
                        allow_finish=(
                            len(state.known_references)
                            >= scenario.minimum_evidence
                        ),
                        minimum_evidence=scenario.minimum_evidence,
                    ),
                )
                context, context_hash = build_step_context(
                    scenario,
                    state,
                    self.registry,
                    max_chars=context_chars_limit,
                )
                state.context_hashes.append(context_hash)
                system_prompt, user_prompt = build_step_prompt(
                    scenario,
                    state,
                    step_number,
                )
                schema = decision_schema(scenario.available_tools)
                expected = ExpectedOutput(
                    format=OutputFormat.JSON_SCHEMA,
                    schema=schema,
                    enum_constraints=(
                        EnumConstraint(
                            "$.decision",
                            DECISION_VALUES,
                        ),
                        EnumConstraint(
                            "$.tool_name",
                            scenario.available_tools,
                        ),
                        EnumConstraint("$.stop_reason", STOP_VALUES),
                    ),
                    reference_constraints=(
                        ReferenceConstraint(
                            "$.evidence_refs",
                            tuple(sorted(state.known_references)),
                            allow_empty=True,
                        ),
                    ),
                )
                request = ModelRequest(
                    task_profile="TOOL_SELECTION",
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    context=context,
                    allowed_tools=scenario.available_tools,
                    expected_output=expected,
                    temperature=self.config.temperature,
                    max_context_tokens=context_limit,
                    max_output_tokens=self.config.max_output_tokens,
                    metadata={
                        "benchmark_version": BENCHMARK_VERSION,
                        "consumer": "stateful_benchmark",
                        "scenario": scenario.scenario_id,
                        "step": step_number,
                        "repetition": repetition,
                        "progress_key": (
                            f"{scenario.scenario_id}:{repetition}"
                        ),
                    },
                    model_preferences=ModelPreferences(
                        providers=("ollama",),
                        models=(self.config.model,),
                    ),
                    execution_constraints=ExecutionConstraints(
                        max_attempts=2,
                        timeout_seconds=self.config.timeout_seconds,
                        streaming=False,
                        thinking=False,
                        allow_recovery=True,
                        stop_on_no_progress=True,
                    ),
                )
                if self.config.debug_prompts:
                    self._write_debug_prompt(
                        scenario,
                        repetition,
                        step_number,
                        request,
                    )
                tracker.record_input(request.fingerprint())
                response = await self.harness.execute(request)
                tracker.record_output(response.raw_text)
                decision: ModelDecision | None = None
                semantic_issues: list[str] = []
                removed_context = important_context_removed(context)
                if removed_context:
                    semantic_issues.append(
                        "Important context was removed: "
                        + ", ".join(removed_context)
                    )
                if response.status == ModelResponseStatus.SUCCEEDED:
                    try:
                        decision = ModelDecision.from_mapping(
                            response.structured_output
                        )
                    except (TypeError, ValueError) as exc:
                        semantic_issues.append(str(exc))
                else:
                    semantic_issues.append(
                        f"model_response_status={response.status.value}"
                    )
                    semantic_issues.extend(
                        "provider_error="
                        + str(item.get("type") or "unknown")
                        for item in response.errors
                    )
                if decision is not None:
                    semantic_issues.extend(
                        validate_transition(
                            benchmark_step,
                            scenario,
                            state,
                            decision,
                        )
                    )
                progress = tracker.snapshot()
                observation: ToolObservation | None = None
                selected_tool = decision.tool_name if decision else ""
                tool_arguments = (
                    dict(decision.arguments) if decision else {}
                )
                if response.status == ModelResponseStatus.PROVIDER_FAILED:
                    stop_reason = StopReason.RECOVERY_EXHAUSTED
                elif response.status == ModelResponseStatus.STOPPED:
                    stop_reason = _progress_stop_reason(progress.conditions)
                    semantic_issues.append(
                        "ModelHarness progress guard stopped the request."
                    )
                elif semantic_issues:
                    stop_reason = (
                        StopReason.RECOVERY_EXHAUSTED
                        if _recovery_was_attempted(response)
                        else StopReason.VALIDATION_FAILED
                    )
                elif decision is not None:
                    if not _constraints_retained(scenario, decision):
                        stop_reason = StopReason.CONSTRAINT_VIOLATION
                        semantic_issues.append(
                            "Active constraint IDs were not retained."
                        )
                    elif _decision_violates_forbidden_paths(
                        scenario,
                        decision,
                    ):
                        stop_reason = StopReason.CONSTRAINT_VIOLATION
                        semantic_issues.append(
                            "A negative path constraint was violated."
                        )
                    else:
                        tracker.record_tool_call(
                            decision.tool_name,
                            decision.arguments,
                        )
                        progress = tracker.snapshot()
                        if ProgressCondition.REPEATED_TOOL_CALLS in (
                            progress.conditions
                        ):
                            stop_reason = StopReason.REPEATED_TOOL_CALL
                            semantic_issues.append(
                                "Identical tool call repeated without evidence."
                            )
                        else:
                            observation = self.registry.execute(
                                sandbox,
                                ToolRequest(
                                    scenario_id=scenario.scenario_id,
                                    step_number=step_number,
                                    name=decision.tool_name,
                                    arguments=decision.arguments,
                                ),
                            )
                            tools_called.append(decision.tool_name)
                            state.decisions.append(decision)
                            if decision.decision == "FINISH":
                                final_decision = decision
                                stop_reason = _parse_stop_reason(
                                    decision.stop_reason
                                )
                            elif observation.status in {
                                ToolStatus.BLOCKED,
                                ToolStatus.FAILED,
                                ToolStatus.TIMED_OUT,
                            }:
                                stop_reason = StopReason.TOOL_FAILED
                                semantic_issues.append(
                                    observation.error_code
                                    or observation.summary
                                )
                            else:
                                is_new = state.add_observation(observation)
                                if not is_new:
                                    tracker.record_action(
                                        "observation",
                                        "NO_NEW_EVIDENCE",
                                    )
                                if state.no_new_evidence_steps >= 2:
                                    stop_reason = StopReason.NO_PROGRESS
                                    semantic_issues.append(
                                        "Context grew without new evidence."
                                    )
                if semantic_issues:
                    errors.extend(semantic_issues)
                step_result = self._step_result(
                    scenario,
                    repetition,
                    step_number,
                    request,
                    response,
                    decision,
                    observation,
                    context,
                    context_hash,
                    progress,
                    stop_reason if (
                        semantic_issues
                        or final_decision is not None
                    ) else None,
                    semantic_issues,
                )
                steps.append(step_result)
                self.telemetry_records.append(
                    self._step_telemetry(step_result, response)
                )
                if (
                    semantic_issues
                    or final_decision is not None
                    or stop_reason in {
                        StopReason.NO_PROGRESS,
                        StopReason.REPEATED_TOOL_CALL,
                        StopReason.TOOL_FAILED,
                    }
                ):
                    break

        criteria = evaluate_scenario(
            scenario,
            state,
            final_decision,
            tools_called,
            stop_reason,
            steps,
        )
        status = classify_scenario(criteria, scenario)
        context_values = [item.context_chars for item in steps] or [0]
        return ScenarioResult(
            scenario_id=scenario.scenario_id,
            repetition=repetition,
            group=scenario.group.value,
            capability=scenario.capability,
            status=status,
            stop_reason=stop_reason,
            step_count=len(steps),
            final_conclusion=(
                final_decision.conclusion if final_decision else ""
            ),
            evidence_refs=(
                final_decision.evidence_refs if final_decision else ()
            ),
            tools_called=tuple(tools_called),
            retained_constraints=(
                final_decision.retained_constraint_ids
                if final_decision
                else ()
            ),
            plan_steps=(
                len(final_decision.plan) if final_decision else 0
            ),
            criteria=tuple(criteria),
            total_latency_ms=sum(item.latency_ms for item in steps),
            input_tokens=sum(item.input_tokens or 0 for item in steps),
            output_tokens=sum(item.output_tokens or 0 for item in steps),
            response_hashes=tuple(
                item.model_output_hash for item in steps
            ),
            context_range_chars=(
                min(context_values),
                max(context_values),
            ),
            recovery_used=any(
                any(
                    record.get("retry_requested")
                    for record in item.recovery_result
                )
                for item in steps
            ),
            errors=tuple(errors),
        ), steps

    async def _run_fault_scenario(
        self,
        scenario: BenchmarkScenario,
        repetition: int,
    ) -> tuple[ScenarioResult, list[StepResult], dict[str, Any]]:
        fault = scenario.fault_injection
        if fault in {
            "invalid_enum",
            "truncated_json",
            "missing_tool_argument",
            "unknown_reference",
        }:
            return await self._run_harness_fault(
                scenario,
                repetition,
            )
        return self._run_tool_fault(scenario, repetition)

    async def _run_harness_fault(
        self,
        scenario: BenchmarkScenario,
        repetition: int,
    ) -> tuple[ScenarioResult, list[StepResult], dict[str, Any]]:
        fault = scenario.fault_injection
        invalid, valid, expected = _fault_payloads(fault)
        calls: list[str] = []

        async def callback(
            request: ModelRequest,
            _route: Any,
            _progress: Any,
        ) -> ProviderResult:
            calls.append(request.fingerprint())
            return ProviderResult(
                raw_text=invalid if len(calls) == 1 else valid,
                usage=ModelUsage(
                    input_tokens=10,
                    output_tokens=10,
                    total_tokens=20,
                ),
            )

        harness = ModelHarness(
            ProviderRegistry([
                CallableModelProvider(
                    "fault",
                    "deterministic-fault-provider",
                    callback,
                )
            ]),
            recovery=RecoveryCoordinator(
                transformer=stateful_recovery_transformer
            ),
        )
        request = ModelRequest(
            task_profile="STRUCTURED_EXTRACTION",
            system_prompt="Return valid benchmark JSON.",
            user_prompt=f"Fault injection: {fault}.",
            expected_output=expected,
            temperature=0.0,
            metadata={
                "benchmark_version": BENCHMARK_VERSION,
                "scenario": scenario.scenario_id,
                "progress_key": (
                    f"fault:{scenario.scenario_id}:{repetition}"
                ),
            },
            model_preferences=ModelPreferences(
                providers=("fault",),
                models=("deterministic-fault-provider",),
            ),
            execution_constraints=ExecutionConstraints(
                max_attempts=2,
                allow_recovery=True,
                stop_on_no_progress=True,
            ),
        )
        response = await harness.execute(request)
        passed = (
            response.status == ModelResponseStatus.SUCCEEDED
            and len(calls) == 2
            and len(set(calls)) == 2
            and any(
                record.retry_requested for record in response.recovery
            )
            and any(
                record.input_changed for record in response.recovery
            )
        )
        stop = (
            StopReason.COMPLETED
            if passed
            else StopReason.RECOVERY_EXHAUSTED
        )
        progress = ProgressTracker()
        progress.record_input(calls[0] if calls else "missing")
        if len(calls) > 1:
            progress.record_input(calls[1])
        step = StepResult(
            scenario_id=scenario.scenario_id,
            repetition=repetition,
            step_number=1,
            objective=scenario.objective,
            current_constraints=tuple(
                item.constraint_id for item in scenario.constraints
            ),
            available_tools=scenario.available_tools,
            selected_tool="fault_provider",
            tool_arguments={"fault": fault},
            normalized_observation=None,
            model_output_hash=hashlib.sha256(
                response.raw_text.encode("utf-8")
            ).hexdigest(),
            context_hash=sha256_json({"fault": fault}),
            context_chars=0,
            context_items=0,
            context_decisions=(),
            validation_result=response.validation.to_dict(),
            progress_result=progress.snapshot().to_dict(),
            recovery_result=tuple(
                record.to_dict() for record in response.recovery
            ),
            stop_reason=stop.value,
            latency_ms=response.latency_ms,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            tokens_per_second=None,
            request_fingerprint=request.fingerprint(),
        )
        criteria = ({
            "criterion": "recovery_transformer_changed_input",
            "passed": passed,
            "evidence": (
                f"calls={len(calls)}, unique_fingerprints={len(set(calls))}, "
                f"status={response.status.value}"
            ),
        },)
        result = ScenarioResult(
            scenario_id=scenario.scenario_id,
            repetition=repetition,
            group=scenario.group.value,
            capability=scenario.capability,
            status=(
                ScenarioStatus.PASS if passed else ScenarioStatus.FAIL
            ),
            stop_reason=stop,
            step_count=1,
            final_conclusion="",
            evidence_refs=(),
            tools_called=(),
            retained_constraints=(),
            plan_steps=0,
            criteria=criteria,
            total_latency_ms=response.latency_ms,
            input_tokens=response.usage.input_tokens or 0,
            output_tokens=response.usage.output_tokens or 0,
            response_hashes=(step.model_output_hash,),
            context_range_chars=(0, 0),
            recovery_used=True,
            errors=(() if passed else ("Recovery contract failed.",)),
        )
        fault_report = {
            "scenario_id": scenario.scenario_id,
            "fault": fault,
            "provider": "deterministic-fault-provider",
            "model_benchmark": False,
            "harness_benchmark": True,
            "expected_stop_reason": scenario.expected_stop_reason.value,
            "actual_stop_reason": stop.value,
            "calls": len(calls),
            "unique_request_fingerprints": len(set(calls)),
            "identical_retry": (
                len(calls) > 1 and len(set(calls)) != len(calls)
            ),
            "recovery": [
                record.to_dict() for record in response.recovery
            ],
            "passed": passed,
        }
        self.telemetry_records.append({
            "provider": "fault",
            "model": "deterministic-fault-provider",
            "profile": "STRUCTURED_EXTRACTION",
            "scenario": scenario.scenario_id,
            "step": 1,
            "latency_ms": response.latency_ms,
            "prompt_tokens": response.usage.input_tokens,
            "completion_tokens": response.usage.output_tokens,
            "tokens_per_second": None,
            "validation": response.validation.status.value,
            "recovery": [
                record.action.value for record in response.recovery
            ],
            "progress": progress.snapshot().to_dict(),
            "selected_tool": "",
            "tool_result_hash": "",
            "context_hash": step.context_hash,
            "stop_reason": stop.value,
        })
        return result, [step], fault_report

    def _run_tool_fault(
        self,
        scenario: BenchmarkScenario,
        repetition: int,
    ) -> tuple[ScenarioResult, list[StepResult], dict[str, Any]]:
        fault = scenario.fault_injection
        tracker = ProgressTracker()
        observations: list[ToolObservation] = []
        calls: list[ToolRequest] = []
        with FixtureSandbox(scenario.fixture) as sandbox:
            if fault == "empty_tool_result":
                request = ToolRequest(
                    scenario.scenario_id,
                    1,
                    "read_file",
                    {"path": "facts.txt"},
                )
                calls.append(request)
                tracker.record_tool_call(request.name, request.arguments)
                observation = self.registry.execute(
                    sandbox,
                    request,
                    injected_fault="empty",
                )
                observations.append(observation)
                stop = StopReason.NEEDS_MORE_EVIDENCE
                passed = observation.status == ToolStatus.EMPTY
            elif fault == "tool_timeout":
                request = ToolRequest(
                    scenario.scenario_id,
                    1,
                    "read_file",
                    {"path": "facts.txt"},
                )
                calls.append(request)
                tracker.record_tool_call(request.name, request.arguments)
                observation = self.registry.execute(
                    sandbox,
                    request,
                    injected_fault="timeout",
                )
                observations.append(observation)
                stop = StopReason.TOOL_FAILED
                passed = observation.status == ToolStatus.TIMED_OUT
            elif fault == "repeated_tool_call":
                request = ToolRequest(
                    scenario.scenario_id,
                    1,
                    "read_file",
                    {"path": "facts.txt"},
                )
                calls.extend((request, replace(request, step_number=2)))
                tracker.record_tool_call(request.name, request.arguments)
                snapshot = tracker.record_tool_call(
                    request.name,
                    request.arguments,
                )
                stop = StopReason.REPEATED_TOOL_CALL
                passed = (
                    ProgressCondition.REPEATED_TOOL_CALLS
                    in snapshot.conditions
                )
            else:
                first = ToolObservation(
                    tool_name="query_fixture_index",
                    status=ToolStatus.SUCCEEDED,
                    result={"value_hash": sha256_json("READY")},
                    references=("fixture:status",),
                    result_sha256=sha256_json({"status": "READY"}),
                    summary="Status is READY.",
                    raw_context='{"status":"READY"}',
                )
                second = ToolObservation(
                    tool_name="query_fixture_index",
                    status=ToolStatus.SUCCEEDED,
                    result={"value_hash": sha256_json("BLOCKED")},
                    references=("fixture:status",),
                    result_sha256=sha256_json({"status": "BLOCKED"}),
                    summary="Status is BLOCKED.",
                    raw_context='{"status":"BLOCKED"}',
                )
                observations.extend((first, second))
                tracker.record_action("fixture:status", "READY")
                tracker.record_action("fixture:status", "BLOCKED")
                stop = StopReason.UNSUPPORTED_CONCLUSION
                passed = first.result_sha256 != second.result_sha256
        expected = scenario.expected_stop_reason
        passed = passed and stop == expected
        observation = observations[-1] if observations else None
        snapshot = tracker.snapshot()
        step = StepResult(
            scenario_id=scenario.scenario_id,
            repetition=repetition,
            step_number=max(1, len(calls)),
            objective=scenario.objective,
            current_constraints=tuple(
                item.constraint_id for item in scenario.constraints
            ),
            available_tools=scenario.available_tools,
            selected_tool=(calls[-1].name if calls else "synthetic_observation"),
            tool_arguments=(
                dict(calls[-1].arguments) if calls else {}
            ),
            normalized_observation=(
                observation.report_view() if observation else None
            ),
            model_output_hash=sha256_json({
                "fault": fault,
                "calls": [
                    {"name": item.name, "arguments": dict(item.arguments)}
                    for item in calls
                ],
            }),
            context_hash=sha256_json({
                "observations": [
                    item.result_sha256 for item in observations
                ]
            }),
            context_chars=0,
            context_items=len(observations),
            context_decisions=(),
            validation_result={
                "status": "FAULT_INJECTION",
                "issues": [],
            },
            progress_result=snapshot.to_dict(),
            recovery_result=(),
            stop_reason=stop.value,
            latency_ms=0,
            input_tokens=0,
            output_tokens=0,
            tokens_per_second=None,
            request_fingerprint=sha256_json({
                "scenario": scenario.scenario_id,
                "repetition": repetition,
            }),
            tool_result_hash=(
                observation.result_sha256 if observation else ""
            ),
        )
        criteria = ({
            "criterion": "deterministic_fault_stop",
            "passed": passed,
            "evidence": (
                f"fault={fault}, expected={expected.value}, actual={stop.value}"
            ),
        },)
        result = ScenarioResult(
            scenario_id=scenario.scenario_id,
            repetition=repetition,
            group=scenario.group.value,
            capability=scenario.capability,
            status=(
                ScenarioStatus.PASS if passed else ScenarioStatus.FAIL
            ),
            stop_reason=stop,
            step_count=max(1, len(calls)),
            final_conclusion="",
            evidence_refs=tuple(
                ref for item in observations for ref in item.references
            ),
            tools_called=tuple(item.name for item in calls),
            retained_constraints=(),
            plan_steps=0,
            criteria=criteria,
            total_latency_ms=0,
            input_tokens=0,
            output_tokens=0,
            response_hashes=(step.model_output_hash,),
            context_range_chars=(0, 0),
            recovery_used=False,
            errors=(() if passed else ("Fault stop mismatch.",)),
        )
        report = {
            "scenario_id": scenario.scenario_id,
            "fault": fault,
            "provider": "deterministic-tool-fixture",
            "model_benchmark": False,
            "harness_benchmark": True,
            "expected_stop_reason": expected.value,
            "actual_stop_reason": stop.value,
            "calls": len(calls),
            "unique_request_fingerprints": len({
                sha256_json({
                    "name": item.name,
                    "arguments": dict(item.arguments),
                })
                for item in calls
            }),
            "identical_retry": False,
            "recovery": [],
            "progress": snapshot.to_dict(),
            "passed": passed,
        }
        self.telemetry_records.append({
            "provider": "deterministic-tool-fixture",
            "model": "",
            "profile": "FAULT_INJECTION",
            "scenario": scenario.scenario_id,
            "step": step.step_number,
            "latency_ms": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "tokens_per_second": None,
            "validation": "FAULT_INJECTION",
            "recovery": [],
            "progress": snapshot.to_dict(),
            "selected_tool": step.selected_tool,
            "tool_result_hash": step.tool_result_hash,
            "context_hash": step.context_hash,
            "stop_reason": stop.value,
        })
        return result, [step], report

    def _step_result(
        self,
        scenario: BenchmarkScenario,
        repetition: int,
        step_number: int,
        request: ModelRequest,
        response: ModelResponse,
        decision: ModelDecision | None,
        observation: ToolObservation | None,
        context: Any,
        context_hash: str,
        progress: Any,
        stop_reason: StopReason | None,
        semantic_issues: list[str],
    ) -> StepResult:
        envelope = getattr(
            self.live_provider,
            "envelopes",
            {},
        ).get(response.request_id, {})
        tokens_per_second = provider_tokens_per_second(envelope)
        validation = response.validation.to_dict()
        if response.errors:
            validation = dict(validation)
            validation["provider_errors"] = (
                sanitized_provider_errors(response.errors)
            )
        if semantic_issues:
            validation = dict(validation)
            validation["benchmark_semantic_issues"] = list(
                semantic_issues
            )
        priorities = {
            item.source: item.metadata.get("priority")
            for item in context.items
        }
        context_decisions = tuple({
            "source": item.source,
            "included": item.included,
            "reason": item.reason,
            "hash": item.content_sha256,
            "size": item.size_chars,
            "priority": priorities.get(item.source),
        } for item in context.decisions)
        return StepResult(
            scenario_id=scenario.scenario_id,
            repetition=repetition,
            step_number=step_number,
            objective=scenario.objective,
            current_constraints=tuple(
                item.constraint_id for item in scenario.constraints
            ),
            available_tools=scenario.available_tools,
            selected_tool=(decision.tool_name if decision else ""),
            tool_arguments=(
                dict(decision.arguments) if decision else {}
            ),
            normalized_observation=(
                observation.report_view() if observation else None
            ),
            model_output_hash=hashlib.sha256(
                response.raw_text.encode("utf-8")
            ).hexdigest(),
            context_hash=context_hash,
            context_chars=context.total_chars,
            context_items=len(context.items),
            context_decisions=context_decisions,
            validation_result=validation,
            progress_result=progress.to_dict(),
            recovery_result=tuple(
                record.to_dict() for record in response.recovery
            ),
            stop_reason=stop_reason.value if stop_reason else "",
            latency_ms=response.latency_ms,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            tokens_per_second=tokens_per_second,
            request_fingerprint=request.fingerprint(),
            tool_result_hash=(
                observation.result_sha256 if observation else ""
            ),
        )

    def _step_telemetry(
        self,
        step: StepResult,
        response: ModelResponse,
    ) -> dict[str, Any]:
        return {
            "provider": response.provider,
            "model": response.model,
            "profile": "TOOL_SELECTION",
            "scenario": step.scenario_id,
            "repetition": step.repetition,
            "step": step.step_number,
            "latency_ms": step.latency_ms,
            "prompt_tokens": step.input_tokens,
            "completion_tokens": step.output_tokens,
            "tokens_per_second": step.tokens_per_second,
            "validation": step.validation_result.get("status"),
            "provider_errors": step.validation_result.get(
                "provider_errors",
                [],
            ),
            "recovery": [
                item.get("action") for item in step.recovery_result
            ],
            "progress": dict(step.progress_result),
            "selected_tool": step.selected_tool,
            "tool_result_hash": step.tool_result_hash,
            "context_hash": step.context_hash,
            "stop_reason": step.stop_reason,
        }

    def _write_debug_prompt(
        self,
        scenario: BenchmarkScenario,
        repetition: int,
        step_number: int,
        request: ModelRequest,
    ) -> None:
        debug = self.output_dir / "debug_prompts"
        debug.mkdir(exist_ok=True)
        write_json(
            debug / (
                f"{scenario.scenario_id}-rep{repetition}-"
                f"step{step_number}.json"
            ),
            {
                "system_prompt": request.system_prompt,
                "user_prompt": request.user_prompt,
                "context": [
                    {
                        "source": item.source,
                        "kind": item.kind,
                        "content": item.content,
                    }
                    for item in request.context.items
                ],
            },
        )

    def _manifest(
        self,
        started_at: str,
        scenarios: tuple[BenchmarkScenario, ...],
        runtime: Mapping[str, Any],
        integrity: Mapping[str, Any],
    ) -> dict[str, Any]:
        return {
            "benchmark_version": BENCHMARK_VERSION,
            "created_at": started_at,
            "configuration": _config_payload(self.config),
            "configuration_hash": self.config.configuration_hash,
            "prompts_stored": self.config.debug_prompts,
            "fixture_catalog_sha256": fixture_catalog_hash(),
            "scenario_count": len(scenarios),
            "scenarios": [{
                "scenario_id": item.scenario_id,
                "group": item.group.value,
                "capability": item.capability,
                "objective_sha256": hashlib.sha256(
                    item.objective.encode("utf-8")
                ).hexdigest(),
                "constraints_sha256": sha256_json([
                    asdict(value) for value in item.constraints
                ]),
                "fixture_id": item.fixture.fixture_id,
                "fixture_sha256": item.fixture.content_sha256,
                "available_tools": list(item.available_tools),
                "max_steps": min(
                    item.max_steps,
                    self.config.max_steps,
                ),
                "expected_stop_reason": (
                    item.expected_stop_reason.value
                ),
                "fault_injection": bool(item.fault_injection),
                "variant": item.variant,
            } for item in scenarios],
            "runtime_before": runtime,
            "integrity_before": integrity,
            "safety": {
                "network": "localhost_ollama_only",
                "tool_registry": "benchmark_read_only",
                "project_mutation": False,
                "mission_mutation": False,
                "subprocess_tools": False,
                "shell_tools": False,
                "prompt_content_logged": self.config.debug_prompts,
            },
        }


def validate_transition(
    benchmark_step: BenchmarkStep,
    scenario: BenchmarkScenario,
    state: StatefulContext,
    decision: ModelDecision,
) -> list[str]:
    issues: list[str] = []
    if decision.tool_name not in benchmark_step.transition.allowed_tools:
        issues.append("Selected tool is outside the scenario allowlist.")
    if decision.decision == "CALL_TOOL":
        if decision.tool_name == "finish":
            issues.append("CALL_TOOL cannot select finish.")
        if decision.conclusion or decision.stop_reason or decision.plan:
            issues.append(
                "Non-finish decision contains final-only fields."
            )
    elif decision.decision == "FINISH":
        if decision.tool_name != "finish":
            issues.append("FINISH must select the finish tool.")
        previously_used = {
            item.tool_name for item in state.decisions
        }
        missing_tools = (
            set(scenario.required_tools)
            - previously_used
            - {"finish"}
        )
        if missing_tools:
            issues.append(
                "Finish attempted before required evidence tools: "
                + ", ".join(sorted(missing_tools))
            )
        if (
            len(state.known_references)
            < benchmark_step.transition.minimum_evidence
        ):
            issues.append("Finish attempted before sufficient evidence.")
        if not decision.conclusion or not decision.stop_reason:
            issues.append("Finish requires conclusion and stop_reason.")
        if decision.arguments.get("conclusion") != decision.conclusion:
            issues.append(
                "finish.arguments.conclusion differs from conclusion."
            )
        if decision.arguments.get("stop_reason") != decision.stop_reason:
            issues.append(
                "finish.arguments.stop_reason differs from stop_reason."
            )
    else:
        issues.append("Unknown decision type.")
    unknown_refs = set(decision.evidence_refs) - state.known_references
    if unknown_refs:
        issues.append(
            "Decision cites unknown references: "
            + ", ".join(sorted(unknown_refs))
        )
    return issues


def important_context_removed(context: Any) -> list[str]:
    important_prefixes = (
        "scenario:",
    )
    return [
        item.source
        for item in context.decisions
        if (
            not item.included
            and item.source.startswith(important_prefixes)
            and not item.source.endswith(":recent-decisions")
        )
    ]


def evaluate_scenario(
    scenario: BenchmarkScenario,
    state: StatefulContext,
    final_decision: ModelDecision | None,
    tools_called: list[str],
    actual_stop: StopReason,
    steps: list[StepResult],
) -> list[dict[str, Any]]:
    conclusion = final_decision.conclusion if final_decision else ""
    plan_text = (
        json.dumps(
            [asdict(item) for item in final_decision.plan],
            ensure_ascii=False,
        )
        if final_decision
        else ""
    )
    searchable = f"{conclusion}\n{plan_text}".casefold()
    required_tools = set(scenario.required_tools)
    observed_tools = set(tools_called)
    observed_refs = state.known_references
    cited_refs = (
        set(final_decision.evidence_refs)
        if final_decision
        else set()
    )
    required_terms_pass = all(
        any(option.casefold() in searchable for option in term.split("|"))
        for term in scenario.required_terms
    )
    forbidden_pass = all(
        term.casefold() not in searchable
        for term in scenario.forbidden_terms
    )
    criteria: list[dict[str, Any]] = [
        _criterion(
            "finished_with_structured_decision",
            final_decision is not None,
            f"finish_present={final_decision is not None}",
        ),
        _criterion(
            "expected_stop_reason",
            actual_stop == scenario.expected_stop_reason,
            (
                f"expected={scenario.expected_stop_reason.value}, "
                f"actual={actual_stop.value}"
            ),
        ),
        _criterion(
            "required_tools_used",
            required_tools.issubset(observed_tools),
            (
                f"required={sorted(required_tools)}, "
                f"observed={tools_called}"
            ),
        ),
        _criterion(
            "required_evidence_observed",
            set(scenario.required_references).issubset(observed_refs),
            (
                f"required={list(scenario.required_references)}, "
                f"observed={sorted(observed_refs)}"
            ),
        ),
        _criterion(
            "required_evidence_cited",
            (
                not scenario.required_references
                or set(scenario.required_references).issubset(cited_refs)
            ),
            (
                f"required={list(scenario.required_references)}, "
                f"cited={sorted(cited_refs)}"
            ),
        ),
        _criterion(
            "required_semantics",
            required_terms_pass,
            f"required_terms={list(scenario.required_terms)}",
        ),
        _criterion(
            "forbidden_semantics_absent",
            forbidden_pass,
            f"forbidden_terms={list(scenario.forbidden_terms)}",
        ),
        _criterion(
            "constraints_retained",
            (
                final_decision is not None
                and _constraints_retained(scenario, final_decision)
            ),
            (
                "expected="
                f"{[item.constraint_id for item in scenario.constraints]}, "
                "received="
                f"{list(final_decision.retained_constraint_ids) if final_decision else []}"
            ),
        ),
        _criterion(
            "no_repeated_tool_call",
            not any(
                ProgressCondition.REPEATED_TOOL_CALLS.value
                in item.progress_result.get("conditions", [])
                for item in steps
            ),
            f"step_count={len(steps)}",
        ),
        _criterion(
            "step_limit_respected",
            len(steps) <= min(scenario.max_steps, len(steps) or 1),
            f"steps={len(steps)}, configured={scenario.max_steps}",
        ),
    ]
    if scenario.evaluator == "short_plan":
        plan = final_decision.plan if final_decision else ()
        criteria.extend((
            _criterion(
                "plan_length",
                3 <= len(plan) <= 5,
                f"plan_steps={len(plan)}",
            ),
            _criterion(
                "plan_steps_verifiable",
                bool(plan) and all(
                    item.step
                    and item.required_evidence
                    and item.completion_condition
                    and item.negative_constraints
                    for item in plan
                ),
                "Every step requires evidence, completion and constraints.",
            ),
            _criterion(
                "plan_dependencies_ordered",
                bool(plan) and _plan_dependencies_ordered(plan),
                "Dependencies may only name earlier plan steps.",
            ),
            _criterion(
                "plan_non_redundant",
                bool(plan) and len({
                    item.step.strip().casefold() for item in plan
                }) == len(plan),
                "Plan step descriptions must be unique.",
            ),
        ))
    if scenario.evaluator == "context_scaling":
        max_context = max(
            (item.context_chars for item in steps),
            default=0,
        )
        criteria.append(_criterion(
            "context_target_materialized",
            max_context >= max(1, scenario.context_target_tokens * 4),
            (
                f"target_tokens={scenario.context_target_tokens}, "
                f"max_context_chars={max_context}"
            ),
        ))
    return criteria


def classify_scenario(
    criteria: list[Mapping[str, Any]],
    scenario: BenchmarkScenario,
) -> ScenarioStatus:
    failed = [
        item["criterion"]
        for item in criteria
        if not item["passed"]
    ]
    if not failed:
        return ScenarioStatus.PASS
    if (
        scenario.evaluator == "context_scaling"
        and set(failed).issubset({
            "required_evidence_cited",
            "context_target_materialized",
        })
    ):
        return ScenarioStatus.PASS_WITH_DEGRADATION
    return ScenarioStatus.FAIL


def build_capability_profile(
    results: list[ScenarioResult],
    steps: list[StepResult],
    config: BenchmarkConfig,
) -> tuple[CapabilityResult, ...]:
    grouped: dict[str, list[ScenarioResult]] = defaultdict(list)
    for result in results:
        grouped[result.capability].append(result)
    step_groups: dict[str, list[StepResult]] = defaultdict(list)
    capability_by_scenario = {
        result.scenario_id: result.capability for result in results
    }
    for step in steps:
        step_groups[capability_by_scenario.get(
            step.scenario_id,
            "unknown",
        )].append(step)
    profiles: list[CapabilityResult] = []
    for capability in sorted(grouped):
        capability_results = grouped[capability]
        capability_steps = step_groups.get(capability, [])
        passing = [
            item for item in capability_results
            if item.status in {
                ScenarioStatus.PASS,
                ScenarioStatus.PASS_WITH_DEGRADATION,
            }
        ]
        failing = [
            item for item in capability_results
            if item.status in {
                ScenarioStatus.FAIL,
                ScenarioStatus.INVALID,
            }
        ]
        distinct_cases = {
            _base_scenario_id(item.scenario_id)
            for item in capability_results
        }
        repetitions = max(
            (
                len([
                    item for item in capability_results
                    if item.scenario_id == scenario_id
                ])
                for scenario_id in {
                    item.scenario_id for item in capability_results
                }
            ),
            default=0,
        )
        has_degradation = any(
            item.status == ScenarioStatus.PASS_WITH_DEGRADATION
            for item in capability_results
        )
        if not capability_results:
            status = CapabilityStatus.NOT_DEMONSTRATED
        elif not passing:
            status = CapabilityStatus.FAILED
        elif failing or has_degradation:
            status = CapabilityStatus.DEGRADED
        elif len(distinct_cases) >= 3 and repetitions >= 2:
            status = CapabilityStatus.DEMONSTRATED
        else:
            status = CapabilityStatus.DEMONSTRATED_PRELIMINARY
        confidence = round(
            (
                len(passing) / max(1, len(capability_results))
                * min(1.0, len(distinct_cases) / 3)
                * min(1.0, repetitions / 2)
            ),
            3,
        )
        latencies = [item.latency_ms for item in capability_steps]
        context_values = [
            item.context_chars for item in capability_steps
        ] or [0]
        limitations: list[str] = []
        if len(distinct_cases) < 3:
            limitations.append(
                "Fewer than three distinct cases were exercised."
            )
        if repetitions < 2:
            limitations.append(
                "Fewer than two repetitions were exercised."
            )
        if failing:
            limitations.append(
                f"{len(failing)} scenario repetitions failed."
            )
        profiles.append(CapabilityResult(
            capability=capability,
            status=status,
            confidence=confidence,
            passed_cases=len(passing),
            failed_cases=len(failing),
            total_cases=len(capability_results),
            total_calls=len(capability_steps),
            repetitions=repetitions,
            mean_latency_ms=round(
                statistics.mean(latencies), 2
            ) if latencies else 0.0,
            p95_latency_ms=percentile(latencies, 0.95),
            context_range=(
                min(context_values),
                max(context_values),
            ),
            recovery_used=any(
                item.recovery_used for item in capability_results
            ),
            limitations=tuple(limitations),
            configuration_hash=config.configuration_hash,
        ))
    return tuple(profiles)


def build_summary(
    config: BenchmarkConfig,
    scenarios: tuple[BenchmarkScenario, ...],
    results: list[ScenarioResult],
    steps: list[StepResult],
    profiles: tuple[CapabilityResult, ...],
    integrity: Mapping[str, Any],
    runtime_before: Mapping[str, Any],
    runtime_after: Mapping[str, Any],
    infrastructure_errors: list[str],
    started_at: str,
) -> dict[str, Any]:
    passed = [
        item for item in results
        if item.status in {
            ScenarioStatus.PASS,
            ScenarioStatus.PASS_WITH_DEGRADATION,
        }
    ]
    failed = [
        item for item in results
        if item.status in {
            ScenarioStatus.FAIL,
            ScenarioStatus.INVALID,
        }
    ]
    fault_scenario_ids = {
        item.scenario_id
        for item in scenarios
        if item.fault_injection
    }
    model_steps = [
        item for item in steps
        if item.scenario_id not in fault_scenario_ids
    ]
    fault_steps = [
        item for item in steps
        if item.scenario_id in fault_scenario_ids
    ]
    latencies = [item.latency_ms for item in model_steps]
    throughput = [
        item.tokens_per_second
        for item in model_steps
        if item.tokens_per_second is not None
    ]
    reproducibility = scenario_reproducibility(results)
    decision = final_decision(
        config,
        failed,
        integrity,
        infrastructure_errors,
    )
    completed_at = utc_now()
    return {
        "benchmark_version": BENCHMARK_VERSION,
        "started_at": started_at,
        "completed_at": completed_at,
        "duration_seconds": round(
            (
                datetime.fromisoformat(completed_at)
                - datetime.fromisoformat(started_at)
            ).total_seconds(),
            3,
        ),
        "mode": config.mode.value,
        "model": config.model,
        "configuration": _config_payload(config),
        "configuration_hash": config.configuration_hash,
        "scenario_definitions": len(scenarios),
        "scenario_repetitions": len(results),
        "passed_repetitions": len(passed),
        "failed_repetitions": len(failed),
        "status_counts": dict(sorted(_status_counts(results).items())),
        "total_steps": len(steps),
        "model_calls": len(model_steps),
        "fault_injection_steps": len(fault_steps),
        "provider_failed_steps": len([
            item for item in model_steps
            if item.validation_result.get("provider_errors")
        ]),
        "validation_passed_steps": len([
            item for item in model_steps
            if item.validation_result.get("status") == "PASSED"
        ]),
        "recovery_used_repetitions": len([
            item for item in results if item.recovery_used
        ]),
        "reproducibility": reproducibility,
        "performance": {
            "latency_ms": {
                "min": min(latencies) if latencies else 0,
                "median": (
                    statistics.median(latencies) if latencies else 0
                ),
                "p95": percentile(latencies, 0.95),
                "max": max(latencies) if latencies else 0,
                "mean": (
                    round(statistics.mean(latencies), 2)
                    if latencies else 0
                ),
            },
            "tokens_per_second": {
                "min": min(throughput) if throughput else 0,
                "median": (
                    statistics.median(throughput)
                    if throughput else 0
                ),
                "max": max(throughput) if throughput else 0,
                "mean": (
                    round(statistics.mean(throughput), 3)
                    if throughput else 0
                ),
            },
            "prompt_tokens": sum(
                item.input_tokens or 0 for item in model_steps
            ),
            "completion_tokens": sum(
                item.output_tokens or 0 for item in model_steps
            ),
            "context_chars": {
                "min": min(
                    (item.context_chars for item in model_steps),
                    default=0,
                ),
                "max": max(
                    (item.context_chars for item in model_steps),
                    default=0,
                ),
            },
        },
        "capability_statuses": {
            item.capability: item.status.value for item in profiles
        },
        "stop_reasons": dict(sorted(_stop_counts(results).items())),
        "integrity": dict(integrity),
        "runtime": {
            "before": dict(runtime_before),
            "after": dict(runtime_after),
        },
        "infrastructure_errors": infrastructure_errors,
        "decision": decision,
        "limitations": [
            "Fixtures are synthetic and closed-source.",
            "Read-only tool execution does not demonstrate productive tools.",
            "FULL mode was not executed unless explicitly shown by mode.",
            "Model results apply only to the recorded configuration.",
            (
                "Selected Ollama runner recycling is benchmark-only; "
                "the production Provider and ModelHarness are unchanged."
            ),
        ],
    }


def render_report(
    summary: Mapping[str, Any],
    profiles: tuple[CapabilityResult, ...],
) -> str:
    performance = summary["performance"]
    integrity = summary["integrity"]
    lines = [
        "# ModelHarness Stateful Tool Loop and Project Reasoning Benchmark",
        "",
        "## 1. Resumo executivo",
        (
            f"- Mode: `{summary['mode']}`; model: `{summary['model']}`; "
            f"passed repetitions: {summary['passed_repetitions']}/"
            f"{summary['scenario_repetitions']}."
        ),
        f"- Decision: `{summary['decision']}`.",
        "",
        "## 2. Arquitetura do benchmark",
        "- ModelHarness -> validated decision -> read-only fixture tool -> normalized observation -> ContextBuilder -> next decision.",
        "",
        "## 3. Diferencas entre v1 e v2",
        "- v1 measures isolated calls; v2 measures bounded state transitions and stop behavior.",
        "",
        "## 4. Cenarios implementados",
        f"- {summary['scenario_definitions']} scenario definitions across groups A-G.",
        "",
        "## 5. Tool registry read-only",
        "- list_files, read_file, search_text, inspect_symbol, query_fixture_index and finish.",
        "",
        "## 6. Seguranca da sandbox",
        "- Temporary fixture copies; absolute paths, traversal and symlinks are blocked.",
        "",
        "## 7. Stateful execution",
        f"- {summary['total_steps']} steps; {summary['model_calls']} real model calls.",
        "",
        "## 8. Context management",
        (
            f"- Recorded context range: {performance['context_chars']['min']}-"
            f"{performance['context_chars']['max']} chars."
        ),
        "",
        "## 9. Progress detection",
        f"- Stop reasons: `{json.dumps(summary['stop_reasons'], sort_keys=True)}`.",
        "",
        "## 10. Recovery exercitada",
        f"- Repetitions using recovery: {summary['recovery_used_repetitions']}.",
        "",
        "## 11. Project reasoning",
        f"- multi_file_reasoning: `{summary['capability_statuses'].get('multi_file_reasoning', 'NOT_RUN')}`.",
        "",
        "## 12. Context scaling",
        f"- context_scaling: `{summary['capability_statuses'].get('context_scaling', 'NOT_RUN')}`.",
        "",
        "## 13. Planeamento curto",
        f"- short_horizon_planning: `{summary['capability_statuses'].get('short_horizon_planning', 'NOT_RUN')}`.",
        "",
        "## 14. Documento e investigacao",
        (
            "- closed_source_research: `"
            f"{summary['capability_statuses'].get('closed_source_research', 'NOT_RUN')}`; "
            "evidence_based_document_generation: `"
            f"{summary['capability_statuses'].get('evidence_based_document_generation', 'NOT_RUN')}`."
        ),
        "",
        "## 15. Perfil de capacidades",
        "",
        "| Capability | Status | Confidence | Passed | Failed |",
        "|---|---|---:|---:|---:|",
    ]
    lines.extend(
        f"| {item.capability} | {item.status.value} | "
        f"{item.confidence:.3f} | {item.passed_cases} | "
        f"{item.failed_cases} |"
        for item in profiles
    )
    lines.extend([
        "",
        "## 16. Performance",
        (
            f"- Median latency: {performance['latency_ms']['median']} ms; "
            f"P95: {performance['latency_ms']['p95']} ms; "
            f"mean throughput: "
            f"{performance['tokens_per_second']['mean']} tokens/s."
        ),
        "",
        "## 17. Reprodutibilidade",
        (
            f"- Exact scenario traces: "
            f"{summary['reproducibility']['exact_cases']}/"
            f"{summary['reproducibility']['eligible_cases']}."
        ),
        "",
        "## 18. Integridade",
        (
            f"- Unchanged: `{integrity['unchanged']}`; "
            f"integrity_failed: `{integrity['integrity_failed']}`."
        ),
        "",
        "## 19. Testes",
        "- See repository test evidence reported with this run.",
        "",
        "## 20. Regressoes",
        (
            "- Infrastructure errors: "
            f"{len(summary['infrastructure_errors'])}."
        ),
        "",
        "## 21. Limitacoes factuais",
    ])
    lines.extend(f"- {item}" for item in summary["limitations"])
    lines.extend([
        "",
        "## 22. Proximo passo recomendado",
        "- Review failed scenario evidence before any productive integration.",
        "",
        "## 23. Decisao",
        f"`{summary['decision']}`",
        "",
    ])
    return "\n".join(lines)


def integrity_snapshot() -> dict[str, Any]:
    trees = {
        name: tree_integrity(REPO_ROOT / relative)
        for name, relative in INTEGRITY_TREES.items()
    }
    files: dict[str, Any] = {}
    for relative in CRITICAL_FILES:
        path = REPO_ROOT / relative
        files[relative] = {
            "exists": path.exists(),
            "size_bytes": path.stat().st_size if path.exists() else 0,
            "sha256": (
                sha256_file(path)
                if path.exists()
                else hashlib.sha256(b"missing").hexdigest()
            ),
        }
    return {
        "trees": trees,
        "critical_files": files,
        "fixture_catalog_sha256": fixture_catalog_hash(),
    }


def scenario_reproducibility(
    results: list[ScenarioResult],
) -> dict[str, Any]:
    grouped: dict[str, list[ScenarioResult]] = defaultdict(list)
    for result in results:
        grouped[result.scenario_id].append(result)
    eligible = {
        key: value for key, value in grouped.items() if len(value) > 1
    }
    exact = {
        key: len({
            tuple(item.response_hashes) for item in values
        }) == 1
        for key, values in eligible.items()
    }
    return {
        "eligible_cases": len(eligible),
        "exact_cases": sum(exact.values()),
        "all_exact": bool(eligible) and all(exact.values()),
        "cases": exact,
    }


def final_decision(
    config: BenchmarkConfig,
    failed: list[ScenarioResult],
    integrity: Mapping[str, Any],
    infrastructure_errors: list[str],
) -> str:
    if integrity.get("integrity_failed"):
        return "REGRESSION_DETECTED"
    if infrastructure_errors:
        return "IMPLEMENTATION_INCOMPLETE"
    if config.mode == BenchmarkMode.SMOKE:
        return (
            "MODEL_HARNESS_STATEFUL_CAPABILITIES_PARTIALLY_VALIDATED"
            if not failed
            else "MODEL_HARNESS_STATEFUL_BENCHMARK_IMPLEMENTED_NOT_VALIDATED"
        )
    if failed:
        return "MODEL_HARNESS_STATEFUL_CAPABILITIES_PARTIALLY_VALIDATED"
    return "MODEL_HARNESS_STATEFUL_CAPABILITIES_VALIDATED"


def repetitions_for(mode: BenchmarkMode, configured: int) -> int:
    if mode == BenchmarkMode.SMOKE:
        return 1
    if mode == BenchmarkMode.FULL:
        return max(2, configured)
    return max(2, configured)


def provider_tokens_per_second(
    envelope: Mapping[str, Any],
) -> float | None:
    count = envelope.get("eval_count")
    duration = envelope.get("eval_duration")
    if (
        isinstance(count, int)
        and isinstance(duration, int)
        and duration > 0
    ):
        return round(count / (duration / 1_000_000_000), 3)
    return None


def sanitized_provider_errors(
    errors: tuple[Mapping[str, Any], ...],
) -> list[dict[str, str]]:
    return [{
        "stage": str(item.get("stage") or "PROVIDER"),
        "type": str(item.get("type") or "UnknownProviderError"),
        "message_sha256": hashlib.sha256(
            str(item.get("message") or "").encode("utf-8")
        ).hexdigest(),
    } for item in errors]


def _fault_payloads(
    fault: str,
) -> tuple[str, str, ExpectedOutput]:
    if fault == "invalid_enum":
        expected = ExpectedOutput(
            format=OutputFormat.JSON_SCHEMA,
            schema={
                "type": "object",
                "required": ["status"],
                "properties": {"status": {"type": "string"}},
                "additionalProperties": False,
            },
            enum_constraints=(
                EnumConstraint("$.status", ("READY",)),
            ),
        )
        return '{"status":"BROKEN"}', '{"status":"READY"}', expected
    if fault == "truncated_json":
        expected = ExpectedOutput(
            format=OutputFormat.JSON_SCHEMA,
            schema={
                "type": "object",
                "required": ["status"],
                "properties": {"status": {"type": "string"}},
                "additionalProperties": False,
            },
        )
        return '{"status":', '{"status":"READY"}', expected
    if fault == "missing_tool_argument":
        expected = ExpectedOutput(
            format=OutputFormat.JSON_SCHEMA,
            schema={
                "type": "object",
                "required": ["arguments"],
                "properties": {
                    "arguments": {
                        "type": "object",
                        "required": ["path"],
                        "properties": {
                            "path": {"type": "string"},
                        },
                        "additionalProperties": False,
                    },
                },
                "additionalProperties": False,
            },
        )
        return (
            '{"arguments":{}}',
            '{"arguments":{"path":"facts.txt"}}',
            expected,
        )
    expected = ExpectedOutput(
        format=OutputFormat.JSON_SCHEMA,
        schema={
            "type": "object",
            "required": ["source"],
            "properties": {"source": {"type": "string"}},
            "additionalProperties": False,
        },
        reference_constraints=(
            ReferenceConstraint(
                "$.source",
                ("file:facts.txt",),
            ),
        ),
    )
    return (
        '{"source":"file:unknown.txt"}',
        '{"source":"file:facts.txt"}',
        expected,
    )


def _criterion(
    name: str,
    passed: bool,
    evidence: str,
) -> dict[str, Any]:
    return {
        "criterion": name,
        "passed": bool(passed),
        "evidence": evidence,
    }


def _constraints_retained(
    scenario: BenchmarkScenario,
    decision: ModelDecision,
) -> bool:
    return set(decision.retained_constraint_ids) == {
        item.constraint_id for item in scenario.constraints
    }


def _decision_violates_forbidden_paths(
    scenario: BenchmarkScenario,
    decision: ModelDecision,
) -> bool:
    serialized = json.dumps(
        {
            "arguments": dict(decision.arguments),
            "evidence_refs": list(decision.evidence_refs),
        },
        ensure_ascii=False,
        sort_keys=True,
    ).casefold()
    return any(
        term.casefold() in serialized
        for term in scenario.forbidden_terms
        if "/" in term or "\\" in term
    )


def _parse_stop_reason(value: str) -> StopReason:
    try:
        return StopReason(value)
    except ValueError:
        return StopReason.VALIDATION_FAILED


def _progress_stop_reason(
    conditions: tuple[ProgressCondition, ...],
) -> StopReason:
    if ProgressCondition.REPEATED_TOOL_CALLS in conditions:
        return StopReason.REPEATED_TOOL_CALL
    return StopReason.NO_PROGRESS


def _recovery_was_attempted(response: ModelResponse) -> bool:
    return any(item.retry_requested for item in response.recovery)


def _base_scenario_id(value: str) -> str:
    if value.endswith(("_V1", "_V2", "_V3")):
        return value[:-3]
    return value


def _plan_dependencies_ordered(plan: tuple[Any, ...]) -> bool:
    for index, item in enumerate(plan):
        prior_names = {
            prior.step.strip().casefold()
            for prior in plan[:index]
        }
        for dependency in item.dependencies:
            normalized = dependency.strip().casefold()
            if normalized in prior_names:
                continue
            digits = "".join(
                character
                for character in normalized
                if character.isdigit()
            )
            if digits and 1 <= int(digits) <= index:
                continue
            return False
    return True


def _status_counts(
    results: list[ScenarioResult],
) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for item in results:
        counts[item.status.value] += 1
    return dict(counts)


def _stop_counts(
    results: list[ScenarioResult],
) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for item in results:
        counts[item.stop_reason.value] += 1
    return dict(counts)


def _config_payload(config: BenchmarkConfig) -> dict[str, Any]:
    payload = asdict(config)
    payload["mode"] = config.mode.value
    return payload


def percentile(values: list[int], quantile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    position = (len(ordered) - 1) * quantile
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return round(
        ordered[lower]
        + (ordered[upper] - ordered[lower]) * fraction,
        2,
    )


def write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            sort_keys=False,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )


def write_json_lines(
    path: Path,
    records: list[Mapping[str, Any]],
) -> None:
    path.write_text(
        "".join(
            json.dumps(
                record,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
            for record in records
        ),
        encoding="utf-8",
        newline="\n",
    )


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
