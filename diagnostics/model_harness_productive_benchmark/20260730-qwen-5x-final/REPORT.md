# Qwen3.5 9B Productive ModelHarness Benchmark

- Modelo: `qwen3.5:9b`
- Missoes completas: 10/20 (50.0%)
- Respostas estruturais validas: 100/100 (100.0%)
- Integridade do codigo fonte: inalterada
- Promocao: FAIL

## Cenarios

### S1_INSPECTION - Inspecao read-only

- Conclusao: 5/5 (100.0%)
- Finish prematuro: 0
- Tools invalidas: 0
- Repeticoes: 0
- Falhas de schema: 0
- Passos medios: 4.0
- Latencia media: 22.437s

### S2_SIMPLE_EDIT - Alteracao simples validada

- Conclusao: 5/5 (100.0%)
- Finish prematuro: 0
- Tools invalidas: 0
- Repeticoes: 0
- Falhas de schema: 0
- Passos medios: 7.0
- Latencia media: 33.395s

### S3_VALIDATION_FAILURE - Falha, correcao e reteste

- Conclusao: 0/5 (0.0%)
- Finish prematuro: 0
- Tools invalidas: 5
- Repeticoes: 0
- Falhas de schema: 0
- Passos medios: 7.0
- Latencia media: 31.569s

### S4_STATEFUL_DISCIPLINE - Disciplina stateful

- Conclusao: 0/5 (0.0%)
- Finish prematuro: 0
- Tools invalidas: 5
- Repeticoes: 0
- Falhas de schema: 0
- Passos medios: 2.0
- Latencia media: 7.818s

## Metricas Globais

- premature_finish: 0
- invalid_tools: 10
- repeated_calls: 0
- schema_failures: 0
- validation_runs: 10
- failed_validations: 0
- corrections_after_failure: 0
- false_successes: 0
- total_steps: 100
- total_latency_ms: 474317
- input_tokens: 62460
- output_tokens: 7425

## Criterios de Promocao

- completion_rate_at_least_80: False
- all_responses_structurally_valid: True
- zero_false_successes: True
- zero_incomplete_successes: True
- source_integrity_unchanged: True
- promoted: False
