---
type: lesson
domain: jarvis
status: verified
source_type: JARVIS_INTERNAL
confidence: high
freshness: stable
difficulty: intermediate
tags:
  - lesson
  - jarvis
  - markdown
  - wikilinks
  - parsing
  - knowledge-graph
prerequisites:
  - "[[Repository Understanding and Code Indexing]]"
related:
  - "[[JARVIS Obsidian Tools and RAG System]]"
  - "[[ADR-001 - Decoupled Obsidian Knowledge Vault for Agent Memory]]"
used_by:
  - "[[JARVIS Autonomous Agent Hierarchy]]"
failure_modes:
  - "[[AST-Based Refactoring vs Regex Replacement]]"
implementation:
  - "[[JARVIS Obsidian Tools and RAG System]]"
sources:
  - title: JARVIS Codebase - Obsidian Vault Wikilink Audit
    type: JARVIS_INTERNAL
    url: internal://agents/obsidian_tools.py
---

# ðŸ“ Lesson - Unescaped Wikilink Parsing Collisions in Markdown

## Failure
Durante a indexação do grafo de conhecimento, referências a caminhos de arquivos de código colocados dentro de colchetes duplos no frontmatter YAML (ex: `[database.py]` ou `[agents/patch_engine.py]`) foram incorretamente interpretadas como notas Markdown inexistentes no cofre, gerando 11 falsos alertas de links quebrados.

---

## Symptoms
- O validador de integridade do grafo reportou links quebrados para arquivos Python do sistema.
- Os visualizadores de grafos do Obsidian criaram nós fantasmas vazios na raiz do cofre.

---

## Detection
Script de auditoria de grafos em PowerShell identificou targets sem arquivo `.md` correspondente.

---

## Root Cause
Confusão semântica entre caminhos físicos de arquivos do repositório (que devem ser formatados como markdown links normais `[database.py](file:///path)`) e nós conceituais do cofre Obsidian (que usam `[Nota Conceitual]`).

---

## Why Existing Protection Failed
O scanner de expressões regulares buscava cegamente `\[\[(.*?)\]\]` em todo o conteúdo do documento sem distinguir blocos YAML de implementações de referências conceituais.

---

## Blast Radius
Poluição do grafo semântico e quebra na geração de relatórios automatizados de qualidade.

---

## Recovery
Substituir todas as referências literais de código em `[...]` no frontmatter por referências aos nós arquiteturais correspondentes (ex: `[[JARVIS State Store and Persistence]]`).

---

## Corrective Action
Estabelecer regra de linter: `[...]` é exclusivo para nós conceituais do cofre Obsidian; arquivos de código fonte do anfitrião usam links Markdown padrão com prefixo `file://`.

---

## Preventive Control
Adicionar validação estrita no CI do cofre que rejeita extensões `.py`, `.js` e barras `/` dentro de tags `[...]`.

---

## Generalizable Principle
> *No design de grafos de conhecimento para agentes, os nós conceituais (ontologia de conhecimento) devem ser mantidos estritamente desacoplados dos descritores de arquivos de código fonte (árvore de assets), evitando colisões de namespace entre os dois universos.*

---

## Tests
- `tests/test_obsidian_tools.py`

---

## Related Concepts
- [[Repository Understanding and Code Indexing]]
- [[ADR-001 - Decoupled Obsidian Knowledge Vault for Agent Memory]]
- [[AST-Based Refactoring vs Regex Replacement]]

---

## Related Runbooks
- [[How to Safely Validate and Apply Code Patches]]

---

## Evidence
- Relatório de auditoria de grafo da Fase 3.

