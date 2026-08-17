---
type: concept
domain: software-engineering
status: verified
source_type: PRIMARY_SOURCE
confidence: high
difficulty: advanced
tags:
  - software-engineering
  - ast
  - symbol-graphs
  - call-graphs
  - repo-indexing
prerequisites:
  - "[[Abstract Syntax Tree (AST) Parsing and Manipulation]]"
  - "[[Repository Understanding and Code Indexing]]"
related:
  - "[[Control Flow Graph (CFG) and Static Analysis]]"
  - "[[AST-Based Refactoring vs Regex Replacement]]"
used_by:
  - "[[JARVIS Autonomous Agent Hierarchy]]"
failure_modes:
  - "[[Lesson - Regex Refactoring Syntax Corruption]]"
implementation:
  - "[[JARVIS Component Architecture]]"
sources:
  - title: Precise Interprocedural Dataflow Analysis via Graph Reachability (Reps, Horwitz, Sagiv, POPL 1995)
    type: PRIMARY_SOURCE
    url: https://dl.acm.org/doi/10.1145/199448.199462
---

# 🕸️ Symbol Dependency Graphs and Call Graph Indexing

## 1. Pergunta Central
> *Como agentes de código mapeiam a cadeia completa de impacto de uma refatoração em larga escala antes de modificar uma única linha de código?*

---

## 2. A Estrutura do Grafo de Símbolos

```
[ Módulo A: server.py ] ------------------------------------+
       | (chama)                                            | (chama)
       v                                                    v
[ Símbolo: ConnectionManager.broadcast ]        [ Símbolo: get_db_session ]
       | (invocado por)                                     | (depende de)
       v                                                    v
[ Módulo B: gemini_live.py ]                    [ Módulo C: database.py ]
```

Um **Symbol Dependency Graph** $G = (S, E)$ indexa:
- **Nós ($S$)**: Funções, Classes, Métodos e Variáveis Globais com nomes qualificados (`package.module.ClassName.method_name`).
- **Arestas ($E$)**:
  - `calls`: Invocação direta de função.
  - `imports`: Importação de símbolo.
  - `inherits`: Relação de herança orientada a objetos.
  - `mutates`: Modificação de estado de atributos.

---

## 3. Algoritmo de Análise de Impacto (Blast Radius)
Quando Devon propõe alterar a assinatura de `ConnectionManager.broadcast(message: str)` para `ConnectionManager.broadcast(message: dict, sanitize: bool = True)`:
1. Uma busca em largura (**BFS**) no grafo reverso a partir de `broadcast` localiza todos os nós que possuem arestas de chamada direta ou indireta.
2. O agente gera automaticamente os testes de regressão para todos os nós no caminho de impacto.

---

## 4. Related Concepts
- [[Repository Understanding and Code Indexing]]
- [[Control Flow Graph (CFG) and Static Analysis]]
- [[Abstract Syntax Tree (AST) Parsing and Manipulation]]
