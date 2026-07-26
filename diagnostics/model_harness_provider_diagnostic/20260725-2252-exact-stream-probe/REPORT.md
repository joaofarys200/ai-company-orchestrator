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

- Direct exact status: `NOT_TESTED`.
- Response headers observed: `False`.
- First byte observed: `False`.
- First token observed: `False`.
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
| `EXACT_STREAM_PROBE` | direct_ollama | SUCCEEDED | 20794.731 | True | True |

## 9. Chamada direta Ollama

- Status: `NOT_TESTED`.
- Payload SHA-256: ``.
- Response bytes: `0`.

## 10. Chamada via ModelHarness

- Status: `NOT_TESTED`.
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

- `H1_SCHEMA_COMPLEXITY`: **NOT_TESTED**; evidence hash `d4ce14cb612cf4277438fd5d15a42fe882dcc442fddba419365f97d11e16cad6`.
- `H2_PROVIDER_ADAPTER`: **NOT_SUPPORTED**; evidence hash `0d83cf6bed5b5c30699dc9beb6aa5aced27e8ea6e195b11b39dcf7a504fb9b9f`.
- `H3_STREAM_HANDLING`: **NOT_TESTED**; evidence hash `75175d058674e8332358f72faf448b3dba1c6f43fa3cda1a9ec40441ffe6837d`.
- `H4_TOOL_AND_FORMAT_COMBINATION`: **PARTIALLY_SUPPORTED**; evidence hash `521e1f215366aadc05c0bc26a765d7e67e27360f70f2a77376f5c88e498a1150`.
- `H5_CONTEXT_OR_OUTPUT_OPTIONS`: **NOT_TESTED**; evidence hash `004a3567d4300a2512135bdf77be2f5fbdb8b10abffde9f2a9ea1ea9f42b2199`.
- `H6_HTTP_TIMEOUT_LAYER`: **NOT_TESTED**; evidence hash `f1c7ce7ed00368f27bb6d02213585908cb1ee25b55a74e67fa6be4fdc9e69448`.
- `H7_OLLAMA_RUNTIME`: **NOT_SUPPORTED**; evidence hash `15ba49dd9dc4e0cdb2dad5261d650853339dae7a6cd905f155702e0e8810f316`.
- `H8_HARNESS_RESPONSE_PATH`: **NOT_SUPPORTED**; evidence hash `d84c72ceaf2699606f2f266b4d1af4c2d44b46e1fe8b663f46b7476d14fefa6c`.
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
