---
title: Lesson - Self-Improvement Cycle 2 - FINDING-02-NETWORK-RETRY-JITTER
component: backend/services/model_service.py
severity: HIGH
tags:
  - self-improvement
  - engineering-lesson
  - phase-7
---

# Failure
O componente `backend/services/model_service.py` apresentava o seguinte gap observado: Transient ConnectTimeout or ReadTimeout errors from cloud providers raise immediately without retry.

# Root Cause
execute_local() lacked bounded exponential backoff with jitter on transient network exceptions.

# Why Existing Protection Failed
As proteções existentes focavam-se em camadas downstream sem cache ou pré-validação na entrada.

# Corrective Action
Aplicado patch planeado `PLAN-02`: Add deterministic 2-attempt retry with jitter for transient connection errors.

# Generalizable Principle
Sempre aplicar defesa em profundidade e otimizações em memória com invalidação estrita em componentes de alto throughput.

# Tests Added
- `tests/test_model_service.py::test_retry_jitter`

# Evidence
- Redução de latência e ganho de resiliência comprovados empíricamente.

# Related Components
- [[JARVIS System Architecture]]
- [[JARVIS Component Architecture]]
