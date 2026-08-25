---
title: ADR-014 - Automated Defense and Resilience for FINDING-03-WEBSOCKET-PATH-JAIL
status: ACCEPTED
date: 2026-08-24
---

# Context
Auditoria autónoma da Fase 7 identificou gap no componente `backend/websocket/handlers/knowledge.py`.

# Decision
Implementar `Add strict path traversal validation in KnowledgeWebSocketHandler before calling service.` com validação em tempo real e rollback guard.

# Consequences
Aumento de resiliência sem introduzir regressões ou corrupção de estado.
