# ProjectBuilder Flight Recorder and Instrumented WP1 Report

## 1. Executive summary

The Flight Recorder was implemented as a separate observability module and
connected to the real ProjectBuilder and MissionExecutor paths. It does not
change the model, the focal correction protocol, the two-call limit, or any
validation decision.

Baseline after the final implementation:

- `python -m compileall -q agents tests`: passed.
- Flight Recorder tests: `8 passed`.
- ProjectBuilder family: `171 passed`.
- Requester, journal, and MissionState focal tests: `32 passed`.
- Python suite: `399 passed, 14 warnings`.
- `pip check`: passed.
- Frontend was not changed, so frontend lint/build were not rerun for this task.
- Stable synthetic overhead measurement: `3.64%` with local work included.

The single real WP1 ended in `VALIDATION_FAILED`. It consumed two model calls,
received complete HTTP streams, and failed before materialization because the
corrected plan still had semantic errors. No project files, commands, preview,
or healthcheck were produced.

Decision: `FLIGHT_RECORDER_IMPLEMENTED_WP1_FAILED_WITH_ROOT_CAUSE`

Confidence in the failure classification: high. The classification is supported
by the event timeline, requester metrics, planning journal, and persisted Mission
State. Confidence that the provider itself stalled: low; the recorder shows
successful complete responses from both attempts.

## 2. Implemented changes

Files changed by this task:

- `agents/orchestrator/flight_recorder.py`
- `agents/orchestrator/project_builder.py`
- `agents/mission_executor.py`
- `tests/test_project_builder_flight_recorder.py`
- `.gitignore`
- this report

The recorder is injected into `build_project`, can be disabled with
`PROJECT_BUILDER_FLIGHT_RECORDER_ENABLED=0`, and uses a no-op implementation
when disabled. Diagnostic payload and response samples are disabled by default.
The optional flag `PROJECT_BUILDER_FLIGHT_RECORDER_DIAGNOSTICS=1` enables bounded
sanitized raw response artifacts for a specifically authorized diagnostic run.

The recorder is independent of the ProjectBuildJournal. The journal remains the
functional state source; the recorder observes it through an attachment and
records journal writes without changing journal behavior.

## 3. Event schema

Every event contains these fields:

| Field | Meaning |
|---|---|
| `schema_version` | `project_builder_flight_recorder_v1` |
| `run_id` | Unique recorder execution identifier |
| `project_id` | Mission/project correlation identifier |
| `mission_id` | Mission correlation identifier |
| `execution_id` | Mission execution identifier |
| `build_run_id` | Existing ProjectBuildJournal run identifier |
| `phase` | Pipeline phase |
| `event` | Event name |
| `status` | Observed, running, completed, failed, or interrupted |
| `wall_clock_timestamp` | UTC timestamp |
| `monotonic_offset_ms` | Duration-safe offset from recorder start |
| `duration_ms` | Span duration when applicable |
| `parent_span_id` | Parent span relation |
| `span_id` | Unique operation span identifier |
| `attempt` | Request attempt number |
| `thread_id` / `process_id` | Runtime correlation |
| `metadata` | Sanitized bounded metadata |
| `error_type` / `error_message` | Sanitized failure information |
| `progress_counter` | Progress value when available |

Events are appended to `events.jsonl`. All writes flush incrementally. `fsync`
is reserved for critical failures, interruptions, timeouts, and journal writes.

## 4. Persistent artifacts

Each recorder run uses:

```text
diagnostics/project_builder_flight_recorder/<run_id>/
  events.jsonl
  summary.json
  timeline.md
  errors.json
  resource_samples.jsonl
  payload_metrics.json
  final_state.json
```

The generated directory is ignored by Git. Existing forensic artifacts are not
deleted and are referenced by path in this report.

## 5. Real pipeline points instrumented

