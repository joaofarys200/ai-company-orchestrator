# Commands and Evidence

Audit directory: `diagnostics/full_system_audit/20260722-140649`
Branch: `system/full-health-audit`

## Environment

| Command | Exit code | Result |
|---|---:|---|
| `git rev-parse HEAD` | 0 | `aa29728f7bd24fc12ee3673037d5b961e6a15b8b` before audit branch commits |
| `git branch --show-current` | 0 | `system/full-health-audit` |
| `venv/Scripts/python.exe --version` | 0 | Python 3.12.4 |
| `venv/Scripts/python.exe -m pytest --version` | 0 | pytest 8.4.2 |
| `node --version` | 0 | v24.16.0 |
| `npm --version` | 0 | 11.13.0 |
| `ollama --version` | 0 | 0.32.1 |
| `venv/Scripts/python.exe -m pip check` | 0 | No broken requirements found. |

Resolved ProjectBuilder configuration:

```text
provider=ollama
model=qwen3.5:9b
context_tokens=8192
max_output_tokens=16384
temperature=0
top_p=0.8
think=False
stream=True
keep_alive=15m
connect_timeout=5
read_timeout=300
write_timeout=15
pool_timeout=5
protocol=project_builder_focal_correction_v2
```

The model and context values are read from the project `.env` by
`_project_builder_setting`; they were not changed by this audit.

## Collection and Python

| Command | Exit code | Result |
|---|---:|---|
| `venv/Scripts/python.exe -m pytest -q --collect-only` before fixes | 1 | 378 collected, focal v2 import error |
| `venv/Scripts/python.exe -m pytest -q --collect-only` after fixes | 0 | 391 collected |
| `venv/Scripts/python.exe -m compileall` | 0 | Passed |
| `venv/Scripts/python.exe -m pytest -q` | 0 | 391 passed, 14 warnings, 92.92 s |
| non-AirLLM Python suite | 0 | 288 passed, 76.83 s |
| ProjectBuilder group A | 0 | 108 passed, 210.94 s |
| ProjectBuilder group B1 | 0 | 57 passed, 32.11 s |
| ProjectBuilder group B2 | 0 | 41 passed, 12.11 s |
| `tests/test_project_runtime_integrity.py` | 0 | 10 passed, 8.93 s |
| `venv/Scripts/python.exe -m pip check` | 0 | No broken requirements found. |

Unavailable static tools were recorded, not installed: ruff, flake8, pylint,
mypy and pyright.

## Frontend

| Command | Exit code | Result |
|---|---:|---|
| `npm run lint --prefix frontend` | 0 | Passed with no output |
| `npm run build --prefix frontend` | 0 | Vite 8.0.16 build passed |
| ad-hoc `node --check` over every frontend file including `node_modules` | 1 | Invalid audit command reached a TypeScript file in `node_modules`; not an application failure |

## Isolated Node fixture

Fixture: `node_fixture/`

| Command | Exit code | Result |
|---|---:|---|
| `npm run check` | 0 | Backend and test JavaScript syntax passed |
| `npm test` | 0 | Real backend, `/health`, persistence restart and cleanup passed |
| `npm run build` | 0 | Build passed |
| `node tests/reference-error.js` child | 1 | ReferenceError propagated |
| `node tests/promise-rejection.js` child | 1 | Promise rejection propagated |
| `node tests/stderr-zero.js` child | 0 | Demonstrates stderr alone is not a valid success criterion |
| Python static preview on fixture frontend | 0 | HTTP 200 and expected `Health Fixture` content |

The PowerShell wrappers around the two deliberately failing Node scripts did not
forward `$LASTEXITCODE`; the child exit codes above are the authoritative values.

## WP1

The first two commands below were runner calibration failures before a model call:

```text
MissionStateError: project_id did not exist in workspace/projects
ExecutorUnavailableError: executor kind ProjectBuilder is not PROJECT_BUILD
```

The diagnostic runner was corrected to create the required clean project folder
and use the persisted `PROJECT_BUILD` executor kind. These calibration sessions
are not counted as WP1 executions.

Attempt 1 command:

```text
venv/Scripts/python.exe diagnostics/full_system_audit/20260722-140649/wp1_runner.py --label attempt-1 --output diagnostics/full_system_audit/20260722-140649/wp1_attempt_1.json
```

Result: outer command exit 124 after 420.4 s. Ollama emitted HTTP 200 for the
chat request, but the process was terminated before the ProjectBuilder wrote a
final report. Journal recovery later recorded `EXECUTION_INTERRUPTED`.

Attempt 2 command:

```text
venv/Scripts/python.exe diagnostics/full_system_audit/20260722-140649/wp1_runner.py --label attempt-2 --output diagnostics/full_system_audit/20260722-140649/wp1_attempt_2.json
```

Result: outer command exit 124 after 420.2 s. The captured ProjectBuilder log
contains:

```text
attempt=1 duration=300.687 category=PLAN_READ_TIMEOUT retry_reason=retryable:PLAN_READ_TIMEOUT partial_response=false
```

The requester then started the second and final allowed attempt. The outer
command terminated before that attempt completed. Journal recovery recorded
`EXECUTION_INTERRUPTED` after the 300-second stale-heartbeat guard elapsed.
