# JARVIS OS — Phase 17 Benchmark Provenance Audit

**Data:** 2026-09-06  
**Status:** CONCLUÍDO  
**Auditor:** JARVIS OS Independent Verification Subagent  
**Alvo Auditado:** `docs/phase17_benchmark_results.json` e o gerador de benchmarks da Fase 17.

---

## 1. Executive Summary

A Fase 17 introduziu a arquitetura de **Hierarchical Swarm Federation** (`SwarmFederation`, `SubSwarmCoordinator`, `FederatedTaskScheduler`, `FederatedLeaseManager`, `FederatedResourceArbitrator`).

O relatório inicial da Fase 17 reportou throughputs superiores a 7.800–8.600 tasks/s para escalas de 32 a 512 agentes. Esta auditoria examina a proveniência exata destes números, o código executado, a metodologia de medição, eventuais fórmulas sintéticas ou distorções de cache, e classifica explicitamente cada valor reportado como `MEASURED`, `CALCULATED`, `SIMULATED` ou `HARDCODED`.

---

## 2. Respostas às 14 Perguntas Obrigatórias de Proveniência

### 1. Qual script gera o benchmark?
O ficheiro `docs/phase17_benchmark_results.json` foi gerado pelo script de execução da Fase 17 (`scratch/run_phase17_benchmarks.py`).

### 2. Qual código é realmente executado?
No script do benchmark, foram instanciadas e executadas as seguintes classes reais da base de código:
- `agents.swarm_coordinator.SwarmCoordinator` (para o baseline centralizado).
- `agents.swarm_federation.SwarmFederation` (para a coordenação federada).
- `agents.swarm_federation.SubSwarmCoordinator` (para a coordenação local em cada sub-swarm).
- `agents.swarm_federation.FederatedTaskScheduler` (para o particionamento hierárquico e distribuição de WorkPackages).
- `agents.swarm_federation.FederatedResourceArbitrator` (para verificação de path locks cross-swarm).
- `agents.swarm_federation.DeterministicSubSwarmPartitioner` (para particionamento determinístico de tarefas e agentes).
- `agents.task_graph.TaskGraph` e `agents.task_graph.TaskNode` (estruturas reais de DAG).

### 3. Usa `SwarmCoordinator` real?
**SIM.** No baseline centralizado, uma instância real de `SwarmCoordinator` geriu o registo de agentes, seleção de agentes (`select_agent_for_task`), aquisição de leases (`acquire_task_lease`), conciliação periódica (`reconcile_leases_and_failures`) e validação de resultados (`handle_agent_result`).

### 4. Usa `SubSwarmCoordinator` real?
**SIM.** Na arquitetura federada, instâncias reais de `SubSwarmCoordinator` governaram cada partição de 32 agentes, mantendo o seu próprio registo local, quotas locais, scheduler local e lease manager.

### 5. Usa `SwarmFederation` real?
**SIM.** A classe `SwarmFederation` coordenou a topologia hierárquica, a criação dos sub-swarms e o callback de eventos federados.

### 6. Usa `FederatedLeaseManager` real?
**SIM.** A gestão de leases locais e a verificação federada contra conflitos de caminhos partilhados decorreu via `FederatedResourceArbitrator` e `LeaseManager` local em cada sub-swarm.

### 7. Usa `FederatedTaskScheduler` real?
**SIM.** O escalonamento hierárquico dividiu as tarefas em `WorkPackage`s distribuídos aos sub-swarms.

### 8. Executa tasks reais?
**PARCIAL / SIMULADO NO PAYLOAD.**
- As tarefas eram instâncias reais de `TaskNode` organizadas num `TaskGraph` com dependências reais e metadados de caminhos (`path_scope`).
- As transições de estado (`PENDING` -> `RUNNING` -> `COMPLETED`) ocorreram de forma autêntica dentro do grafo e do `MissionStateStore`.
- **Contudo**, o corpo da tarefa (cálculo de ficheiros, AST parsing, chamadas I/O ou subprocessos) não foi executado externamente: o agente retornou um `AgentResult(status=SUCCESS, output={"status": "ok"})` instantâneo em memória.
- **Conclusão:** O benchmark mediu a **taxa máxima de coordenação, escalonamento, atribuição de leases e conciliação de estado** da infraestrutura, e **não** a latência de I/O de ferramentas externas.

### 9. Executa agentes reais?
**PARCIAL / IN-MEMORY OBJECTS.**
- Foram criados objetos reais `AgentInstance` com `AgentCapability`, registados nos `AgentRegistry` locais e centralizados.
- Não foram iniciados processos de SO separados nem chamadas a LLMs externos por cada agente; a execução ocorreu cooperativamente no event loop do asyncio.

### 10. Mede tempo real ou usa modelo analítico/simulação?
**TEMPO REAL MEDIDO.**
- O tempo total de relógio (`duration_s`) e as durações de seleção de agentes e conciliação foram medidos diretamente com `time.perf_counter()`.
- O throughput foi medido através de:  
  Throughput = completed_tasks / total_time_s

