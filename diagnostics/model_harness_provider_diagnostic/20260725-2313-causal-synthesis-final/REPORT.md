# Stateful Provider Path Diagnostic

## 1. Resumo executivo

- Decision: **MODEL_HARNESS_STATEFUL_PROVIDER_PATH_DIAGNOSED**.
- Responsible component: `Ollama llama-server runner and single-slot lifecycle`.
- Blocking phase: `ollama_generation_after_sampler_initialization_before_first_token_and_response_headers`.
- No production change or timeout increase was made.

## 2. Problema reproduzido

- The historical A01 request ended after 300324 ms with `PROVIDER_FAILED`, zero token accounting, and the empty-output hash.
- Exact reconstruction proven: `True`.

## 3. Request exato analisado

- Payload: `6622` bytes, SHA-256 `bf09f238164d9001392710211ed2e3716f68a7f274c1a26837580693b6e6b5e8`.
- Schema: `1341` bytes.
- Input observed by Ollama: `988` tokens.

## 4. Timeline

- Historical: request reached `server_stream`, acquired slot 0, started task 0, processed 988 prompt tokens, and initialized the sampler.
- Historical: no completion/idle event followed; the POST ended 500 at 5m0s and task 0 was cancelled.
- Following queued 5-minute failures: `7`.
- Subsequent slot selections: `0`.

## 5. Tipo de excecao

- Historical benchmark surface: `PROVIDER_FAILED`.
- Controlled contaminated runner: concrete `httpx.ReadTimeout` before response headers and with zero response bytes.

## 6. Comparacao v1 vs v2

- Same endpoint: `True`.
- Same adapter: `True`.
- Same HTTP client: `True`.
- Payload bytes v1/v2: `716` / `6622`.
- The requests differ materially, but the clean matrix refutes those differences as the cause of the 300-second stall.

## 7. Estrutura e complexidade do schema

- Nodes/depth/properties: `22` / `7` / `13`.
- Enums/values/required: `3` / `20` / `13`.
- Full schema and every D12 reduction completed on isolated runners.

## 8. Resultados da matriz

| Variant | Status | Duration ms | Input | Output |
|---|---|---:|---:|---:|
| `D01_BASELINE_SIMPLE` | SUCCEEDED | 22198.698 | 26 | 2 |
| `D02_STATEFUL_PROMPT_NO_SCHEMA` | SUCCEEDED | 40858.35 | 988 | 115 |
| `D03_STATEFUL_PROMPT_MINIMAL_SCHEMA` | SUCCEEDED | 26916.485 | 988 | 14 |
| `D04_FULL_SCHEMA_NO_TOOLS` | SUCCEEDED | 53061.685 | 461 | 133 |
| `D05_FULL_SCHEMA_ONE_TOOL` | SUCCEEDED | 31435.499 | 649 | 91 |
| `D06_FULL_SCHEMA_ALL_TOOLS` | SUCCEEDED | 35415.141 | 988 | 91 |
| `D07_DIRECT_OLLAMA_FULL_REQUEST` | SUCCEEDED | 34919.42 | 988 | 91 |
| `D08_HARNESS_FULL_REQUEST` | SUCCEEDED | 34712.003 | 988 | 91 |
| `D09_V1_PROVIDER_WITH_V2_PAYLOAD` | ALIAS_CONFIRMED | - | - | - |
| `D10_V2_PROVIDER_WITH_V1_PAYLOAD` | NOT_APPLICABLE | - | - | - |
| `D11_SCHEMA_AS_PROMPT_ONLY` | SUCCEEDED | 35387.313 | 1308 | 90 |
| `D12_R1_WITHOUT_PLAN` | SUCCEEDED | 34067.898 | 988 | 85 |
| `D12_R2_WITHOUT_ARGUMENTS` | SUCCEEDED | 33343.406 | 988 | 76 |
| `D12_R3_CORE_DECISION` | SUCCEEDED | 25368.917 | 988 | 23 |
| `D12_R4_CORE_PLUS_ARGUMENTS` | SUCCEEDED | 26768.988 | 988 | 38 |
| `D12_R5_CORE_PLUS_ARRAYS` | SUCCEEDED | 31304.411 | 988 | 65 |
| `D12_SCHEMA_COMPLEXITY_REDUCTION` | COMPLETED | - | - | - |
| `D07S_DIRECT_OLLAMA_FULL_REQUEST_STREAM` | SUCCEEDED | 20794.731 | 988 | 91 |

## 9. Chamada direta Ollama

- Status: `SUCCEEDED` in `34919.42` ms.
- JSON/schema valid: `True` / `True`.

## 10. Chamada via ModelHarness

- Status: `SUCCEEDED` in `34712.003` ms.
- JSON/schema valid: `True` / `True`.

## 11. Streaming e partial output