| Phase | Real function/path | Events |
|---|---|---|
| Mission dispatch | `MissionExecutorService._run_project_builder` | `mission_execution_started`, `project_builder_dispatch_started` |
| Builder entry | `build_project` wrapper and `_build_project_impl` | `build_project_entered`, `configuration_resolved` |
| Prompt | `get_valid_project_plan` | `prompt_build_started`, `prompt_build_completed`, `request_payload_built` |
| Request readiness | `OllamaPlanRequester._readiness` | `readiness_check_started`, `readiness_check_completed` |
| Model request | `OllamaPlanRequester._generate` | request, headers, first byte, first chunk, first content, first JSON, progress, stream completion |
| Request lifecycle | `OllamaPlanRequester.__call__` | requester start/completion/failure, retry scheduling |
| Plan processing | `get_valid_project_plan` | parse, decode, schema and validation events |
| Focal correction | `get_valid_project_plan` | focal start, correction prompt/request/response, effectiveness, completion |
| Validation | plan processing and `_execute_validation_plan` | structural, security, semantic, integrity, component, persistence, entrypoint and preview events |
| Materialization | `_build_project_impl` | materialization span and bounded file write metadata |
| Commands | `_run_project_command` | command start, stdout/stderr bounded metrics, completion/failure, timeout, process lifecycle |
| Healthcheck | `_run_backend_healthcheck` | healthcheck start/completion/failure |
| Journal | `ProjectBuildJournal._persist` | journal write start/completion |
| Mission state | `MissionExecutorService._run_project_builder` | mission state update start/completion |
| Final state | `build_project` and MissionExecutor | build completed/failed/interrupted and final state |

No complete file contents are written to structured events. Files are represented
by relative paths, sizes, and hashes. Prompt and response content is represented
by lengths and hashes unless explicit diagnostics are enabled.

## 6. Recorder tests

`tests/test_project_builder_flight_recorder.py` proves:

1. completed spans have unique identifiers;
2. parent-child relationships are valid;
3. monotonic offsets do not decrease;
4. failed spans preserve the original exception and do not swallow it;
5. interrupted spans survive close;
6. secret fields and bounded output are sanitized;
7. heartbeats record an active phase and resource sample;
8. summary identifies the slowest span, last phases, and gaps;
9. requester stream metrics are persisted without raw response by default;
10. a real `build_project` flow records materialization and command events.

Result: `8 passed`.

## 7. Overhead

The first synthetic comparison against an empty no-op loop was not meaningful:
the baseline operation took approximately `0.0002 s`, so any file I/O produces a
large percentage. The recorder was then optimized to keep JSONL handles open and
avoid `fsync` on non-critical progress events.

The stable measurement used 40 local operations with 2 ms of real work each:

| Mode | Duration |
|---|---:|
| No-op recorder | `0.097853 s` |
| Active recorder | `0.101415 s` |
| Overhead | `3.64%` |
| Events | `120` |
| Event bytes | `63,214` |

The recorder does not cancel work based on heartbeat and does not change command,
retry, validation, or timeout policies.

## 8. Baseline after implementation

The final post-fix baseline was:

```text
compileall: passed
Flight Recorder focal tests: 8 passed
ProjectBuilder/requester/journal/MissionState focal tests: 32 passed
Python suite: 399 passed, 14 warnings, 80.16 s
pip check: No broken requirements found
```

The frontend was not affected by this Python-only change. No benchmark script was
run and no WP2 was executed.

## 9. Instrumented WP1 identifiers

Exactly one real WP1 execution reached the ProjectBuilder after the baseline:

| Identifier | Value |
|---|---|
| `project_id` | `flight-recorder-wp1-9864320f2fa3` |
| `mission_id` | `mission-9864320f2fa3` |
| `execution_id` | `ce4090ed6d0a46be809b4dccade64353` |
| `work_package_id` | `wp1` |
| `build_run_id` | `a794351f203f48828fde4de76fa34972` |
| `recorder_run_id` | `5ac225a31d8b471db547d15b36b9d0e4` |
| `execution status` | `VALIDATION_FAILED` |
| `work package status` | `VALIDATION_FAILED` |
| `mission status` | `ACTIVE` |

The setup attempt before this run did not create a mission or call the model: the
MissionState store rejected a project ID whose host directory did not yet exist.
It is not counted as a WP1 execution.

## 10. WP1 timeline

The integral generated timeline is:

`diagnostics/project_builder_flight_recorder/5ac225a31d8b471db547d15b36b9d0e4/timeline.md`

The JSONL source is:

`diagnostics/project_builder_flight_recorder/5ac225a31d8b471db547d15b36b9d0e4/events.jsonl`

