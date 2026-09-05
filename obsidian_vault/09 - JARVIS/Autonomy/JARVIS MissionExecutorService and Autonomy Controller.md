---
type: architecture
domain: jarvis
status: verified
source_type: JARVIS_INTERNAL
confidence: high
difficulty: advanced
tags:
  - jarvis
  - autonomy
  - executor
  - mission-executor
  - swarm
prerequisites:
  - "[[JARVIS Mission State Machine and Autonomy]]"
  - "[[Planner-Executor Agent Pattern]]"
related:
  - "[[JARVIS MissionStateStore and Persistence Engine]]"
  - "[[JARVIS Autonomous Agent Hierarchy]]"
  - "[[Agent Loop Detection and Circuit Breaker]]"
used_by:
  - "[[JARVIS System Architecture]]"
failure_modes:
  - "[[Lesson - Bounded Autonomy Escape in Subprocess Invocation]]"
implementation:
  - "[[JARVIS System Architecture]]"
sources:
  - title: JARVIS Codebase - agents/mission_executor.py and agents/mission_autonomy.py
    type: JARVIS_INTERNAL
    url: internal://agents/mission_executor.py
---

# âš¡ JARVIS MissionExecutorService and Autonomy Controller

## 1. Purpose
O `MissionExecutorService` e o `MissionAutonomyController` formam o motor central de despacho e supervisão do ciclo de vida das missões, coordenando a execução de passos sequenciais e paralelos entre os agentes especialistas.

---

## 2. Responsibilities
- Decomposição de tarefas em Grafos Acíclicos Dirigidos (DAG).
- Encaminhamento dinâmico de passos para agentes (Clara, Devon, Alex, Quinn).
- Fiscalização de timeouts de passos e quotas de consumo de tokens.
- Circuit breaking e congelamento em `PAUSED_WAITING_HUMAN` quando ocorrem anomalias repetitivas.

---

## 3. Inputs & Outputs
- **Inputs**: Pedidos de missão de alto nível enviados pelo utilizador (via UI ou voz).
- **Outputs**: Ordem de despacho de ferramentas, passos executados, relatórios de progresso via WebSocket.

---

## 4. State Management & Invariants
- Uma missão ativa transita por estados rigorosos da FSM: `PENDING` $\rightarrow$ `PLANNING` $\rightarrow$ `EXECUTING` $\rightarrow$ `VALIDATING` $\rightarrow$ `COMPLETED`.

---

## 5. Dependencies
- [`agents/mission_executor.py`](file:///c:/Users/joaor/Desktop/JarvisOS/agents/mission_executor.py)
- [`agents/mission_autonomy.py`](file:///c:/Users/joaor/Desktop/JarvisOS/agents/mission_autonomy.py)
- [`agents/swarm.py`](file:///c:/Users/joaor/Desktop/JarvisOS/agents/swarm.py)

---

## 6. Failure Modes & Recovery
- **Failure**: Interrupção repentina de processo ou travamento em loop infinito de chamadas de ferramentas.
- **Recovery**: O watchdog recupera o último checkpoint e ativa reflexão ou pausa com notificação humana.

---

## 7. Security Boundaries
- Controla os níveis de autorização: operações que alteram o sistema anfitrião ou branches protegidas exigem aprovação explícita.

---

## 8. Evidence Produced & Tests
- **Evidence**: Grafo de execução persistido, registos de telemetria com W3C trace IDs.
- **Tests**: `tests/test_mission_executor.py`, `tests/test_mission_autonomy.py`.

---

## 9. Related Concepts
- [[JARVIS Mission State Machine and Autonomy]]
- [[JARVIS MissionRecoveryWatchdog and Crash Recovery]]
- [[JARVIS Autonomous Agent Hierarchy]]

