# JARVIS OS — Fase 13: Mission Graph Intelligence & Adaptive Planning

## 1. Visão Geral & Arquitetura Determinística

A Fase 13 introduz o motor de planeamento adaptativo e inteligência de grafos de missão (`AdaptivePlanningEngine`, `AdaptivePlanningValidator`, `MissionAdaptationProposal`, `Observation`) integrado com o `MissionLifecycleOrchestrator` e `TaskGraph`.

### Invariante Fundamental de Segurança
> **NUNCA PERMITIR: LLM → DIRECT GRAPH MUTATION.**  
> O modelo de linguagem propõe alterações exclusivamente de forma **declarativa**.  
> O único fluxo transacional permitido é:
> 
> $$\text{OBSERVATION} \longrightarrow \text{ADAPTATION PROPOSAL} \longrightarrow \text{VALIDATE} \longrightarrow \text{ACCEPT / REJECT} \longrightarrow \text{ATOMIC APPLY} \longrightarrow \text{GRAPH VERSION } + 1$$

---

## 2. Taxonomia de Observações e Gatilhos

### Fontes de Observação (`ObservationSource`)
- `TEST`: Falhas ou regressões em testes unitários, testes de integração ou suites E2E.
- `BUILD`: Erros de compilação, problemas de tipagem TypeScript/mypy ou falhas de transpilação.
- `RUNTIME`: Exceções de runtime em produção/execução, OOM (Out-of-Memory), timeouts de socket.
- `HUMAN_FEEDBACK`: Diretivas de operador, revisões manuais ou alterações de requisitos de negócio.
- `ECONOMIC`: Eventos do motor económico, falhas de faturação ou orçamentos excedidos.
- `SECURITY`: Bloqueios pelo Sentinel, deteção de vetores de ataque ou tentativas de fuga de sandbox.

### Gatilhos de Adaptação (`AdaptationTrigger`)
- `RUNTIME_FAILURE`
- `TEST_FAILURE`
- `BUILD_FAILURE`
- `HUMAN_FEEDBACK`
- `ARCHITECTURE_DISCOVERY`
- `REQUIREMENT_CHANGE`
- `NEW_REQUIREMENT`
- `UNEXPECTED_COMPLEXITY`
- `BLOCKED_DEPENDENCY`
- `RESOURCE_EXHAUSTION`
- `GATE_REJECTION`
- `PERFORMANCE_DEGRADATION`
- `SECURITY_FINDING`
- `MODEL_UNCERTAINTY`
- `ECONOMIC_CONSTRAINT`
- `ENVIRONMENT_MISMATCH`
- `DEPENDENCY_DEPRECATION`
- `DEADLOCK_DETECTED`
- `PREMISE_INVALIDATED`
- `EXTERNAL_SERVICE_FAILURE`

---

## 3. Decisões do Avaliador de Plano (`PlanEvaluationDecision`)

1. `KEEP_PLAN`: Nenhuma alteração estrutural necessária; execução do plano prossegue normalmente.
2. `ADAPT_PLAN`: Mutação localizada no grafo de tarefas (inserção, substituição, reordenação ou cancelamento de tarefas num ramo específico).
3. `REPLAN`: Mudança estrutural profunda (ex: invalidation de premissas arquiteturais); o grafo é re-estruturado preservando estritamente nós com status `COMPLETED`.
4. `HALT_FOR_OPERATOR`: O orçamento de adaptação foi esgotado ou foram detetados riscos críticos; execução interrompida com pedido de aprovação humana.
5. `ABORT_MISSION`: Falhas fatais irrecuperáveis ou violações graves de invariantes determinísticos.

---

## 4. Salvaguardas Determinísticas & Regras de Rejeição

| Código de Erro | Condição de Bloqueio |
|---|---|
| `REJECTED_STALE_GRAPH_VERSION` | `base_graph_version != current_graph_version` (Controlo de Concorrência Otimista). |
| `REJECTED_CYCLE_DETECTED` | Deteção de ciclo no grafo de ensaio (`trial_dag`) via DFS. |
| `COMPLETED_TASK_REGRESSION_FORBIDDEN` | Tentativa de remover ou regredir tarefa em status `COMPLETED` sem justificativa explícita. |
| `RUNNING_TASK_MUTATION_FORBIDDEN` | Tentativa de mutação direta sobre tarefa com execução ativa (`RUNNING`). |
| `REJECTED_STRATEGY_OSCILLATION` | Tentativa de re-propor estratégia com fingerprint idêntico ou ciclo alternado ($A \to B \to A$). |
| `BUDGET_EXCEEDED` | Limite de adaptações por plano (`max_plan_adaptations`) ultrapassado. |
| `REPLAN_BUDGET_EXCEEDED` | Limite de replans globais (`max_replans`) ultrapassado. |
| `CHURN_LIMIT_EXCEEDED` | Total de nós adicionados/removidos excede `max_graph_churn`. |
| `SCOPE_ESCALATION_FORBIDDEN` | Pedido de acesso fora da sandbox (`System32`, `/etc/shadow`, comandos destrutivos). |
| `ECONOMIC_GATE_BYPASS_FORBIDDEN` | Tentativa de contornar portões de aprovação em missões financeiras (`is_economic=True`). |
| `ECONOMIC_EVIDENCE_REMOVAL_FORBIDDEN` | Remoção de critérios ou evidências de validação em missões financeiras. |
| `ECONOMIC_PHANTOM_REVENUE_FORBIDDEN` | Invenção sintética de receita ou liquidações não verificadas. |

---

## 5. Protocolo WebSocket Live (Contratos e Mensagens)