Key events, using recorder monotonic offsets:

| Offset | Event | Result |
|---:|---|---|
| 0 ms | `mission_execution_started` | recorded |
| 16 ms | `build_project_entered` | recorded |
| 31 ms | readiness attempt 1 | service/model available |
| 12,438 ms | `first_response_byte` attempt 1 | received |
| 37,203 ms | `first_valid_json_object` attempt 1 | received |
| 37,266 ms | first plan parse/semantic validation | failed |
| 37,266 ms | focal correction started | recorded |
| 37,625 ms | correction HTTP request started | recorded |
| 40,109 ms | `first_response_byte` attempt 2 | received |
| 46,141 ms | `first_valid_json_object` attempt 2 | received |
| 46,172 ms | correction stream/request completed | complete response |
| 46,188 ms | correction effectiveness | failed semantic revalidation |
| 46,203 ms | `build_completed` | `VALIDATION_FAILED` |

No materialization span completed. No file write, command, preview, or healthcheck
event exists for this run.

## 11. Durations and gaps

Recorder summary:

- total recorder event count: `745`;
- error event count: `14`;
- slowest span: `planning`, `46,172 ms`, failed;
- largest observed regular gap: `5,000 ms` between heartbeat events;
- maximum heartbeat idle duration: `10,016 ms`;
- partial response: `false`;
- second attempt started: `true`;
- materialization partial: `false`;
- journal persisted: `true`;
- false success: `false`.

The gap classifier labels model/requester gaps as `modelo`, process/command gaps as
`subprocesso`, journal writes as `I/O`, and heartbeat-only idle intervals as `sem
progresso`. It does not label a gap as model time without an active requester span.

## 12. Requester and Ollama metrics

Configuration observed in the real run:

- provider: Ollama;
- model: `qwen3.5:9b`;
- context: `8192`;
- temperature: `0`;
- top-p: `0.8`;
- think: `false`;
- stream: `true`;
- keep-alive: `15m`;
- protocol: `project_builder_focal_correction_v2` for the correction response.

| Metric | Attempt 1 | Attempt 2 |
|---|---:|---:|
| Duration | `37.235 s` | `8.891 s` |
| First response byte | `12.219 s` | `2.625 s` |
| First valid JSON | `36.984 s` | `8.657 s` |
| Max chunk gap | `141 ms` | `125 ms` |
| Chunks | `516` | `113` |
| Bytes received | `65,918` | `14,634` |
| Content characters | `1,989` | `495` |
| Prompt eval count | `603` | `1,497` |
| Eval count | `623` | `146` |
| Done reason | `stop` | `stop` |
| Response SHA-256 | `5bb52a11725969fe7907c3c9b3ea29970aadaa85bae806ce03be67e96fd4540f` | `e021bef2af8e9418e8426c54107e7eca1f4eccc08f36a53e6916fea53d6b050c` |

Payload metrics are persisted in:

`diagnostics/project_builder_flight_recorder/5ac225a31d8b471db547d15b36b9d0e4/payload_metrics.json`

Both responses reached `done_reason=stop`; the failure was not a read timeout,
stream truncation, missing JSON, or model unavailability.

## 13. Validation and focal correction

First response semantic errors included:

- `MISSING_REQUESTED_COMPONENTS` for `preview`;
- `MISSING_COMPONENT_MAPPING` for `frontend` and `backend`;
- `DECLARED_COMPONENT_WITHOUT_ARTIFACTS` for declared components;
- `PERSISTENCE_NOT_IMPLEMENTED`;
- `MISSING_HEALTH_ROUTE`.

The second response did add the complete final component list and a healthcheck
strategy, but it was not effective because it referenced these paths without
declaring them in `files`:

- `src/index.html`;
- `public/styles.css`;
- `routes/health.js`.

It also left persistence without a mapped durable read/write implementation. The
final semantic errors were:

- `MAPPED_FILE_NOT_FOUND`;
- `DECLARED_COMPONENT_WITHOUT_ARTIFACTS` for frontend, persistence, and tests;
- `PERSISTENCE_NOT_IMPLEMENTED`;
- `MISSING_REQUIRED_COMPONENT` for frontend.

The validator correctly stopped before materialization. No local repair, third
call, validator relaxation, or automatic artifact creation occurred.

