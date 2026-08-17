---
type: concept
domain: jarvis
difficulty: intermediate
tags:
  - jarvis
  - agents
  - swarm
  - clara
  - devon
  - alex
  - quinn
status: verified
---

# 👥 JARVIS Autonomous Agent Hierarchy

## 1. O Quarteto de Agentes Especialistas

O **JARVIS OS** orquestra 4 personas agênticas com competências, ferramentas e limites de autoridade estritamente definidos:

```
                      +----------------------------------+
                      |         CLARA (Manager)          |
                      |  - Planeamento Estratégico       |
                      |  - Decomposição de Missões (DAG) |
                      |  - Interface com Operador Humano |
                      +-----------------+----------------+
                                        |
                 +----------------------+----------------------+
                 |                                             |
                 v                                             v
+----------------------------------+          +----------------------------------+
|          DEVON (Engineer)        |          |          ALEX (Strategist)       |
|  - Engenharia de Software        |          |  - Pesquisa de Mercado           |
|  - Modificação de Código (AST)   |          |  - Validação Económica           |
|  - Execução de Patches & Build   |          |  - Modelagem de CAC / LTV        |
+----------------+-----------------+          +----------------+-----------------+
                 |                                             |
                 +----------------------+----------------------+
                                        |
                                        v
                      +----------------------------------+
                      |          QUINN (Quality/Sec)     |
                      |  - Execução de Testes Unitários  |
                      |  - Auditoria de Segurança & AST  |
                      |  - Gatekeeper para Merge / Deploy|
                      +----------------------------------+
```

---

## 2. Contratos de Papel e Ferramentas Autorizadas

| Agente | Papel Principal | Ferramentas Autorizadas | Nível de Autonomia |
|---|---|---|---|
| **Clara** | Gestão & Planeamento | `buscar_contexto_obsidian`, `criar_plano_missao`, `notificar_humano` | Alta (Estratégica) |
| **Devon** | Engenharia de Software | `read_file`, `write_to_file`, `apply_patch`, `execute_sandbox_cmd` | Bounded (Restrito à Sandbox) |
| **Alex** | Análise Económica & Negócio | `web_search`, `fetch_market_metrics`, `calcular_unit_economics` | Média (Somente Leitura / Pesquisa) |
| **Quinn** | Qualidade & Segurança | `run_test_suite`, `run_linter`, `audit_security_policy` | Determinística (Aprovação Binária) |

---

## 3. Protocolo de Transição e Handoff
1. **Clara** gera o plano com passos detalhados.
2. **Devon** implementa as alterações de código passo a passo.
3. **Quinn** valida as alterações com testes e linters. Se falhar $\rightarrow$ Devon recebe o feedback objetivo para auto-reparo. Se passar $\rightarrow$ Clara marca a etapa como concluída.

---

## 4. Related Concepts
- [[Planner-Executor Agent Pattern]]
- [[Compiler Feedback and Test-Driven Self-Repair]]
- [[JARVIS System Architecture]]
- [[JARVIS Security Sandbox and Policy Engine]]

---

## 5. Sources
- *JARVIS OS Swarm Specification — `agents/swarm.py`*
