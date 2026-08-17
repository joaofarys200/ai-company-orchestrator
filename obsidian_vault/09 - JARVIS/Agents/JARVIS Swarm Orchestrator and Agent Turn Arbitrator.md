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
  - swarm
  - crewai
  - agent-hierarchy
  - turn-arbitrator
  - skills
prerequisites:
  - "[[JARVIS Autonomous Agent Hierarchy]]"
  - "[[Planner-Executor Agent Pattern]]"
related:
  - "[[JARVIS MissionExecutorService and Autonomy Controller]]"
  - "[[Self-Healing Prompt Loops and Reflective Orchestration (RHO-SHE)]] "
used_by:
  - "[[JARVIS System Architecture]]"
failure_modes:
  - "[[Agent Loop Detection and Circuit Breaker]]"
implementation:
  - "[[JARVIS Component Architecture]]"
sources:
  - title: JARVIS Codebase - agents/swarm.py and agents/agent_profiles.py
    type: JARVIS_INTERNAL
    url: internal://agents/swarm.py
---

# ðŸ JARVIS Swarm Orchestrator and Agent Turn Arbitrator

## 1. Purpose
O mÃ³dulo `agents/swarm.py` orquestra a colaboraÃ§Ã£o hierÃ¡rquica entre mÃºltiplos agentes especializados (Clara, Devon, Alex, Quinn e subagentes especialistas), mapeando dinamicamente habilidades (*Agent Skills*) a partir de palavras-chave do prompt e gerenciando transiÃ§Ãµes de turno sem concorrÃªncia descontrolada.

---

## 2. Responsibilities
- Mapear papÃ©is a pacotes de habilidades especializadas (`_SKILL_AGENT_MAP` para `pm`, `qa`, `tester`, `designer`, `coder`, `dev_lead`, `sys_admin`, `ops_specialist`).
- Identificar automaticamente competÃªncias necessÃ¡rias via detecÃ§Ã£o de keywords em prompts (`_PROMPT_KEYWORD_SKILLS`).
- Injetar o conteÃºdo de instruÃ§Ãµes das habilidades (`.agents/skills/<skill>/SKILL.md`) no contexto do agente apropriado.
- Coordenar a execuÃ§Ã£o sequencial ou paralela de tarefas via CrewAI / Swarm.
- Arbitrar turnos de fala e evitar sobreposiÃ§Ãµes de comandos na sandbox.

---

## 3. Inputs & Outputs
- **Inputs**: SolicitaÃ§Ã£o do utilizador, perfil de missÃ£o, estado atual do repositÃ³rio.
- **Outputs**: Tarefas concluÃ­das, planos de execuÃ§Ã£o estruturados, relatÃ³rios de QA e PRs.

---

## 4. Dependencies
- [`agents/swarm.py`](file:///c:/Users/joaor/Desktop/JarvisOS/agents/swarm.py)
- [`agents/agent_profiles.py`](file:///c:/Users/joaor/Desktop/JarvisOS/agents/agent_profiles.py)
- [`agents/globals.py`](file:///c:/Users/joaor/Desktop/JarvisOS/agents/globals.py)

---

## 5. Failure Modes & Recovery
- **Failure**: Impasse entre agentes (*Deadlock de ColaboraÃ§Ã£o*) ou passagem de bastÃ£o infinita.
- **Recovery**: O `TurnArbitrator` impÃµe um teto estrito de $N \le 5$ handoffs por tarefa antes de invocar o `MissionAutonomyController`.

---

## 6. Related Concepts
- [[JARVIS Autonomous Agent Hierarchy]]
- [[Planner-Executor Agent Pattern]]
- [[Agent Loop Detection and Circuit Breaker]]

