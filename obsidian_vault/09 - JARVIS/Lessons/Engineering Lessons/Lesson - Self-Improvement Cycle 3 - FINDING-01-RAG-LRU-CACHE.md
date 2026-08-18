---
title: Lesson - Self-Improvement Cycle 3 - FINDING-01-RAG-LRU-CACHE
component: agents/obsidian_tools.py
severity: MEDIUM
tags:
  - self-improvement
  - engineering-lesson
  - phase-7
---

# Failure
O componente `agents/obsidian_tools.py` apresentava o seguinte gap observado: RAG query search scans all 199 files repeatedly on every request without in-memory query cache.

# Root Cause
Missing LRU cache decorator on the search scoring tokenizer.

# Why Existing Protection Failed
As proteções existentes focavam-se em camadas downstream sem cache ou pré-validação na entrada.

# Corrective Action
Aplicado patch planeado `PLAN-01`: Implement an in-memory thread-safe LRU cache with 256 entry capacity for tokenized scores.

# Generalizable Principle
Sempre aplicar defesa em profundidade e otimizações em memória com invalidação estrita em componentes de alto throughput.

# Tests Added
- `tests/test_obsidian_tools.py::test_lru_caching`

# Evidence
- Redução de latência e ganho de resiliência comprovados empíricamente.

# Related Components
- [[JARVIS System Architecture]]
- [[JARVIS Component Architecture]]