- **`mission_plan_evaluate`**:
  - Envia observações estruturadas (`Observation`) e contexto de alterações.
  - Resposta: `mission_plan_evaluation_result` contendo `decision`, `reason`, `trigger`, `metrics`.
- **`mission_adaptation_propose`**:
  - Envia proposta declarativa `MissionAdaptationProposal` com `base_graph_version`.
  - Resposta: `mission_adaptation_proposal_result` com status `success: true/false`, mensagem e `AdaptationRecord` auditável.
- **`mission_adaptation_get_history`**:
  - Devolve todos os registos persistidos em `adaptations/*.json`.

---

## 6. Resultados de Verificação e Benchmarks Empíricos

- **Pytest Fase 13**: 30/30 testes verdes (100% PASS em 1.11s).
- **Pytest Fase 12 Regressão**: 23/23 testes verdes (100% PASS em 4.94s).
- **WebSocket E2E Scorecard**: 10/10 requisitos validados ao vivo em `ws://127.0.0.1:8001/?token=local-dev-token`.
- **Throughput de Fingerprinting de Estratégia**: 52,315 hashes SHA-256/segundo (19.12 µs/operação).
- **Latência de Validação & Trial DAG (50 nós + 5 adicionados)**: 0.199 ms/operação.
- **Latência de Replan Massivo (100 nós, 70 removidos, 20 adicionados)**: 0.618 ms/operação.
- **FIRST_REAL_LIMIT (Fase 13 Original)**: `RecursionError: Python recursive call stack limit exceeded (1000 frames) at reverse linear chain depth >= 1000 nodes during TaskGraph cycle detection` — **TOTALMENTE RESOLVIDO na Fase 13.1**.

---

## 7. Graph Validation Scalability (Fase 13.1)

### 7.1 Eliminação do FIRST_REAL_LIMIT da Fase 13
Na Fase 13, identificou-se o limite estrutural `RecursionError: maximum recursion depth exceeded (1000 frames)` quando uma cadeia linear com $\ge 1000$ tarefas era inserida em ordem inversa à topológica (devido ao DFS recursivo em `TaskGraph.validate()` e `TaskGraph.topological_sort()`).

Na Fase 13.1, a dependência da call stack de recursão do interpretador Python foi totalmente eliminada com a substituição do DFS recursivo pelo **Algoritmo de Kahn Iterativo Determinístico**:
1. **Controlo de In-Degree e Adjacência Direta**: Cálculo estático de pré-requisitos para cada nó do grafo.
2. **Min-Heap com Desempate Lexicográfico Determinístico**: Fila de prioridades com chave `(-node.priority, node.task_id)` para ordenação reproduzível.
3. **Reconstrução Iterativa de Ciclos**: Se `len(order) < len(nodes)`, os nós com `in_degree > 0` contêm pelo menos um ciclo direcionado. O caminho fechado do ciclo é extraído iterativamente sem chamadas recursivas.
4. **Fonte Única de Verdade**: Unificação de `validate()` e `topological_sort()`, bem como do helper `MissionStateStore._validate_dag()`, que agora delegam para a mesma implementação iterativa O(V + E).
5. **Persistência em Lote de Entidades**: `MissionStateStore.create_work_packages_batch` eliminou a sobrecarga quadrática de I/O de disco ($O(N^2) \to O(N)$), permitindo decomposições de milhares de tarefas em segundos.

### 7.2 Resultados Empíricos de Escala (Fase 13.1)
- **1,000 nós lineares**: Validação em 4.03 ms | Topo sort em 3.92 ms | Memória de pico: 167.1 KB.
- **2,000 nós invertidos**: Validação em 8.90 ms | Topo sort em 8.25 ms | Memória de pico: 336.2 KB (Zero RecursionError).
- **5,000 nós lineares**: Validação em 22.04 ms | Topo sort em 20.84 ms | Memória de pico: 771.1 KB.
- **10,000 nós lineares / invertidos**: Validação em 47.50 ms | Topo sort em 48.63 ms | Memória de pico: 1.51 MB.
- **Ciclos Profundos (5,000 nós)**: Deteção e extração em 20.90 ms com isolamento auditável.
- **NOVO FIRST_REAL_LIMIT (Fase 13.1)**: `Local OS Disk I/O serialization limit on single-directory JSON file creation when N >= 25,000 individual files (NTFS MFT lock contention)` — **RESOLVIDO na Fase 13.2**.

---

## 8. Mission State Persistence Scalability & Storage Architecture (Fase 13.2)

Na Fase 13.2, foi resolvida a barreira física de 25.000 ficheiros individuais com o desacoplamento entre **Mission State** e **File-per-Entity**:
- **Abstração `MissionStatePersistence`**: Suporta backends `hybrid` (padrão), `sqlite`, `sharded` (64 shards CRC32) e `legacy`.
- **Modo Híbrido**: SQLite WAL para indexação $B$-Tree e transações ACID atómicas, sincronizando um manifesto legível `mission.json` na raiz da missão.
- **Escalabilidade Comprovada**:
  - 1.000 tarefas: 116 ms (116x mais rápido que o modo legacy de 13,5s).
  - 25.000 tarefas: 1.915 ms em 3 ficheiros (vs saturação NTFS da Fase 13.1).
  - 100.000 tarefas: 8.776 ms em 3 ficheiros, ocupando apenas 25,4 MB de disco.
  - Latência de lookup de tarefa $O(1)$: **1.30 ms** a 100.000 tarefas.
- **Documentação Detalhada**: Consultar [`docs/JARVIS_MISSION_STORAGE.md`](file:///c:/Users/joaor/Desktop/JarvisOS/docs/JARVIS_MISSION_STORAGE.md) para benchmarks completos, comparativos arquiteturais e guia de migração.
