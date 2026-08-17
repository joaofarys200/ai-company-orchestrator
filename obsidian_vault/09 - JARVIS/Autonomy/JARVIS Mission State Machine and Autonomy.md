---
type: concept
domain: jarvis
difficulty: intermediate
tags:
  - jarvis
  - autonomy
  - state-machine
  - mission-lifecycle
status: verified
---

# 🔄 JARVIS Mission State Machine and Autonomy

## 1. Ciclo de Vida e Estados de Missão
Cada missão gerida pelo **JARVIS OS** transita por uma Máquina de Estados Finita (**FSM**) estrita, garantindo rastreabilidade, checkpointing e gates de aprovação humana:

```
[ PENDING ] 
     |
     v
[ PLANNING ] (Clara decompõe a missão em DAG de tarefas)
     |
     v
[ IN_PROGRESS ] (Devon/Alex executam tarefas na Sandbox)
     |
     +---> (Erro Repetido / Limite de Tentativas) -> [ PAUSED_WAITING_HUMAN ]
     |                                                      |
     |                                                      v (Operador Aprova/Ajusta)
     |                                               [ IN_PROGRESS ]
     v
[ VALIDATING ] (Quinn executa suites de testes e auditorias)
     |
     +---> (Testes Falham) -> Retorna a [ IN_PROGRESS ] para Self-Repair
     |
     v
[ COMPLETED ] (Sucesso 100% verificado)
```

---

## 2. Níveis de Autonomia Delimitada (Bounded Autonomy)
- **Nível 1 (Read-Only / Consulta)**: Leitura de código, busca no Obsidian, análise estática. Executado automaticamente sem bloqueios.
- **Nível 2 (Sandbox Modification)**: Edição de ficheiros e execução de comandos em `sandbox_dir/`. Auto-aprovado se os testes unitários passarem.
- **Nível 3 (Host / Deployment Modification)**: Operações que afetam ficheiros fora da sandbox, commits para o branch principal ou exclusão de bancos de dados. Exige **Aprovação Explícita do Operador Humano** via interface desktop.

---

## 3. Related Concepts
- [[Planner-Executor Agent Pattern]]
- [[Agent Loop Detection and Circuit Breaker]]
- [[JARVIS Autonomous Agent Hierarchy]]
- [[JARVIS Security Sandbox and Policy Engine]]

---

## 4. Sources
- *JARVIS OS Codebase — `agents/swarm.py`, `database.py`*
