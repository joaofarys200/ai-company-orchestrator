# Full System Health and Stabilization Report

Date: 2026-07-22
Branch: `system/full-health-audit`
Baseline commits created by this audit:

- `3b51a36 Make local test package explicit`
- `6c83b32 Bound large logical edit diff`

Pre-existing AirLLM changes remain uncommitted and were not staged or modified
by the ProjectBuilder audit.

## 1. Initial state

The worktree was already dirty with AirLLM experiments. The repository root and
branch were recorded before ProjectBuilder corrections. A dedicated branch was
created without reset, clean, checkout or deletion. Prior workspace runs and
projects were preserved.

## 2. Architecture identified

The real build path is:

```text
MissionStateStore
  -> MissionExecutorService.execute_work_package
  -> _run_project_builder
  -> agents.orchestrator.project_builder.build_project
  -> OllamaPlanRequester
  -> structural/security/semantic/integrity validation
  -> one focal correction at most
  -> materialization
  -> pre-validation and technical validation
  -> real commands and optional project preview
  -> ProjectBuildJournal
  -> MissionState execution/evidence
```

`MissionStateStore` persists missions and WorkPackages. `MissionExecutorService`
selects `PROJECT_BUILD`; it does not autonomously advance WP2. `ProjectBuilder`
owns planning, correction, validation, materialization, process supervision and
its journal. `F.3`/correction-effectiveness logic validates that focal changes
resolve the reported errors without broad rewrites. The structured correction
protocol is `project_builder_focal_correction_v2` and the maximum planning
attempt count remains two.

`CodingSession` and `ProjectContext` are separate paths used by the IDE executor
and are covered by the Python suite. `server.py` exposes mission execution and
ProjectBuilder websocket operations. No production orchestrator `__init__.py`
was modified.

## 3. Environment and dependencies

Python 3.12.4 is executed through the repository venv. Node is v24.16.0 and npm
is 11.13.0. Ollama is 0.32.1. `pip check` is clean. ProjectBuilder resolves
`qwen3.5:9b` and context 8192 from `.env`; the active process environment did
not override these values.

No static checker beyond the configured test/build tools was installed. Ruff,
flake8, pylint, mypy and pyright are unavailable.

## 4. Import and packaging problems

Confirmed root cause: the local `tests/` directory had no `__init__.py`, while
the venv contained an external regular package named `tests` distributed by
installed packages. `tests.test_project_builder_focal_v2` therefore resolved to
the external package and collection failed.

Correction: `tests/__init__.py` was added. After the correction, `tests`,
`agents`, `server` and project `config` resolve locally. No equivalent collision
was found for the checked project namespaces. The local `tests` package change
was committed separately as `3b51a36`.

## 5. Test collection

Before the correction, collection stopped with one import error and exposed 378
tests. After the correction, collection exposed 391 tests with exit code 0.
No tests were hidden with skips, xfail or collection filters.

## 6. Static analysis

`compileall` passed. The initial broad Python suite exposed no syntax or import
failure after the package correction. The remaining suite timeout was diagnosed
with `faulthandler`: `intelligence/coding_session.py:_logical_edit_scope` called
`difflib.SequenceMatcher(..., autojunk=False)` on a highly repetitive large
fixture, producing a quadratic comparison.

The minimal correction trims common line prefix/suffix and uses a controlled
single logical region when the remaining product exceeds 4,000,000 cells. This
keeps the public result fields and logical-edit meaning while preventing the
unbounded comparison. It was committed separately as `6c83b32`.

## 7. Complete suite

The final Python suite passed: `391 passed, 14 warnings in 92.92 s`. The 14
warnings are torch deprecations and did not fail tests. The ProjectBuilder
focused groups and frontend lint/build also passed. No known baseline blocker
remains in the tested Python, frontend or isolated Node paths.

## 8. Failure matrix

| ID | Class | Symptom | Root cause | Severity | WP1 impact | State |
|---|---|---|---|---|---|---|
| A-01 | C import/packaging | focal v2 collection import failed | external regular `tests` package shadowed local tests | High | Direct | Fixed |
| E-01 | E ProjectBuilder/IDE | large-file test suite stalled | quadratic `SequenceMatcher` on repetitive lines | High | Indirect | Fixed |
| D-01 | D test harness | first diagnostic runner rejected missing project root | runner did not create required MissionState project folder | Medium | Harness only | Fixed in diagnostic runner |
| D-02 | D test harness | executor unavailable in first real harness setup | runner used `ProjectBuilder` instead of persisted `PROJECT_BUILD` | Medium | Harness only | Fixed in diagnostic runner |
| K-01 | K model/provider | no plan within finite read timeout | Ollama `qwen3.5:9b` plan stream timed out | High | Blocks WP1 | Confirmed in attempt 2 |
| G-01 | G execution control | outer diagnostic process ended before second allowed model attempt | audit command timeout was 420 s while two internal reads can take about 600 s | Medium | Prevented complete evidence | Confirmed, not a production change |
| I-01 | I preview/health | no WP1 preview evidence | plan never reached materialization | High | Blocks WP1 evidence | Consequence, not independent root cause |

