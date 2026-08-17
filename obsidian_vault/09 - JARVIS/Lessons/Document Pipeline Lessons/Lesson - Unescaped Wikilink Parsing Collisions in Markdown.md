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
Durante a indexaÃ§Ã£o do grafo de conhecimento, referÃªncias a caminhos de arquivos de cÃ³digo colocados dentro de colchetes duplos no frontmatter YAML (ex: `[database.py]` ou `[agents/patch_engine.py]`) foram incorretamente interpretadas como notas Markdown inexistentes no cofre, gerando 11 falsos alertas de links quebrados.

---

## Symptoms
- O validador de integridade do grafo reportou links quebrados para arquivos Python do sistema.
- Os visualizadores de grafos do Obsidian criaram nÃ³s fantasmas vazios na raiz do cofre.

---

## Detection
Script de auditoria de grafos em PowerShell identificou targets sem arquivo `.md` correspondente.

---

## Root Cause
ConfusÃ£o semÃ¢ntica entre caminhos fÃ­sicos de arquivos do repositÃ³rio (que devem ser formatados como markdown links normais `[database.py](file:///path)`) e nÃ³s conceituais do cofre Obsidian (que usam `[Nota Conceitual]`).

---

## Why Existing Protection Failed
O scanner de expressÃµes regulares buscava cegamente `\[\[(.*?)\]\]` em todo o conteÃºdo do documento sem distinguir blocos YAML de implementaÃ§Ãµes de referÃªncias conceituais.

---

## Blast Radius
PoluiÃ§Ã£o do grafo semÃ¢ntico e quebra na geraÃ§Ã£o de relatÃ³rios automatizados de qualidade.

---

## Recovery
Substituir todas as referÃªncias literais de cÃ³digo em `[...]` no frontmatter por referÃªncias aos nÃ³s arquiteturais correspondentes (ex: `[[JARVIS State Store and Persistence]]`).

---

## Corrective Action
Estabelecer regra de linter: `[...]` Ã© exclusivo para nÃ³s conceituais do cofre Obsidian; arquivos de cÃ³digo fonte do anfitriÃ£o usam links Markdown padrÃ£o com prefixo `file://`.

---

## Preventive Control
Adicionar validaÃ§Ã£o estrita no CI do cofre que rejeita extensÃµes `.py`, `.js` e barras `/` dentro de tags `[...]`.

---

## Generalizable Principle
> *No design de grafos de conhecimento para agentes, os nÃ³s conceituais (ontologia de conhecimento) devem ser mantidos estritamente desacoplados dos descritores de arquivos de cÃ³digo fonte (Ã¡rvore de assets), evitando colisÃµes de namespace entre os dois universos.*

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
- RelatÃ³rio de auditoria de grafo da Fase 3.

