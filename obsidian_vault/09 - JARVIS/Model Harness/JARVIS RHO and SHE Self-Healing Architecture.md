---
type: architecture
domain: jarvis
status: verified
source_type: JARVIS_INTERNAL
confidence: high
difficulty: advanced
tags:
  - jarvis
  - model-harness
  - rho
  - she
  - self-healing
prerequisites:
  - "[[Self-Healing Prompt Loops and Reflective Orchestration (RHO-SHE)]]"
  - "[[Model Harness Architecture]]"
related:
  - "[[Compiler Feedback and Test-Driven Self-Repair]]"
  - "[[Agent Loop Detection and Circuit Breaker]]"
used_by:
  - "[[JARVIS Model Harness Implementation]]"
failure_modes:
  - "[[Lesson - Unhandled Rate Limits and Context Explosion]]"
implementation:
  - "[[JARVIS Model Harness Implementation]]"
sources:
  - title: JARVIS Codebase - RHO and SHE Implementation Test Suites
    type: JARVIS_INTERNAL
    url: internal://tests/test_model_harness_rho_she.py
---

# 🧠 JARVIS RHO and SHE Self-Healing Architecture

## 1. Purpose
O **RHO (Reflective Healing Orchestrator)** e o **SHE (Self-Healing Engine)** formam o subsistema de auto-correção reflexiva do JARVIS OS, permitindo que os agentes diagnosticam e corrijam erros de execução de código e chamadas de ferramentas de forma autÃ´noma.

---

## 2. Responsibilities
- Interceptar exceções de execução em sandbox e saídas de erro de testes.
- Gerar sumários semânticos e hipóteses explicativas (*Reflective Diagnosis*) sem inflar o contexto.
- Injetar feedback corretivo direcionado no turno de reparação do agente Devon.
- Fiscalizar o limite de 3 tentativas para evitar custos e loops estéreis.

---

## 3. Inputs & Outputs
- **Inputs**: Stacktraces, mensagens de erro do compilador/interpretador, asserções falhadas de testes.
- **Outputs**: Hipóteses de diagnóstico, prompts de auto-reparo estruturados, relatórios de resolução.

---

## 4. State Management & Invariants
- Cada ciclo de reflexão incrementa o contador de auto-cura da tarefa; ao atingir o limiar máximo, o processo congela no estado `PAUSED_WAITING_HUMAN`.

---

## 5. Dependencies
- [`agents/tools.py`](file:///c:/Users/joaor/Desktop/JarvisOS/agents/tools.py)
- [`agents/patch_engine.py`](file:///c:/Users/joaor/Desktop/JarvisOS/agents/patch_engine.py)

---

## 6. Failure Modes & Recovery
- **Failure**: Hipótese de reflexão alucinada que sugere alterações irrelevantes.
- **Recovery**: O circuit breaker de hashing de patches detecta oscilação e aciona fallback para modelo frontier ou intervenção do operador.

---

## 7. Security Boundaries
- Todo o ciclo de auto-reparo é restrito aos ficheiros sob a governança da missão na sandbox.

---

## 8. Evidence Produced & Tests
- **Evidence**: Registos de reflexão em `telemetry_logs` com categoria `REFLECTIVE_HEALING`.
- **Tests**: `tests/test_model_harness_rho_she.py`.

---

## 9. Related Concepts
- [[Self-Healing Prompt Loops and Reflective Orchestration (RHO-SHE)]]
- [[Compiler Feedback and Test-Driven Self-Repair]]
- [[ADR-003 - Reflective Healing Orchestration (RHO) for Model Harness]]