## 14. Materialization, commands, preview, and healthcheck

The ProjectBuilder journal reports:

- `current_phase`: `PLANNING`;
- `completion_reason`: `PLAN_SEMANTIC_INVALID`;
- `materialized_files`: empty;
- `files_created`: empty;
- commands executed: empty;
- preview: not started;
- healthcheck: not started;
- technical success: false.

The ProjectBuilder did not create the generated `health-boundary-probe` project.
The host directory used to satisfy MissionState project identity remained a
separate empty project directory; no generated source was written there.

## 15. Persistence, preview, and healthcheck state

The MissionExecutor persisted the failed execution and left the mission `ACTIVE`.
No evidence was created because the ProjectBuilder produced no technical result.
No preview server, backend process, or orphan subprocess was observed.

The first instrumented implementation closed the recorder before the mission state
save completed, so this run's summary has `mission_state_updated=false`. The state
itself was persisted by MissionExecutor. The lifecycle was corrected afterwards:
MissionExecutor now keeps the recorder open through `mission_state_update_started`
and `mission_state_update_completed`, then closes it. The fix passed the targeted
MissionExecutor and recorder tests and the final Python suite. WP1 was not repeated,
so the corrected event sequence is not claimed as a real-run observation.

## 16. Journal and MissionState consistency

ProjectBuilder journal:

`workspace/.jarvis/project_builder/runs/a794351f203f48828fde4de76fa34972.json`

Mission state is persisted under the project/mission metadata area for
`flight-recorder-wp1-9864320f2fa3` and `mission-9864320f2fa3`. The execution is
`VALIDATION_FAILED`; it was not marked completed or successful.

## 17. Root cause

The provider and HTTP requester completed normally in both attempts. The root
cause is semantic plan failure:

1. the original model plan omitted requested `preview` and component mappings;
2. the focal correction returned mappings to paths absent from the corrected file
   list;
3. persistence remained an in-memory design without durable read/write evidence;
4. the semantic validator rejected the corrected plan before any write.

This is a model-output/plan-quality failure observed at the semantic validation
boundary, not a provider timeout, parser failure, buffering failure, context
overflow, materialization failure, preview failure, or healthcheck failure.

## 18. Evidence artifacts

Primary recorder artifacts:

- `diagnostics/project_builder_flight_recorder/5ac225a31d8b471db547d15b36b9d0e4/events.jsonl`
- `diagnostics/project_builder_flight_recorder/5ac225a31d8b471db547d15b36b9d0e4/summary.json`
- `diagnostics/project_builder_flight_recorder/5ac225a31d8b471db547d15b36b9d0e4/timeline.md`
- `diagnostics/project_builder_flight_recorder/5ac225a31d8b471db547d15b36b9d0e4/errors.json`
- `diagnostics/project_builder_flight_recorder/5ac225a31d8b471db547d15b36b9d0e4/resource_samples.jsonl`
- `diagnostics/project_builder_flight_recorder/5ac225a31d8b471db547d15b36b9d0e4/payload_metrics.json`
- `diagnostics/project_builder_flight_recorder/5ac225a31d8b471db547d15b36b9d0e4/final_state.json`

Related functional journal:

- `workspace/.jarvis/project_builder/runs/a794351f203f48828fde4de76fa34972.json`

Raw prompts and full raw responses were not persisted because diagnostic content
mode was disabled. Lengths, hashes, bounded sanitized errors, and stream metrics
were persisted.

## 19. Commits

Commits created without staging or changing the existing AirLLM work:

1. `73f3802` - Add ProjectBuilder flight recorder core
2. `69039fb` - Instrument ProjectBuilder execution and requester
3. `2e11533` - Add Flight Recorder regression tests
4. `5815ad2` - Close flight recorder after mission state persistence

The report is intentionally separate from these implementation commits. AirLLM
changes remain outside the commits above.

## 20. Final decision

`FLIGHT_RECORDER_IMPLEMENTED_WP1_FAILED_WITH_ROOT_CAUSE`

The system now provides a durable timeline capable of distinguishing provider
latency, stream progress, parsing, semantic validation, materialization, process,
journal, and state phases. The single real WP1 was not successful, and WP2 was not
executed.
