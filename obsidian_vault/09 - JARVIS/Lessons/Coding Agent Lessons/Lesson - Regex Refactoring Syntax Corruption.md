---
type: lesson
domain: jarvis
source: production
severity: high
component: coding-agent
status: verified
source_type: JARVIS_INTERNAL
confidence: high
tags:
  - jarvis
  - lesson
  - coding-agent
  - devon
  - ast
  - regex
prerequisites:
  - "[[Abstract Syntax Tree (AST) Parsing and Manipulation]]"
  - "[[AST-Based Refactoring vs Regex Replacement]]"
related:
  - "[[Patch Generation and Safe Application]]"
  - "[[Compiler Feedback and Test-Driven Self-Repair]]"
  - "[[How to Safely Rollback Failed Code Changes]]"
used_by:
  - "[[JARVIS Autonomous Agent Hierarchy]]"
failure_modes:
  - "[[Safe Rollback and Git Transactional Strategies]]"
implementation:
  - "[[JARVIS System Architecture]]"
sources:
  - title: JARVIS Incident Report - Incident INC-2026-08-09
    type: JARVIS_INTERNAL
    url: internal://incidents/INC-2026-08-09
---

# 📝 Lesson - Regex Refactoring Syntax Corruption

## 1. Failure
O agente Devon foi instruído a renomear a variável `token` para `auth_token` num módulo central. O agente utilizou uma substituição baseada em expressões regulares ingênuas (`s/token/auth_token/g`), alterando inadvertidamente trechos dentro de strings literais (`"token_type"` $\rightarrow$ `"auth_token_type"`), docstrings e até o nome de classes dependentes, quebrando 14 testes unitários e introduzindo uma falha sintática silenciosa.

---

## 2. Root Cause
1. **Agnosticismo Sintático de Regex**: Expressões regulares tratam o código como um fluxo contínuo de caracteres sem noção de escopo léxico, AST ou fronteira de símbolos.
2. **Falta de Validação Pré-Escrita por Compilador**: O patch foi gravado diretamente no disco antes de passar por uma verificação em memória de AST (`ast.parse()`).

---

## 3. Why Existing Protection Failed
O motor de patching aceitou o comando de busca e substituição sem verificar se a âncora textual coincidia com múltiplos contextos léxicos diferentes no mesmo ficheiro.

---

## 4. Corrective Action
1. **Enforce de Refatoração por AST**: Renomeação de variáveis, métodos e classes passou a ser executada obrigatoriamente através do módulo `ast.NodeTransformer` ou RedBaron/Tree-sitter.
2. **Validação de Compilação em Sandbox (Pre-Commit Hook)**: O `SafePatcher` agora executa `python -m py_compile <temp_file>` antes de permitir a substituição atómica do ficheiro original.

---

## 5. Generalizable Principle
> *Nunca utilize expressões regulares para refatorações estruturais de código onde o contexto semântico da gramática seja relevante.*

---

## 6. Related Concepts
- [[AST-Based Refactoring vs Regex Replacement]]
- [[Abstract Syntax Tree (AST) Parsing and Manipulation]]
- [[Patch Generation and Safe Application]]
- [[Compiler Feedback and Test-Driven Self-Repair]]

---

## 7. Tests Added
- `tests/test_patch_engine_ast.py::test_symbol_rename_does_not_corrupt_string_literals`
- `tests/test_patch_engine_ast.py::test_syntax_validation_blocks_invalid_patches`
