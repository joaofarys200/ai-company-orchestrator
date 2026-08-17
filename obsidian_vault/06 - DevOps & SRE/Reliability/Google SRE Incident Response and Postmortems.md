---
type: concept
domain: devops
status: verified
source_type: PRIMARY_SOURCE
confidence: high
difficulty: intermediate
tags:
  - devops
  - sre
  - postmortems
  - incident-response
  - reliability
prerequisites:
  - "[[SLI-SLO Metrics and Error Budgets]]"
  - "[[SRE_Site_Reliability_Engineering_Body_of_Knowledge]]"
related:
  - "[[Healthchecks and Circuit Breakers]]"
  - "[[CI-CD Pipeline Failure Triage and Automated Healing]]"
used_by:
  - "[[JARVIS System Architecture]]"
failure_modes:
  - "[[Lesson - Unhandled Rate Limits and Context Explosion]]"
implementation:
  - "[[JARVIS Component Architecture]]"
sources:
  - title: Site Reliability Engineering - Postmortem Culture (Google SRE Book)
    type: PRIMARY_SOURCE
    url: https://sre.google/sre-book/postmortem-culture/
---

# 🚨 Google SRE Incident Response and Postmortems

## 1. Pergunta Central
> *Como estruturar um processo de resposta a incidentes e conduzir post-mortems sem culpabilização individual (Blameless Postmortems) para converter falhas em salvaguardas arquiteturais permanentes?*

---

## 2. Estrutura Canônica de um Blameless Postmortem (Google SRE)

```markdown
# Incident Postmortem: [INC-YYYY-MM-DD]

## Executive Summary
Breve sumário executivo com impacto no utilizador e tempo de indisponibilidade.

## Timeline
Cronologia detalhada em UTC:
- 14:00: Início do incidente (ex: aumento de 429 da API).
- 14:05: Disparo de alerta automático de queima de error budget.
- 14:15: Intervenção humana / ativação de fallback local.
- 14:20: Serviço totalmente restaurado.

## Root Cause Analysis (5 Whys)
Análise profunda da causa raiz sistêmica (não individual).

## Lessons Learned
- O que correu bem;
- O que correu mal;
- Onde tivemos sorte.

## Action Items (P0 / P1 / P2)
Ações corretivas com dono e prazo:
- [P0] Adicionar teste unitário de jitter no harness (Dono: Devon).
- [P1] Criar alerta de saturação de buffer de telemetria (Dono: Quinn).
```

---

## 3. Métricas Chave de Resiliência SRE
- **MTTD (Mean Time to Detect)**: Tempo decorrido entre o surgimento da falha e o primeiro alerta do monitor.
- **MTTR (Mean Time to Recover)**: Tempo decorrido entre a deteção do incidente e a restauração do SLO de produção.

---

## 4. Related Concepts
- [[SLI-SLO Metrics and Error Budgets]]
- [[Healthchecks and Circuit Breakers]]
- [[SRE_Site_Reliability_Engineering_Body_of_Knowledge]]