- Exact stream probe: `SUCCEEDED` in `20794.731` ms.
- Headers, first byte, first chunk, and first token were observed at 14859 ms; completion was observed at 19687 ms.
- Historical failed calls produced no partial output.

## 12. Estado do Ollama

- The historical first request occupied the only slot and did not return it to idle after cancellation.
- Explicitly approved model unloads isolated matrix variants; all 14 matrix unloads and the stream-probe unload succeeded (15 total).

## 13. GPU, VRAM, RAM e CPU

- Original Ollama load system memory: `{'total': '15.7 GiB', 'free': '659.2 MiB', 'free_swap': '5.7 GiB'}`.
- Stateful GPU before: `{'name': 'NVIDIA GeForce RTX 5060 Laptop GPU', 'driver_version': '581.34', 'memory_total_mib': 8151, 'memory_used_mib': 4276, 'memory_free_mib': 3535, 'utilization_percent': 61}`.
- Bounded v1 GPU before: `{'name': 'NVIDIA GeForce RTX 5060 Laptop GPU', 'driver_version': '581.34', 'memory_total_mib': 8151, 'memory_used_mib': 1129, 'memory_free_mib': 6682, 'utilization_percent': 15}`.
- Clean runtime snapshots and process CPU/RAM samples are in `ollama_runtime.jsonl`.

## 14. Hipoteses avaliadas

- `H1_SCHEMA_COMPLEXITY`: **NOT_SUPPORTED**.
- `H2_PROVIDER_ADAPTER`: **NOT_SUPPORTED**.
- `H3_STREAM_HANDLING`: **NOT_SUPPORTED**.
- `H4_TOOL_AND_FORMAT_COMBINATION`: **NOT_SUPPORTED**.
- `H5_CONTEXT_OR_OUTPUT_OPTIONS`: **NOT_SUPPORTED**.
- `H6_HTTP_TIMEOUT_LAYER`: **SUPPORTED**.
- `H7_OLLAMA_RUNTIME`: **SUPPORTED**.
- `H8_HARNESS_RESPONSE_PATH`: **NOT_SUPPORTED**.
- `H9_REQUEST_SERIALIZATION`: **NOT_SUPPORTED**.
- `H10_MODEL_COLD_OR_RELOAD`: **PARTIALLY_SUPPORTED**.

## 15. Causa raiz

The historical request reached Ollama, acquired the only llama-server slot, processed all 988 prompt tokens, and initialized its sampler, but the runner emitted no observable completion and never returned the slot to idle. The client then hit its 300-second read timeout; cancellation did not make the slot available, so the following seven requests queued and timed out. The identical full payload succeeds both directly and through ModelHarness after isolating runner state.

Resource pressure is a likely trigger, not a proven sole trigger.

## 16. Correcao proposta

In a separate scoped phase, add a bounded provider health guard for zero-byte ReadTimeouts: preserve the original exception, inspect runner availability, and recycle only the selected model runner before a later request. Prove the exact stateful request and the bounded v1 request; do not increase timeout.

## 17. Correcao implementada

None. The diagnostic did not modify production.

## 18. Validacao apos correcao

Not applicable because no production correction was implemented.

## 19. Testes

- Validation record: `{"focal_pytest": {"duration_seconds": 0.71, "passed": 35, "status": "PASSED"}, "full_pytest": {"duration_seconds": 133.29, "passed": 529, "skipped": 1, "status": "PASSED", "warnings": 14}, "full_stateful_smoke_rerun": false, "import_server": {"output": "IMPORT_SERVER_OK", "status": "PASSED"}, "py_compile": {"status": "PASSED"}}`.
- Normal tests do not require Ollama; live calls remain isolated.

## 20. Integridade

- Live diagnostic protected state unchanged: `True`.
- Tree changes: `[]`.
- Critical file changes: `[]`.
- Post-validation state unchanged: `False`.
- Post-validation changed trees: `['workspace_projects', 'mission_metadata']`.

## 21. Regressoes

- No protected project, mission, Chroma collection, or productive Harness file was mutated by live requests.
- The existing full pytest suite wrote ProjectBuilder test journals and fixture metadata after the live run. They were identified by test fixture names/timestamps and were not deleted.

## 22. Limitacoes

- The exact low-level cause of the runner stall below the sampler boundary is not emitted by Ollama logs.
- Resource pressure is correlated with the failure but was not independently manipulated, so it remains a likely trigger rather than a proven sole cause.
- The historical buffered provider collapsed the concrete ReadTimeout to PROVIDER_FAILED; the diagnostic reproduced the concrete ReadTimeout in the same contaminated runner state.

## 23. Proximo passo

In a separate scoped phase, add a bounded provider health guard for zero-byte ReadTimeouts: preserve the original exception, inspect runner availability, and recycle only the selected model runner before a later request. Prove the exact stateful request and the bounded v1 request; do not increase timeout.

## 24. Decisao

**MODEL_HARNESS_STATEFUL_PROVIDER_PATH_DIAGNOSED**
