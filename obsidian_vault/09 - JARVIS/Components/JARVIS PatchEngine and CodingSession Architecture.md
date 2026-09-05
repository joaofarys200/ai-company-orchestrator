---
type: architecture
domain: jarvis
status: verified
source_type: JARVIS_INTERNAL
confidence: high
difficulty: advanced
tags:
  - jarvis
  - patch-engine
  - coding-session
  - ast
  - devon
prerequisites:
  - "[[Patch Generation and Safe Application]]"
  - "[[Abstract Syntax Tree (AST) Parsing and Manipulation]]"
related:
  - "[[Compiler Feedback and Test-Driven Self-Repair]]"
  - "[[Safe Rollback and Git Transactional Strategies]]"
used_by:
  - "[[JARVIS Autonomous Agent Hierarchy]]"
failure_modes:
  - "[[Lesson - Regex Refactoring Syntax Corruption]]"
implementation:
  - "[[JARVIS Component Architecture]]"
sources:
  - title: JARVIS Codebase - agents/patch_engine.py and tests/test_coding_session.py
    type: JARVIS_INTERNAL
    url: internal://agents/patch_engine.py
---

# 🩹 JARVIS PatchEngine and CodingSession Architecture

## 1. Purpose
O `PatchEngine` e a `CodingSession` fornecem a infraestrutura de modificação atómica e segura de código utilizada pelo agente Devon, combinando diffs unificados com validação sintática pré-escrita por AST.

---

## 2. Responsibilities
- Gerar e aplicar diffs unificados em ficheiros de código fonte.
- Validar sintaxe em memória com `ast.parse()` antes de cometer qualquer alteração em disco.
- Manter uma sessão de codificação (`CodingSession`) com rollback atómico para reversão de alterações quebradas.
- Integrar linters e feedback de compilação diretamente no ciclo de auto-reparo.

---

## 3. Inputs & Outputs
- **Inputs**: Código fonte original, blocos de substituição ou diffs unificados gerados pelo LLM.
- **Outputs**: Ficheiros atualizados em disco, relatórios de validação sintática e testes.

---

## 4. State Management & Invariants
- Nenhuma alteração é gravada no ficheiro original se a validação sintática do novo código falhar.

---

## 5. Dependencies
- [`agents/patch_engine.py`](file:///c:/Users/joaor/Desktop/JarvisOS/agents/patch_engine.py)
- Módulo nativo Python `ast` e `difflib`.

---

## 6. Failure Modes & Recovery
- **Failure**: Conflito de âncoras ou diff malformado emitido pelo modelo.
- **Recovery**: Fallback para substituição de bloco exato ou regeneração do patch com contexto ampliado (ver [[Lesson - Regex Refactoring Syntax Corruption]]).

---

## 7. Security Boundaries
- Todas as gravações são estritamente contidas no diretório da sandbox pela `workspace_policy.py`.

---

## 8. Evidence Produced & Tests
- **Evidence**: Diff unificado registrado no log da sessão de codificação.
- **Tests**: `tests/test_coding_session.py`, `tests/test_atomic_text_edit.py`.

---

## 9. Related Concepts
- [[Patch Generation and Safe Application]]
- [[AST-Based Refactoring vs Regex Replacement]]
- [[Coding Agent Failure Mode and Recovery Matrix]]

