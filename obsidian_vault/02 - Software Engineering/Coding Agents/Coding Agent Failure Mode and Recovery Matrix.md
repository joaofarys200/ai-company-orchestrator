---
type: reference
domain: software-engineering
status: verified
source_type: SYNTHESIZED
confidence: high
difficulty: advanced
tags:
  - software-engineering
  - coding-agents
  - failure-modes
  - recovery-matrix
  - self-repair
prerequisites:
  - "[[Compiler Feedback and Test-Driven Self-Repair]]"
  - "[[Safe Rollback and Git Transactional Strategies]]"
related:
  - "[[Patch Generation and Safe Application]]"
  - "[[Symbol Dependency Graphs and Call Graph Indexing]]"
used_by:
  - "[[JARVIS Autonomous Agent Hierarchy]]"
failure_modes:
  - "[[Lesson - Regex Refactoring Syntax Corruption]]"
implementation:
  - "[[JARVIS Component Architecture]]"
sources:
  - title: SWE-bench - Can Language Models Resolve Real-World GitHub Issues? (Jimenez et al., ICLR 2024)
    type: PRIMARY_SOURCE
    url: https://arxiv.org/abs/2310.06770
---

# 📊 Matriz de Modos de Falha e Recuperacao de Agentes de Codigo Coding Agents

Esta matriz codifica os modos de falha mais frequentes em agentes autónomos de engenharia de software e coding agents (como Devon), estabelecendo mecanismos determinísticos de **Deteção**, **Prevenção**, **Recuperação** e **Evidência Observável**.

---

## 1. Matriz de Resiliência de Agentes de Código

| Failure Mode | Detection Mechanism | Prevention Strategy | Recovery Action | Observable Evidence |
|---|---|---|---|---|
| **1. Corrupção Sintática por Regex** | `ast.parse()` lança `SyntaxError` em memória | Banir substituição por string; forçar `ast.NodeTransformer` | Reverter para checkpoint Git da árvore limpa | AST Parse Error com linha e offset exatos |
| **2. Alucinação de Imports / Dependências** | `py_compile` ou `ModuleNotFoundError` no runner | Consulta obrigatória ao grafo de símbolos locais | Auto-instalação ou injeção de import canónico | Stacktrace de resolução de módulo em `sys.path` |
| **3. Quebra de Contrato de Tipagem** | Linter / MyPy reporta type mismatch | Schemas Pydantic estritos nas fronteiras de I/O | Regenerar chamada com coerção de tipos | Log de erro do analisador estático |
| **4. Evasão do Path Jail / Path Traversal** | Exceção em `workspace_policy.py` | Resolução canônica com `os.path.commonpath` | Bloqueio imediato e congelamento do agente | Evento de segurança no log de auditoria |
| **5. Loop de Auto-Reparo Estéril** | Contador de tentativas $N \ge 3$ ou hash de diff repetido | Circuit breaker com hashing de patches | Pausar missão e solicitar intervenção humana | Alerta WebSocket `MISSION_PAUSED_HUMAN` |
| **6. Exaustão de Context Window** | Harness alerta $Tokens > Budget$ | Poda de histórico e sumarização por AST | Compressão semântica e reset de mensagens efêmeras | Métricas de contagem de tokens por turno |

---

## 2. Related Concepts
- [[Compiler Feedback and Test-Driven Self-Repair]]
- [[Safe Rollback and Git Transactional Strategies]]
- [[Symbol Dependency Graphs and Call Graph Indexing]]
- [[Lesson - Regex Refactoring Syntax Corruption]]
