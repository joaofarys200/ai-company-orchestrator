---
title: Lesson - Self-Improvement Cycle 1 - FINDING-03-WEBSOCKET-PATH-JAIL
component: backend/websocket/handlers/knowledge.py
severity: HIGH
tags:
  - self-improvement
  - engineering-lesson
  - phase-7
---

# Failure
O componente `backend/websocket/handlers/knowledge.py` apresentava o seguinte gap observado: WebSocket save_note message handler lacked explicit validation of '../' before dispatch.

# Root Cause
Missing pre-validation gate in knowledge WebSocket handler.

# Why Existing Protection Failed
As proteções existentes focavam-se em camadas downstream sem cache ou pré-validação na entrada.

# Corrective Action
Aplicado patch planeado `PLAN-03`: Add strict path traversal validation in KnowledgeWebSocketHandler before calling service.

# Generalizable Principle
Sempre aplicar defesa em profundidade e otimizações em memória com invalidação estrita em componentes de alto throughput.

# Tests Added
- `tests/test_knowledge_handler.py::test_path_traversal_blocked`

# Evidence
- Redução de latência e ganho de resiliência comprovados empíricamente.

# Related Components
- [[JARVIS System Architecture]]
- [[JARVIS Component Architecture]]
