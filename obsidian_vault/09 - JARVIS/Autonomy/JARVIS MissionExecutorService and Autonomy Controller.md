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
O `MissionExecutorService` e o `MissionAutonomyController` formam o motor central de despacho e supervisÃ£o do ciclo de vida das missÃµes, coordenando a execuÃ§Ã£o de passos sequenciais e paralelos entre os agentes especialistas.

---

## 2. Responsibilities
- DecomposiÃ§Ã£o de tarefas em Grafos AcÃ­clicos Dirigidos (DAG).
- Encaminhamento dinÃ¢mico de passos para agentes (Clara, Devon, Alex, Quinn).
- FiscalizaÃ§Ã£o de timeouts de passos e quotas de consumo de tokens.
- Circuit breaking e congelamento em `PAUSED_WAITING_HUMAN` quando ocorrem anomalias repetitivas.

---

## 3. Inputs & Outputs
- **Inputs**: Pedidos de missÃ£o de alto nÃ­vel enviados pelo utilizador (via UI ou voz).
- **Outputs**: Ordem de despacho de ferramentas, passos executados, relatÃ³rios de progresso via WebSocket.

---

## 4. State Management & Invariants
- Uma missÃ£o ativa transita por estados rigorosos da FSM: `PENDING` $\rightarrow$ `PLANNING` $\rightarrow$ `EXECUTING` $\rightarrow$ `VALIDATING` $\rightarrow$ `COMPLETED`.

---

## 5. Dependencies
- [`agents/mission_executor.py`](file:///c:/Users/joaor/Desktop/JarvisOS/agents/mission_executor.py)
- [`agents/mission_autonomy.py`](file:///c:/Users/joaor/Desktop/JarvisOS/agents/mission_autonomy.py)
- [`agents/swarm.py`](file:///c:/Users/joaor/Desktop/JarvisOS/agents/swarm.py)

---

## 6. Failure Modes & Recovery
- **Failure**: InterrupÃ§Ã£o repentina de processo ou travamento em loop infinito de chamadas de ferramentas.
- **Recovery**: O watchdog recupera o Ãºltimo checkpoint e ativa reflexÃ£o ou pausa com notificaÃ§Ã£o humana.

---

## 7. Security Boundaries
- Controla os nÃ­veis de autorizaÃ§Ã£o: operaÃ§Ãµes que alteram o sistema anfitriÃ£o ou branches protegidas exigem aprovaÃ§Ã£o explÃ­cita.

---

## 8. Evidence Produced & Tests
- **Evidence**: Grafo de execuÃ§Ã£o persistido, registos de telemetria com W3C trace IDs.
- **Tests**: `tests/test_mission_executor.py`, `tests/test_mission_autonomy.py`.

---

## 9. Related Concepts
- [[JARVIS Mission State Machine and Autonomy]]
- [[JARVIS MissionRecoveryWatchdog and Crash Recovery]]
- [[JARVIS Autonomous Agent Hierarchy]]

