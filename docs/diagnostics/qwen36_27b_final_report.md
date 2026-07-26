# Encerramento do Qwen3.6:27B e otimização controlada do Qwen3.5:9B

Data: 21-07-2026 (Europe/Lisbon)

## Decisão

**B — aplicar uma otimização de configuração limitada ao ProjectBuilder.**

O modelo de produção permanece `qwen3.5:9b`. O único ajuste aplicado foi:

```env
PROJECT_BUILDER_PLAN_CONTEXT_TOKENS=8192
```

Não foi introduzido outro modelo, não foi alterada a arquitetura e a variante compactada do prompt não foi adotada.

## 1. Encerramento do modelo experimental

Estado antes da remoção:

- Ollama: `0.32.1`;
- `qwen3.6:27b`: ID `a50eda8ed977`, tamanho apresentado `17 GB`;
- `qwen3.5:9b`: ID `6488c96fa5fa`, tamanho apresentado `6.6 GB`;
- nenhum modelo ativo em `ollama ps`;
- espaço livre inicial: `548 828 549 120` bytes (`511,136 GiB`).

Foi executado exclusivamente `ollama rm qwen3.6:27b`, com exit code `0` e saída `deleted 'qwen3.6:27b'`.

Espaço libertado:

- antes: `548 828 549 120` bytes;
- depois: `566 249 070 592` bytes;
- libertado: `17 420 521 472` bytes (`16,224 GiB`).

Após a remoção, `ollama list` manteve `qwen3.5:9b` e os restantes modelos previamente existentes. `ollama ps` ficou vazio.

## 2. Blobs e manifests

O manifesto `C:\Users\joaor\manifests\registry.ollama.ai\library\qwen3.6\27b` deixou de existir.

Também deixaram de existir os dois blobs conhecidos do candidato:

- `sha256-83c54730a5fea8a0958598c01617c1419c431e93b33bacf980b49a420c798926`;
- `sha256-728c795c776272002ed455cf94ef825cbbe4cc04c9a925a1a78933bbf0c2b63b`.

O manifesto de `qwen3.5:9b` permanece presente. Não foram apagados blobs manualmente nem foi removida a pasta global de modelos.

## 3. Preservação da experiência anterior

Confirmado antes da remoção:

- [scripts/qwen36_27b_validation.py](/C:/Users/joaor/Desktop/ai-company-orchestrator/scripts/qwen36_27b_validation.py:1), 53 215 bytes;
- `scratch/qwen36-27b-validation/`, 38 ficheiros, 1 480 129 bytes;
- manifesto, resultados JSONL, métricas, outputs, hashes, ambiente e artefactos de testes preservados.

Os resultados desta fase foram gravados em `scratch/qwen36-27b-final-closure/`. Não foram copiados modelos ou dumps binários para o repositório.

## 4. Configuração de produção

O modelo efetivo continua:

```env
OLLAMA_MODEL=qwen3.5:9b
```

Estado anterior conhecido:

- data: `2026-07-06T12:36:32+01:00`;
- SHA-256: `2E19C6D3683F77E50AC2A7BF6A6CF2DB0D9D461BEA96B072D3AAA539425A2D38`.

Estado após esta fase:

- data: `2026-07-21T15:34:47+01:00`;
- SHA-256: `403714674A2FE5761EF7F5FEC18617471C8FC3D8294A86DE9FE424516C286989`;
- motivo: adição explícita de `PROJECT_BUILDER_PLAN_CONTEXT_TOKENS=8192`.

O runtime confirmou `model=qwen3.5:9b`, `num_ctx=8192`, `max_output_tokens=16384`, `keep_alive=15m` e timeouts `{connect:5, read:300, write:15, pool:5}`.

## 5. Baseline do Qwen3.5:9B

Opções comuns do baseline: `temperature=0`, `seed=1518`, `think=false`, `top_k=20`, `top_p=0.95`, `min_p=0`, `presence_penalty=1.5`, `repeat_penalty=1`, `num_ctx=32768`, `keep_alive=15m`.

| Teste | Resultado | Tempo | Prompt tok/s | Geração tok/s |
|---|---|---:|---:|---:|
| Smoke | `Lisboa`, correto | 13,312 s | 61,442 | 20,389 |
| Instruction, 5 execuções | 5/5 `Rápido, seguro, estável.` | média 2,519 s | média 724,912 | média 18,396 |
| Structured JSON | válido, schema válido, referências válidas | 19,109 s | 281,936 | 16,703 |
| Plano de agentes | JSON/schema/dependências válidos; score 99/100 | 233,797 s | 612,799 | 16,270 |

O plano de agentes cobriu 14/15 pontos; a única violação foi `coverage:14/15`. Não houve thinking visível.

Memória do baseline:

