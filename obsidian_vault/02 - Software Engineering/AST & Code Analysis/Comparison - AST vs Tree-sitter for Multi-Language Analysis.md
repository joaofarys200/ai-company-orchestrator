---
type: comparison
domain: software-engineering
status: verified
source_type: PRIMARY_SOURCE
confidence: high
freshness: stable
difficulty: advanced
tags:
  - software-engineering
  - comparison
  - ast
  - tree-sitter
  - code-analysis
prerequisites:
  - "[[Abstract Syntax Tree (AST) Parsing and Manipulation]]"
  - "[[Tree-sitter Incremental Parsing in Massive Repositories]]"
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
  - title: Python ast module documentation vs Tree-sitter Architecture
    type: PRIMARY_SOURCE
    url: https://docs.python.org/3/library/ast.html
---

# ⚖️ Comparison: Python AST vs Tree-sitter for Multi-Language Analysis

## 1. Tabela Comparativa de Capacidades

| Dimensão | Python `ast` Nativo | Tree-sitter Multi-Linguagem |
|---|---|---|
| **Linguagens Suportadas** | Estritamente Python | **40+ Linguagens (TS, JS, Rust, Go, Python, C++)** |
| **Parsing Incremental** | Não (Reparse completo do arquivo a cada edição) | **Sim (Atualização em microssegundos via GLR)** |
| **Tolerância a Erros Sintáticos** | Zero (Lança `SyntaxError` e aborta a árvore inteira) | **Alta (Constrói árvore parcial com nós `ERROR`)** |
| **Dependências Externas** | Zero (Biblioteca padrão do Python) | Requer bindings C/Rust compilados |
| **Nível de Detalhe da Árvore** | Árvore Sintática Abstrata (Omite comentários e pontuação) | Árvore Sintática Concreta (Preserva 100% dos bytes) |

---

## 2. Decisão de Engenharia para o JARVIS

### When should JARVIS choose Python `ast`?
- Para validação sintática pré-commit de código Python (`ast.parse(code)`).
- Para refatorações e transformações de código que rodam em ambientes restritos sem dependências nativas C.

### When should JARVIS choose Tree-sitter?
- Para indexação e busca de símbolos em repositórios poliglota (TypeScript, Rust, Go, Python).
- Para editores em tempo real e análise de código incompleto com erros parciais de digitação.

### What failure mode does each introduce?
- **Python `ast`**: Aborta a análise completa se houver um único erro de digitação no arquivo.
- **Tree-sitter**: Se a gramática estiver dessincronizada com uma nova versão da linguagem, pode gerar nós `ERROR` silenciosos.

---

## 3. Related Concepts
- [[Abstract Syntax Tree (AST) Parsing and Manipulation]]
- [[Tree-sitter Incremental Parsing in Massive Repositories]]
- [[Symbol Dependency Graphs and Call Graph Indexing]]