## 9. Root causes grouped

Infrastructure and imports are stable after the local package correction. Python
dependencies are internally consistent. The large diff issue was implementation
logic, not a model issue. The remaining end-to-end blocker is the active Ollama
planning path: attempt 2 produced a direct `PLAN_READ_TIMEOUT` after 300.687 s
with no partial response. The provider was reachable (`/api/tags`, `/api/ps` and
`/api/chat` returned HTTP 200 where observed), but the required JSON plan was not
delivered before the read timeout.

## 10. Corrections implemented

- Added `tests/__init__.py` to make local intra-suite imports deterministic.
- Added a large-core guard to `_logical_edit_scope` in `CodingSession` so a
  repetitive large fixture cannot hang on quadratic matching.
- Added only diagnostic fixture/runner files under this audit evidence folder.
- Did not modify `agents/orchestrator/__init__.py`, ProjectBuilder protocol,
  model settings, AirLLM files, fixtures or benchmark criteria.

## 11. Regression coverage

The complete suite, ProjectBuilder groups, runtime-integrity tests, collection,
compileall, pip check, frontend lint/build and isolated Node fixture all pass.
The large-file regression is now exercised by the existing runtime-integrity
tests. No new production tests were needed for the import correction beyond the
collection result because the failure was packaging resolution itself.

## 12. Baseline

`SYSTEM_BASELINE_PASSED` is established for the tested local system:

- collection: passed;
- compileall: passed;
- Python suite: 391 passed;
- pip check: passed;
- frontend lint/build: passed;
- Node syntax/test/build fixture: passed;
- persistence restart fixture: passed;
- preview and healthcheck fixture: passed.

## 13. WP1 execution 1

The first counted session used:

```text
project_id=health-attempt-1-c429262dd0
mission_id=wp1-b447ae6a7d7b45eb
execution_id=71c34a62f4004a43a9c54b019b1b7e25
build_run_id=34ff0b1118ef4cbb8c1cede503fa8804
```

The real executor entered `PROJECT_BUILD` and the journal entered `PLANNING`.
The outer command ended with exit 124 after 420.4 s. Ollama HTTP request logging
showed a 200 chat response, but the process ended before the requester persisted
diagnostics or a final plan. No plan hash, project name, expected files,
materialized files, command result or preview URL exists. Recovery through the
official stale-heartbeat path set the journal to `INTERRUPTED` and the execution
to `FAILED` with `primary_error.type=ProjectBuilderInterruptedError`.

This is not a success and not evidence of materialization.

## 14. WP1 execution 2

The independent session used:

```text
project_id=health-attempt-2-7b370c4342
mission_id=wp1-de42615c7fbd4126
execution_id=0bbc7c53751b48a6a17fced87f632fdf
build_run_id=66c62227ca7f4740821fcdd3968404a1
```

The requester log is conclusive for the first of the two allowed model calls:

```text
provider=ollama model=qwen3.5:9b attempt=1 duration=300.687
category=PLAN_READ_TIMEOUT partial_response=false
retry_reason=retryable:PLAN_READ_TIMEOUT
```

The second allowed attempt was started. The 420 s outer command ended before it
completed, so no plan or materialization was produced. The official recovery
path later set the journal to `INTERRUPTED` and execution to `FAILED`, preserving
the execution's primary interruption error. There was no WP2 call.

## 15. Remaining problems

1. The active Qwen/Ollama planning path did not produce a plan within the
   configured 300-second read timeout in the real WP1 session. This is a model or
   provider throughput blocker, not a validated ProjectBuilder semantic failure.
2. The audit runner's first outer timeout was too short to observe two sequential
   300-second planning calls. This is recorded as a diagnostic execution limit;
   no production timeout was changed.
3. The first real run was externally interrupted before it could persist its
   requester diagnostics. The journal recovery mechanism preserved a truthful
   interrupted state, but the missing final attempt record limits detail.
4. Static tools not already installed were not run. Their absence is an audit
   coverage limitation, not a reported code failure.

## 16. Risks

The main risk is declaring WP1 healthy based on baseline tests while the actual
model path remains unproven. A plan may still be rejected semantically after the
provider latency is resolved; that question is not demonstrated by these runs.
There is no evidence from this audit that the ProjectBuilder produced a false
success, wrote to Obsidian or materialized partial files.

## 17. Final state

```text
SYSTEM_STABLE_WP1_MODEL_BLOCKED
```

Confidence:

- baseline stable: high;
- import root cause and correction: high;
- large diff root cause and correction: high;
- no false-success materialization in WP1: high;
- provider blocking WP1: high for attempt 2, medium overall because attempt 1
  was externally interrupted before final requester diagnostics;
- WP1 reproducibility: not demonstrated.

The next action is to run the same real WP1 runner with an outer observation
window longer than the two configured internal read timeouts, without changing
the model, context, protocol or validators. Do not start WP2 before a plan reaches
technical validation and the required evidence is persisted.
