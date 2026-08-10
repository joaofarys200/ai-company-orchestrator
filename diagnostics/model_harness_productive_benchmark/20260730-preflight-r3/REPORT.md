# Qwen3.5 9B Productive ModelHarness Benchmark

- Modelo: `qwen3.5:9b`
- Missoes completas: 3/4 (75.0%)
- Respostas estruturais validas: 24/24 (100.0%)
- Integridade do codigo fonte: inalterada
- Promocao: FAIL

## Cenarios

### S1_INSPECTION - Inspecao read-only

- Conclusao: 1/1 (100.0%)
- Finish prematuro: 0
- Tools invalidas: 0
- Repeticoes: 0
- Falhas de schema: 0
- Passos medios: 4.0
- Latencia media: 22.935s

### S2_SIMPLE_EDIT - Alteracao simples validada

- Conclusao: 1/1 (100.0%)
- Finish prematuro: 0
- Tools invalidas: 0
- Repeticoes: 0
- Falhas de schema: 0
- Passos medios: 7.0
- Latencia media: 35.046s

### S3_VALIDATION_FAILURE - Falha, correcao e reteste

- Conclusao: 0/1 (0.0%)
- Finish prematuro: 0
- Tools invalidas: 1
- Repeticoes: 0
- Falhas de schema: 0
- Passos medios: 6.0
- Latencia media: 30.105s

### S4_STATEFUL_DISCIPLINE - Disciplina stateful

- Conclusao: 1/1 (100.0%)
- Finish prematuro: 0
- Tools invalidas: 0
- Repeticoes: 0
- Falhas de schema: 0
- Passos medios: 7.0
- Latencia media: 34.442s

## Metricas Globais

- premature_finish: 0
- invalid_tools: 1
- repeated_calls: 0
- schema_failures: 0
- validation_runs: 3
- failed_validations: 1
- corrections_after_failure: 0
- false_successes: 0
- total_steps: 24
- total_latency_ms: 121886
- input_tokens: 15639
- output_tokens: 1812

## Criterios de Promocao

- completion_rate_at_least_80: False
- all_responses_structurally_valid: True
- zero_false_successes: True
- zero_incomplete_successes: True
- source_integrity_unchanged: True
- promoted: False