### 11. Existem valores hardcoded?
**NÃO nos throughputs ou tempos.**  
Todos os números de throughput (`11159.22`, `8645.08`, `8492.04`, `8467.59`, `7809.86`, `7833.80`) e latências foram o produto direto das medições de `time.perf_counter()`.  
**EXCEÇÃO:** No baseline centralizado, o campo `lease_overhead_ms` foi calculado por uma fórmula heurística sintética: `round(coord.metrics.total_expired_leases * 0.1, 2)`.

### 12. Existem fórmulas que geram throughput em vez de medir execução?
- O throughput em si **não** foi gerado por fórmula sintética, foi medido por tarefas concluídas / tempo real decorrido.
- Os campos comparativos derivados (`speedup = f_tput / c_tput`, `efficiency = speedup / sub_swarms` e `coordination_reduction_pct`) foram **CALCULATED**.

### 13. Existem mocks/stubs/fake clocks?
- **Fake clocks:** NÃO. Foi usado `time.perf_counter()`.
- **Stubs:** SIM, o payload do agente (`AgentResult(output={"status": "ok"})`) era um stub em memória que eliminou o tempo de I/O, isolando a coordenação pura.

### 14. Existe warm-up ou caching que possa distorcer a medição?
**SIM.**
- As escalas de 32, 64, 128, 256 e 512 foram executadas sequencialmente no mesmo processo Python.
- As execuções de 128, 256 e 512 beneficiaram de bytecode Python em memória, caches de imports e heap pré-alocada.
- O consumo de memória reportado como `0.0 MB` em algumas escalas decorreu da reutilização de memória interna do alocador do Python (`pymalloc`) após `gc.collect()`, sem devolução imediata ao SO.
- Apenas uma única execução foi realizada para cada escala no benchmark original (sem repetições estatísticas ou desvio padrão).

---

## 3. Classificação de Proveniência dos Resultados Originais

| Métrica Original | Valor Reportado (Exemplo) | Proveniência | Justificação |
| :--- | :--- | :--- | :--- |
| `duration_s` | `0.0191 s` | **MEASURED** | Medido diretamente via `time.perf_counter()`. |
| `throughput` (Centralized 32) | `11159.22 tasks/s` | **MEASURED** | `completed / duration_s` medido em tempo real. |
| `throughput` (Federated 512) | `7833.80 tasks/s` | **MEASURED** | `completed / duration_s` medido em tempo real. |
| `latencies_ms.p50, p95, p99` | `0.0477 ms`, `0.0539 ms` | **MEASURED** | Quantis calculados a partir das amostras medidas com `time.perf_counter()`. |
| `coordination_overhead_ms` | `10.08 ms` | **MEASURED** | Soma dos tempos medidos nas rotinas de coordenação e conciliação. |
| `lease_overhead_ms` (Centralized) | `0.0 ms` (ou $0.1 \times \text{leases}$) | **SIMULATED** | Estimativa heurística baseada no número de leases expiradas. |
| `memory_mb` | `0.00` a `1.81 MB` | **MEASURED (DISTORTED)** | Delta de RSS medido via `psutil`, mas distorcido por pools pymalloc no mesmo processo. |
| `speedup` | `6.1x` | **CALCULATED** | Throughput_fed / Throughput_cent. |
| `efficiency` | `0.38` | **CALCULATED** | Speedup / SubSwarms. |
| `coordination_reduction_pct`| `90.84%` | **CALCULATED** | 1.0 - (Overhead_fed / Overhead_cent). |
| Task Payload Execution | `AgentResult(output={"status": "ok"})` | **SIMULATED** | O payload não executou I/O nem transformações reais de ficheiros no disco. |

---

## 4. Requisitos para o Benchmark Independente (Fase 17.1)

Para garantir integridade inquestionável, a Fase 17.1 institui:
1. **Runner Independente (`scripts/phase17_independent_benchmark.py`):**
   - Não importa resultados anteriores nem partilha estado.
   - Realiza trabalho computacional real em cada tarefa (cálculo de hashes criptográficos e validação de payload).
   - Mede explicitamente o ciclo de vida completo de cada agente: `tasks_assigned`, `tasks_completed`, `tasks_failed`, `lease_count`, `execution_count`.
   - Separa **Cold Run** (processo isolado sem caches prévias) de **Warm Run**.
   - Executa **5 repetições independentes** para cada escala (32, 64, 128, 256, 512) calculando: média, mediana, desvio padrão, min, max, p50, p95, p99.
   - Decompõe a latência em: `scheduling_latency`, `lease_latency`, `execution_latency`, `coordination_latency`, `federation_latency` e `end_to_end_latency`.
   - Testa a fronteira empírica do sistema (`512 -> 768 -> 1024 -> 1536 -> 2048`) identificando o `FIRST_REAL_LIMIT`.
   - Grava os resultados de forma isolada em `docs/phase17_independent_benchmark_results.json` mantendo `docs/phase17_benchmark_results.json` intacto.
