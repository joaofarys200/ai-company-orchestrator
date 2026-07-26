# Stateful Provider Path Diagnostic

## 1. Resumo executivo

- Decision: **ROOT_CAUSE_NOT_IDENTIFIED**.
- Root cause: The observed controls do not isolate one cause.
- Blocking phase: `UNKNOWN`.
- Confidence: `low`.
- No production fix was implemented.

## 2. Problema reproduzido

- Scenario: `A01_FIND_RELEVANT_FILE`.
- Model: `qwen3.5:9b`.
- Historical request fingerprint matched: `True`.
- Historical context hash matched: `True`.

## 3. Request exato analisado

- Payload bytes: `6622`.
- Payload SHA-256: `bf09f238164d9001392710211ed2e3716f68a7f274c1a26837580693b6e6b5e8`.
- Schema SHA-256: `17b993fcf2e562e823c8061a79b883b34d28260de2f4d5b107cd2f394a965380`.
- Tools in top-level payload: `0`.
- Tool contracts are represented in selected context and in schema enums.

## 4. Timeline

- Direct exact status: `SUCCEEDED`.
- Response headers observed: `True`.
- First byte observed: `True`.
- First token observed: `True`.
- Unavailable phases are recorded as `NOT_OBSERVABLE`, never inferred.

## 5. Tipo de exceção

- Direct: `none` (`none`).
- Harness: `none` (`none`).

## 6. Comparação v1 vs v2

- Same endpoint: `True`.
- Same provider adapter: `True`.
- Same HTTP client: `True`.
- V1 payload bytes: `716`.
- V2 payload bytes: `6622`.
- V1 output cap: `768`.
- V2 output cap: `1024`.

## 7. Estrutura e complexidade do schema

- Bytes: `1341`.
- Nodes: `22`.
- Maximum depth: `7`.
- Properties: `13`.
- Required entries: `13`.
- Enums / values: `3` / `20`.
- Potential constructions: `[{"path": "#/properties/arguments", "construction": "unconstrained_object"}]`.
- Heuristics are not treated as proof; matrix controls decide support.

## 8. Resultados da matriz

| Variant | Path | Status | Duration ms | First byte | First token |
|---|---|---|---:|---|---|
| `D01_BASELINE_SIMPLE` | direct_ollama | SUCCEEDED | 22198.698 | True | True |
| `D02_STATEFUL_PROMPT_NO_SCHEMA` | direct_ollama | SUCCEEDED | 40858.35 | True | True |
| `D03_STATEFUL_PROMPT_MINIMAL_SCHEMA` | direct_ollama | SUCCEEDED | 26916.485 | True | True |
| `D04_FULL_SCHEMA_NO_TOOLS` | direct_ollama | SUCCEEDED | 53061.685 | True | True |
| `D05_FULL_SCHEMA_ONE_TOOL` | direct_ollama | SUCCEEDED | 31435.499 | True | True |
| `D06_FULL_SCHEMA_ALL_TOOLS` | direct_ollama | SUCCEEDED | 35415.141 | True | True |
| `D07_DIRECT_OLLAMA_FULL_REQUEST` | direct_ollama | SUCCEEDED | 34919.42 | True | True |
| `D08_HARNESS_FULL_REQUEST` | ModelHarness.execute -> OllamaBenchmarkProvider | SUCCEEDED | 34712.003 | False | False |
| `D09_V1_PROVIDER_WITH_V2_PAYLOAD` | same OllamaBenchmarkProvider used by v1 and v2 | ALIAS_CONFIRMED | - | False | False |
| `D10_V2_PROVIDER_WITH_V1_PAYLOAD` |  | NOT_APPLICABLE | - | False | False |
| `D11_SCHEMA_AS_PROMPT_ONLY` | direct_ollama | SUCCEEDED | 35387.313 | True | True |
| `D12_R1_WITHOUT_PLAN` | direct_ollama | SUCCEEDED | 34067.898 | True | True |
| `D12_R2_WITHOUT_ARGUMENTS` | direct_ollama | SUCCEEDED | 33343.406 | True | True |
| `D12_R3_CORE_DECISION` | direct_ollama | SUCCEEDED | 25368.917 | True | True |
| `D12_R4_CORE_PLUS_ARGUMENTS` | direct_ollama | SUCCEEDED | 26768.988 | True | True |
| `D12_R5_CORE_PLUS_ARRAYS` | direct_ollama | SUCCEEDED | 31304.411 | True | True |
| `D12_SCHEMA_COMPLEXITY_REDUCTION` | schema reduction | COMPLETED | - | - | - |
| `D12_R1_WITHOUT_PLAN` | direct_ollama | SUCCEEDED | 34067.898 | True | True |
| `D12_R2_WITHOUT_ARGUMENTS` | direct_ollama | SUCCEEDED | 33343.406 | True | True |
| `D12_R3_CORE_DECISION` | direct_ollama | SUCCEEDED | 25368.917 | True | True |
| `D12_R4_CORE_PLUS_ARGUMENTS` | direct_ollama | SUCCEEDED | 26768.988 | True | True |
| `D12_R5_CORE_PLUS_ARRAYS` | direct_ollama | SUCCEEDED | 31304.411 | True | True |

