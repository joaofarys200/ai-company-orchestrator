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

# ðŸ©¹ JARVIS PatchEngine and CodingSession Architecture

## 1. Purpose
O `PatchEngine` e a `CodingSession` fornecem a infraestrutura de modificaÃ§Ã£o atÃ³mica e segura de cÃ³digo utilizada pelo agente Devon, combinando diffs unificados com validaÃ§Ã£o sintÃ¡tica prÃ©-escrita por AST.

---

## 2. Responsibilities
- Gerar e aplicar diffs unificados em ficheiros de cÃ³digo fonte.
- Validar sintaxe em memÃ³ria com `ast.parse()` antes de cometer qualquer alteraÃ§Ã£o em disco.
- Manter uma sessÃ£o de codificaÃ§Ã£o (`CodingSession`) com rollback atÃ³mico para reversÃ£o de alteraÃ§Ãµes quebradas.
- Integrar linters e feedback de compilaÃ§Ã£o diretamente no ciclo de auto-reparo.

---

## 3. Inputs & Outputs
- **Inputs**: CÃ³digo fonte original, blocos de substituiÃ§Ã£o ou diffs unificados gerados pelo LLM.
- **Outputs**: Ficheiros atualizados em disco, relatÃ³rios de validaÃ§Ã£o sintÃ¡tica e testes.

---

## 4. State Management & Invariants
- Nenhuma alteraÃ§Ã£o Ã© gravada no ficheiro original se a validaÃ§Ã£o sintÃ¡tica do novo cÃ³digo falhar.

---

## 5. Dependencies
- [`agents/patch_engine.py`](file:///c:/Users/joaor/Desktop/JarvisOS/agents/patch_engine.py)
- MÃ³dulo nativo Python `ast` e `difflib`.

---

## 6. Failure Modes & Recovery
- **Failure**: Conflito de Ã¢ncoras ou diff malformado emitido pelo modelo.
- **Recovery**: Fallback para substituiÃ§Ã£o de bloco exato ou regeneraÃ§Ã£o do patch com contexto ampliado (ver [[Lesson - Regex Refactoring Syntax Corruption]]).

---

## 7. Security Boundaries
- Todas as gravaÃ§Ãµes sÃ£o estritamente contidas no diretÃ³rio da sandbox pela `workspace_policy.py`.

---

## 8. Evidence Produced & Tests
- **Evidence**: Diff unificado registrado no log da sessÃ£o de codificaÃ§Ã£o.
- **Tests**: `tests/test_coding_session.py`, `tests/test_atomic_text_edit.py`.

---

## 9. Related Concepts
- [[Patch Generation and Safe Application]]
- [[AST-Based Refactoring vs Regex Replacement]]
- [[Coding Agent Failure Mode and Recovery Matrix]]

