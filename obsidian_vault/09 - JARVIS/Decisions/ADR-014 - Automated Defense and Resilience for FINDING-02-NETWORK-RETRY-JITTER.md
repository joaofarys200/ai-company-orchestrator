---
title: ADR-014 - Automated Defense and Resilience for FINDING-02-NETWORK-RETRY-JITTER
status: ACCEPTED
date: 2026-08-24
---

# Context
Auditoria autónoma da Fase 7 identificou gap no componente `backend/services/model_service.py`.

# Decision
Implementar `Add deterministic 2-attempt retry with jitter for transient connection errors.` com validação em tempo real e rollback guard.

# Consequences
Aumento de resiliência sem introduzir regressões ou corrupção de estado.
