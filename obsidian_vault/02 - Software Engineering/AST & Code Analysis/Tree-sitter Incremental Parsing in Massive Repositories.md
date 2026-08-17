---
type: concept
domain: software-engineering
status: verified
source_type: PRIMARY_SOURCE
confidence: high
freshness: stable
difficulty: advanced
tags:
  - software-engineering
  - tree-sitter
  - incremental-parsing
  - ast
  - repo-indexing
prerequisites:
  - "[[Abstract Syntax Tree (AST) Parsing and Manipulation]]"
  - "[[LALR and Recursive Descent Parsing]]"
related:
  - "[[Symbol Dependency Graphs and Call Graph Indexing]]"
  - "[[AST-Based Refactoring vs Regex Replacement]]"
used_by:
  - "[[JARVIS Autonomous Agent Hierarchy]]"
failure_modes:
  - "[[Lesson - Regex Refactoring Syntax Corruption]]"
implementation:
  - "[[JARVIS Component Architecture]]"
sources:
  - title: Tree-sitter - An Incremental Parsing System for Programming Tools (Max Brunsfeld, GitHub)
    type: PRIMARY_SOURCE
    url: https://tree-sitter.github.io/tree-sitter/
---

# 🌳 Tree-sitter Incremental Parsing in Massive Repositories

## 1. Pergunta Central
> *Como indexar e manter atualizadas árvores sintáticas concretas (CST/AST) de milhões de linhas de código em tempo real após cada edição atómica de ficheiro em menos de 1 milissegundo?*

---

## 2. O Mecanismo do Parsing Incremental
Compiladores tradicionais descartam a árvore inteira e reanalisam o arquivo do zero a cada alteração ($O(N)$).
O **Tree-sitter** utiliza um algoritmo baseado em **GLR (Generalized LR)** com reuso de nós da árvore anterior:

```
[ Árvore CST Anterior ] -> Nó A (Linhas 1-50) | Nó B Modificado (Linhas 51-53) | Nó C (Linhas 54-1000)
                                                    |
                                    (Edição do usuário: adiciona caractere)
                                                    |
                                                    v
[ Nova Árvore Reconstruída ] -> Reusa Nó A | Reparseia apenas Nó B (3 linhas!) | Ajusta offsets de Nó C
```

O tempo de reparse é proporcional ao tamanho da edição ($O(\Delta)$) e não ao tamanho do arquivo ($O(N)$), operando tipicamente em $50\mu\text{s} - 300\mu\text{s}$.

---

## 3. Consultas Estruturadas via S-Expressions (Tree-sitter Queries)
O Tree-sitter permite buscar padrões sintáticos de código usando queries declarativas em formato Lisp:

```scheme
(function_definition
  name: (identifier) @function.name
  parameters: (parameters) @function.params
  body: (block) @function.body)
```

---

## 4. Related Concepts
- [[Symbol Dependency Graphs and Call Graph Indexing]]
- [[Abstract Syntax Tree (AST) Parsing and Manipulation]]
- [[AST-Based Refactoring vs Regex Replacement]]
