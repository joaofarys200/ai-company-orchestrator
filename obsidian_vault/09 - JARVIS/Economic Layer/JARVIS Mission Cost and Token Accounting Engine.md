---
type: architecture
domain: jarvis
status: verified
source_type: JARVIS_INTERNAL
confidence: high
freshness: stable
difficulty: advanced
tags:
  - jarvis
  - cost-accounting
  - token-budget
  - economics
  - metrics
prerequisites:
  - "[[JARVIS MissionStateStore and Persistence Engine]]"
  - "[[SaaS Unit Economics - CAC, LTV and Magic Number]]"
related:
  - "[[Context Engineering and Compression]]"
  - "[[JARVIS Economic Engine and Metric Verification]]"
used_by:
  - "[[JARVIS Autonomous Agent Hierarchy]]"
failure_modes:
  - "[[Lesson - Unhandled Rate Limits and Context Explosion]]"
implementation:
  - "[[JARVIS State Store and Persistence]]"
sources:
  - title: JARVIS Codebase - agents/mission_state.py and tests/test_mission_state.py
    type: JARVIS_INTERNAL
    url: internal://agents/mission_state.py
---

# ðŸ’° JARVIS Mission Cost and Token Accounting Engine

## 1. Purpose
O motor de contabilidade de custos e tokens monitora e persiste o consumo exato de tokens de entrada (*Prompt Tokens*) e saÃ­da (*Completion Tokens*) de cada invocaÃ§Ã£o de modelo por agente em cada passo de uma missÃ£o, calculando o custo acumulado em dÃ³lares e aplicando limites orÃ§amentÃ¡rios (*Hard Budget Limits*).

---

## 2. Responsibilities
- Extrair metadados de uso (`usage: {prompt_tokens, completion_tokens, total_tokens}`) em todas as respostas de LLM.
- Multiplicar as contagens pelos preÃ§os unitÃ¡rios do modelo ativo (ex: $0.0015/1k tokens de entrada para modelos locais/cloud).
- Atualizar incrementalmente os campos `tokens_used` e `cost_estimate_usd` no `StepState` e no `MissionState`.
- Disparar alerta `BUDGET_THRESHOLD_REACHED` ao atingir 80% do orÃ§amento e congelar a missÃ£o se o limite de 100% for excedido.

---

## 3. Inputs & Outputs
- **Inputs**: Respostas brutas da API do modelo contendo objetos de usage.
- **Outputs**: MÃ©tricas financeiras e de tokens persistidas na tabela `steps` e transmitidas via telemetria WebSocket.

---

## 4. Dependencies
- [`agents/mission_state.py`](file:///c:/Users/joaor/Desktop/JarvisOS/agents/mission_state.py)
- [`tests/test_mission_state.py`](file:///c:/Users/joaor/Desktop/JarvisOS/tests/test_mission_state.py)

---

## 5. Failure Modes & Recovery
- **Failure**: Provedor nÃ£o retorna contagem de tokens (ex: streaming chunks sem uso).
- **Recovery**: Fallback para contagem estimada por tokenizer local `tiktoken` / `cl100k_base`.

---

## 6. Related Concepts
- [[Context Engineering and Compression]]
- [[SaaS Unit Economics - CAC, LTV and Magic Number]]
- [[JARVIS MissionStateStore and Persistence Engine]]