- RAM usada de pico: aproximadamente 10,76–10,84 GiB;
- RAM livre mínima: aproximadamente 4,87–4,95 GiB;
- VRAM de pico: 7 025–7 032 MiB;
- CPU média: 18,38% no smoke, 20,41% nas instruções e 47,96% no JSON;
- CPU máxima: 63,4%;
- não houve paginação extrema nem erro CUDA.

## 6. Contexto real utilizado

Foram medidas cinco missões pequenas, cinco médias, cinco grandes e cinco entradas focais, usando as mensagens e o schema reais do ProjectBuilder. Os valores são `prompt_eval_count` do Ollama.

| Categoria | n | mínimo | mediana | p90 | p95 | máximo |
|---|---:|---:|---:|---:|---:|---:|
| Missões pequenas | 5 | 478 | 480 | 481 | 481 | 482 |
| Missões médias | 5 | 486 | 488 | 489 | 489 | 497 |
| Missões grandes | 5 | 511 | 525 | 528 | 528 | 551 |
| Correção focal | 5 | 179 | 181 | 183 | 183 | 204 |

Histórico real preservado nos journals: prompt inicial máximo 2 939 bytes, prompt focal efetivo máximo 9 733 bytes e resposta máxima 6 260 bytes. Não houve truncamento de entrada nas amostras.

## 7. Matriz de `num_ctx`

Foram testados isoladamente `8192`, `16384` e `32768`, mantendo constantes temperatura, seed, thinking, top-k, top-p e streaming.

| Contexto | Smoke | JSON | Plano curto | Plano médio* | Plano grande* | Focal |
|---:|---:|---:|---:|---:|---:|---:|
| 8192 | 11,704 s | 12,531 s | 22,140 s | 42,047 s | 42,266 s | 4,297 s |
| 16384 | 11,078 s | 14,750 s | 27,250 s | 49,359 s | 50,250 s | 4,938 s |
| 32768 | 12,672 s | 18,625 s | 39,515 s | 62,188 s | 61,906 s | 5,766 s |

\* Os planos médio/grande desta matriz usaram experimentalmente `num_predict=1024`; terminaram por limite de saída, não por falta de contexto.

Uma repetição grande com `num_predict=4096` produziu JSON completo nos três contextos:

| Contexto | Tempo | Completion tokens | JSON | Validação semântica |
|---:|---:|---:|---|---|
| 8192 | 100,094 s | 2 244 | válido | falhou em componentes/mapeamentos |
| 16384 | 130,437 s | 2 503 | válido | falhou em persistence/frontend |
| 32768 | 183,094 s | 2 855 | válido | falhou em componentes/mapeamentos |

O requester real do ProjectBuilder em `8192` executou duas chamadas, incluindo structured output focal, sem erro de contexto ou timeout. O teste equivalente em `32768` também completou as duas chamadas; ambos falharam por validação semântica do plano, não por truncamento.

Runner medido pelo Ollama:

- `8192`: 6 420 147 727 bytes;
- `32768`: 7 393 205 284 bytes;
- redução: 973 057 557 bytes, aproximadamente 0,91 GiB.

Critério: `8192` foi adotado por reduzir memória e latência sem truncamento de entrada, sem quebra de schema e sem aumento demonstrado de falhas relativamente ao controle.

## 8. `keep_alive`

| Configuração | Cold | Warm imediato | Comportamento |
|---|---:|---:|---|
| `0` | ~10,94 s | ~11,41 s | recarrega a cada chamada; modelo libertado em ~1 s |
| `5m` | ~11,22 s | ~1,64 s | reutilização eficaz |
| `15m` | ~11,16 s | ~1,58 s | reutilização eficaz |

O valor existente `15m` já é adequado para uso interativo e não foi alterado. O cenário esporádico foi simulado por stop explícito e confirmou cold start semelhante.

## 9. Structured outputs

O ProjectBuilder já utiliza os mecanismos nativos do Ollama:

- geração inicial: `format="json"`;
- correção focal v2: `format=<JSON Schema dinâmico>`;
- parser JSON local;
- validação schema, semântica, segurança e eficácia;
- fallback textual não foi introduzido;
- a segunda chamada focal continua limitada ao protocolo existente.

As chamadas gerais de agentes usam tool calling e não foram convertidas automaticamente para JSON Schema. A coding session pede JSON por contrato textual, mas continua sem migração global.

## 10. Thinking

Foi confirmado `think=false` no ProjectBuilder, correção focal, `query_ollama_with_tools`, coding session e harness. Não houve thinking visível e nenhum conteúdo de thinking foi exposto ao frontend.

## 11. Auditoria de parâmetros e timeouts