## 9. Chamada direta Ollama

- Status: `SUCCEEDED`.
- Payload SHA-256: `bf09f238164d9001392710211ed2e3716f68a7f274c1a26837580693b6e6b5e8`.
- Response bytes: `576`.

## 10. Chamada via ModelHarness

- Status: `SUCCEEDED`.
- Exception preserved: `False`.
- The existing provider buffers `stream=false`; internal HTTP milestones are therefore marked `NOT_OBSERVABLE` on this path.

## 11. Streaming e partial output

- Streaming probe status: `NOT_TESTED`.
- First streamed token observed: `False`.
- Partial bytes: `0`.

## 12. Estado do Ollama

- Runtime snapshots before, during, and after calls are in `ollama_runtime.jsonl`.

## 13. GPU, VRAM, RAM e CPU

- Resource measurements are correlated by `correlation_id` and `variant_id`; unavailable values are left absent.

## 14. Hipóteses avaliadas

- `H1_SCHEMA_COMPLEXITY`: **NOT_SUPPORTED**; evidence hash `72987c4e74e07ddf6d0cfd66e28413e2d518cbaef6b2cacf3f97ed10e2ca8bd6`.
- `H2_PROVIDER_ADAPTER`: **NOT_SUPPORTED**; evidence hash `990297d6cccce3feec4b660023e7ca8902bbb8bedae3535abeb51ea46eee2629`.
- `H3_STREAM_HANDLING`: **NOT_TESTED**; evidence hash `8a19a477fc7d30805e3bd1126e614f76bd2f323159a9cb7da8f45704a7fe8edd`.
- `H4_TOOL_AND_FORMAT_COMBINATION`: **NOT_SUPPORTED**; evidence hash `9d44b884440c73abf5997bb910c02e95c0b88dce7e995a47e93500d3b9f414e2`.
- `H5_CONTEXT_OR_OUTPUT_OPTIONS`: **NOT_SUPPORTED**; evidence hash `befef52663adb518c82d4582f04cfc4f645bfca1b07adb6bb0fd3a55bc8bbc97`.
- `H6_HTTP_TIMEOUT_LAYER`: **NOT_TESTED**; evidence hash `f1c7ce7ed00368f27bb6d02213585908cb1ee25b55a74e67fa6be4fdc9e69448`.
- `H7_OLLAMA_RUNTIME`: **PARTIALLY_SUPPORTED**; evidence hash `15853e2d0d975367b16c8b6c8940d524ed7524c10cb27b30766ac75063c93b1e`.
- `H8_HARNESS_RESPONSE_PATH`: **NOT_SUPPORTED**; evidence hash `e356f80c54001340a18edc0a76a6d27eb8485dbea62a3a3a9b7c9474876112ba`.
- `H9_REQUEST_SERIALIZATION`: **NOT_SUPPORTED**; evidence hash `029e8cc364e75dc35353bfce4c2e7f39d4cc496f0734d69cd3e7a9e1dcf84a18`.
- `H10_MODEL_COLD_OR_RELOAD`: **PARTIALLY_SUPPORTED**; evidence hash `68058da04ffffe502f1d465907520edeef7fcaf7a10495f63f51019cf82db83a`.

## 15. Causa raiz

The observed controls do not isolate one cause.

## 16. Correção proposta

Do not modify production; extend one controlled diagnostic dimension.

## 17. Correção implementada

None. Diagnosis preceded any production change, as required.

## 18. Validação após correção

Not applicable because no production correction was implemented.

## 19. Testes

Offline unit and integration results are recorded by the invoking engineering validation; live calls are isolated from the normal suite.

## 20. Integridade

- Unchanged: `True`.
- Changed trees: `[]`.
- Changed critical files: `[]`.

## 21. Regressões

No protected runtime tree or critical production file changed.

## 22. Limitações

- The historical failed run did not store raw prompts or provider payloads; exact reconstruction is proven by deterministic builders, matching context hash, matching request fingerprint, and matching configuration.
- D10 is not applicable because stateful v2 reuses the v1 provider.

## 23. Próximo passo

Do not modify production; extend one controlled diagnostic dimension.

## 24. Decisão

**ROOT_CAUSE_NOT_IDENTIFIED**
