# Qwen3.5-9B vs Qwopus3.5-9B-v3 ProjectBuilder Benchmark

## 1. Resumo executivo
Decisao: `QWOPUS_NO_MATERIAL_IMPROVEMENT`.
Benchmark isolado com dois casos, quatro chamadas totais e sem alteracoes produtivas.

## 2. Modelos
Qwen: `qwen3.5:9b`; Qwopus: `hf.co/Jackrong/Qwopus3.5-9B-v3-GGUF:Q4_K_M`. Ambos permaneceram instalados.

## 3. Hardware e memória
A evidencia bruta de `ollama list`, `ollama show`, `ollama ps`, sistema e GPU esta em `runtime/`.
Ollama reportou ambos como arquitetura qwen35/Q4_K_M; o Qwopus reportou 8.95B parametros e contexto suportado 262144.

## 4. Configuração controlada
Foram carregados sem reconstrução: payload, prompt e schema P1 do prototipo typed; prompt e schema K1 do protocolo compacto.
Contexto 8192, temperature 0, top_p 0.8, think false, stream false, timeout 180 s. A unica diferenca intencional entre pares foi `model`.
Diferencas de payload fora de model: P1 `[]`, compacto `[]`.

## 5. P1 — Qwen
{
  "case": "qwen",
  "done": true,
  "done_reason": "stop",
  "json_valid": true,
  "schema_valid": true,
  "operations_valid": true,
  "server_js_operation": false,
  "persistence_operation": false,
  "plan_operations": 6,
  "invented_paths": [],
  "validators_valid": false,
  "errors": [
    {
      "code": "PERSISTENCE_NOT_IMPLEMENTED",
      "field_path": "component_files.persistence",
      "message": "O componente persistence nao demonstra leitura e escrita duravel; estado em memoria nao e persistencia.",
      "expected_type": "mapped artifact implementing durable read and write operations",
      "received_type": "string",
      "offending_value": "no durable read/write mechanism in mapped persistence artifacts",
      "repairable": false,
      "suggestion": "Associa persistence a um artefacto existente que implemente leitura e escrita duravel.",
      "phase": "PLAN_SEMANTIC_VALIDATION",
      "file": "server.js",
      "line": null,
      "symbol": "",
      "target": "server.js",
      "expected": "mapped artifact implementing durable read and write operations",
      "actual": "no durable read/write mechanism in mapped persistence artifacts",
      "component": "persistence"
    }
  ],
  "persistence_detected_in_content": false,
  "accepted_operation_count": 6,
  "model": "qwen3.5:9b",
  "elapsed_seconds": 19.676,
  "content_sha256": "5925f58455857c47353bd07a6fbd42d8de79e12c504b6ccc1725d61afc7bfbce"
}

## 6. P1 — Qwopus
{
  "case": "qwopus",
  "done": true,
  "done_reason": "stop",
  "json_valid": true,
  "schema_valid": true,
  "operations_valid": false,
  "server_js_operation": false,
  "persistence_operation": false,
  "plan_operations": 10,
  "invented_paths": [],
  "validators_valid": false,
  "errors": [
    {
      "code": "INVALID_FIELD_TYPE",
      "message": "Invalid value for preview field: enabled",
      "details": {
        "field": "enabled"
      }
    }
  ],
  "model": "hf.co/Jackrong/Qwopus3.5-9B-v3-GGUF:Q4_K_M",
  "elapsed_seconds": 30.334,
  "content_sha256": "1e11d37c2d13e0d5e2ef9e1e667b3f33eeaa7732f627b6cc8bc77f10e86d947e"
}

## 7. Teste compacto — Qwen
{
  "case": "qwen",
  "done": true,
  "done_reason": "stop",
  "json_valid": true,
  "schema_valid": true,
  "operations_valid": false,
  "server_js_operation": true,
  "persistence_operation": true,
  "plan_operations": 4,
  "invented_paths": [],
  "validators_valid": false,
  "errors": [
    {
      "code": "HASH_MISMATCH",
      "message": "Transform hash does not match original content",
      "details": {
        "path": "server.js",
        "expected": "a1b2c3d4e5f67890abcdef1234567890fedcba9876543210abcdef1234567890",
        "actual": "5bdbf49b0e707cf43da23ffb5d642e9ed97f8e98e103a8a0c9a69e6ccca9bd31"
      }
    }
  ],
  "model": "qwen3.5:9b",
  "elapsed_seconds": 24.296,
  "content_sha256": "bcf98ea4a8345832ec718b12f2db9387553e6527016fe0e612c50bc0e5b83402"
}

## 8. Teste compacto — Qwopus
{
  "case": "qwopus",
  "done": true,
  "done_reason": "stop",
  "json_valid": true,
  "schema_valid": true,
  "operations_valid": false,
  "server_js_operation": true,
  "persistence_operation": true,
  "plan_operations": 4,
  "invented_paths": [],
  "validators_valid": false,
  "errors": [
    {
      "code": "HASH_MISMATCH",
      "message": "Transform hash does not match original content",
      "details": {
        "path": "server.js",
        "expected": "a1b2c3d4e5f6789012345678901234567890abcdef1234567890abcdef123456",
        "actual": "5bdbf49b0e707cf43da23ffb5d642e9ed97f8e98e103a8a0c9a69e6ccca9bd31"
      }
    }
  ],
  "model": "hf.co/Jackrong/Qwopus3.5-9B-v3-GGUF:Q4_K_M",
  "elapsed_seconds": 22.939,
  "content_sha256": "22ed02b467b880770fbdf0d88af290bc2f0b6a1b56140234364394a164d4b248"
}

## 9. Comparação
| Modelo/caso | done | JSON | schema | server.js | persistence op | validators | segundos |
|---|---:|---:|---:|---:|---:|---:|---:|
| P1 qwen3.5:9b | True | True | True | False | False | False | 19.676 |
| P1 hf.co/Jackrong/Qwopus3.5-9B-v3-GGUF:Q4_K_M | True | True | True | False | False | False | 30.334 |
| Compacto qwen3.5:9b | True | True | True | True | True | False | 24.296 |
| Compacto hf.co/Jackrong/Qwopus3.5-9B-v3-GGUF:Q4_K_M | True | True | True | True | True | False | 22.939 |

## 10. Validators
Cada resposta foi validada localmente e, quando a composição foi aceite, pelos validators reais reutilizados do prototipo. Nenhuma reparação foi feita.

## 11. Desempenho
Tempos, tokens, bytes, done_reason e estado de memoria estao nos metrics.json de cada caso e no diretório runtime.

## 12. Limitações
E um benchmark de uma fixture e de dois prompts fixos. Não mede capacidade geral. O teste não executa WP1/WP2, não materializa ficheiros, não inicia preview e não executa npm.

## 13. Decisão
`QWOPUS_NO_MATERIAL_IMPROVEMENT`.

## 14. Próximo passo
Não alterar o ProjectBuilder com base neste benchmark. Se Qwopus passar, repetir a confirmação apenas num benchmark independente autorizado; se falhar, manter o diagnóstico de protocolo/modelo.