| Parâmetro | Valor efetivo | Local |
|---|---:|---|
| Modelo | `qwen3.5:9b` | `.env`/ProjectBuilder |
| Base URL ProjectBuilder | `http://127.0.0.1:11434` | `project_builder.py` |
| Base URL provider | `OLLAMA_BASE_URL` ou `http://localhost:11434` | provider Ollama |
| Temperatura ProjectBuilder | `0` | payload hardcoded |
| Top-p ProjectBuilder | `0.8` | payload hardcoded |
| `num_predict` | 16 384 | `PROJECT_BUILDER_PLAN_MAX_OUTPUT_TOKENS` |
| `num_ctx` | 8 192 | `.env`, novo ajuste comprovado |
| `keep_alive` | `15m` | default ProjectBuilder |
| Streaming ProjectBuilder | `true` | contrato de geração |
| Structured output inicial | `json` | contrato Ollama |
| Structured output focal | JSON Schema dinâmico | `project_builder_focal_correction_v2` |
| Think | `false` | payload Ollama |
| Connect/read/write/pool | `5/300/15/5` s | `PlanTimeoutConfig` |
| Tool calling timeout | 120 s | `agents/orchestrator/__init__.py` |
| Coding session timeout | 120 s | `intelligence/coding_session.py` |

Os timeouts existentes acomodaram o `qwen3.5:9b`; não foram aumentados para esconder hangs nem reduzidos abaixo dos valores observados.

## 12. Auditoria e A/B de prompt

Foi criada apenas em `scratch` uma variante experimental que preservou schema, agentes e regras materiais.

| Variante | Prompt tokens | Redução | n | JSON válido | Validação semântica | Tempo médio |
|---|---:|---:|---:|---:|---:|---:|
| Original | 498 | — | 10 | 0/10 (limite experimental 1024) | 0/10 | 41,928 s |
| Compacta | 446 | 10,4% | 10 | 10/10 | 0/10 | 19,500 s |

As duas variantes foram determinísticas, mas nenhuma produziu plano semanticamente válido nesta missão. A compactação não foi aplicada.

## 13. Correção focal v2

Os testes existentes foram preservados e executados. A suite focal v2 executada com shim de coleção passou `13/13`.

Os quatro cenários cobertos são dependência inexistente, owner inválido, critério de aceitação vazio e campo obrigatório em falta. Os testes confirmam correção focal, preservação de IDs/tarefas válidas, envelope JSON/schema, ausência de reparação global, máximo de duas chamadas e ausência de terceira chamada.

O requester real em `8192` enviou o schema dinâmico `project_builder_focal_correction_schema_v2` na segunda chamada.

## 14. Concorrência

Pedidos curtos com `num_ctx=8192`:

| Concorrência | Sucesso | Tempo total |
|---:|---:|---:|
| 1 | 1/1 | 8,110 s (cold) |
| 2 | 2/2 | 1,750 s (warm) |
| 3 | 3/3 | 2,031 s (warm) |

Não foram alterados limites globais. A concorrência elevada continua fora do escopo.

## 15. Testes automatizados

- `python -m py_compile scripts\\qwen36_27b_validation.py`: passou;
- `git diff --check`: passou;
- `pytest -q --ignore=tests\\test_project_builder_focal_v2.py`: `378 passed`, 14 warnings;
- `test_project_builder_focal_v2.py` separado com shim: `13 passed`;
- `pytest -q` sem shim: falha de coleção preexistente `ModuleNotFoundError: tests.test_project_builder_correction_effectiveness`;
- total de testes executáveis: `391 passed`.

Os 14 avisos são de depreciação do `torch.jit.script_method` e não estão relacionados com o modelo.

## 16. Artefactos

Criados nesta fase:

- este relatório;
- a linha de configuração no `.env`;
- resultados ignorados em `scratch/qwen36-27b-final-closure/`.

Os testes criaram 1 log e 32 runs novos; foram movidos, sem eliminação irreversível, para `scratch/qwen36-27b-final-closure/pytest-artifacts-final/`. Os índices preexistentes `workspace/.jarvis/projects/task-app/project_context.json` e `symbols_index.json` foram atualizados pela suite e copiados para o mesmo arquivo. Não foram removidos journals históricos nem workspaces existentes.

## 17. Arquitetura e modelo

Não foram alterados ProjectBuilder, Alex, Clara, Devon, Quinn, Mission Executor, providers, API, frontend, WebSockets, protocolo da Arena, materialização transacional, schema principal ou correção focal v2.

Não foi descarregado outro modelo. O `qwen3.6:27b` foi o único modelo removido. `qwen3.5:9b` continua a ser o modelo principal.

## 18. Recomendação final

Manter `qwen3.5:9b`, `PROJECT_BUILDER_PLAN_CONTEXT_TOKENS=8192` limitado ao ProjectBuilder e `keep_alive=15m`.

Não adotar a compactação do prompt. Não reabrir a investigação AirLLM/modelos nesta fase. Reavaliar `8192` apenas se aparecerem planos reais próximos do limite de contexto ou sinais de truncamento.
