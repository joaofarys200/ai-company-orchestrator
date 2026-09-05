---
type: architecture
domain: jarvis
status: verified
source_type: JARVIS_INTERNAL
confidence: high
difficulty: advanced
tags:
  - jarvis
  - evidence-gateway
  - market-verification
  - validation-gate
  - alex
prerequisites:
  - "[[Distinguishing Real vs Synthetic Market Evidence]]"
  - "[[Market Opportunity Discovery and Scoring Matrix]]"
related:
  - "[[JARVIS EconomicExecutionGateway and Monetization]]"
  - "[[How to Validate Product Ideas with Low-Cost Experiments]]"
used_by:
  - "[[JARVIS Autonomous Agent Hierarchy]]"
failure_modes:
  - "[[Lesson - Synthetic Evidence Hallucination in Market Validation]]"
implementation:
  - "[[JARVIS Economic Engine and Metric Verification]]"
sources:
  - title: JARVIS Codebase - Evidence Gateway and Verification Contracts
    type: JARVIS_INTERNAL
    url: internal://workspace/financial_analytics/report_generator.py
---

# ðŸ” JARVIS EvidenceGateway and Market Verification Gate

## 1. Purpose
O `EvidenceGateway` atua como a barreira de integridade epistêmica do JARVIS OS, garantindo que propostas de produtos, hipóteses de negócio e scores de oportunidade sejam validados contra evidências reais antes da alocação de recursos de engenharia.

---

## 2. Responsibilities
- Auditar e classificar toda a evidência apresentada pelo agente Alex.
- Exigir comprovativos de interesse de utilizadores (ex: cliques reais em landing page, pré-inscrições por email, conversões de pagamento).
- Rejeitar planos baseados unicamente em consenso sintético de LLMs.
- Gerar relatórios de validação com graus de certeza explícitos.

---

## 3. Inputs & Outputs
- **Inputs**: Relatórios de mercado do Alex, dados de tráfego web, formulários de captura de leads.
- **Outputs**: Certificado de validação de evidência, pontuação de confiança auditada.

---

## 4. State Management & Invariants
- Nenhuma missão de escala ou lançamento pode prosseguir sem a chancela do `EvidenceGateway`.

---

## 5. Dependencies
- [`workspace/financial_analytics/analyzer.py`](file:///c:/Users/joaor/Desktop/JarvisOS/workspace/financial_analytics/analyzer.py)

---

## 6. Failure Modes & Recovery
- **Failure**: Tentativa de burlar o gateway com dados simulados.
- **Recovery**: Bloqueio e requisição de teste de fumaça com utilizadores reais (ver [[How to Validate Product Ideas with Low-Cost Experiments]]).

---

## 7. Security Boundaries
- Garante que dados de utilizadores capturados em landing pages respeitem regras de privacidade e mascaramento.

---

## 8. Evidence Produced & Tests
- **Evidence**: Registo de evidência auditada com selo criptográfico SHA-256.
- **Tests**: `tests/test_financial_analytics.py`.

---

## 9. Related Concepts
- [[Distinguishing Real vs Synthetic Market Evidence]]
- [[JARVIS Economic Engine and Metric Verification]]
- [[ADR-005 - Economic Evidence Provenance and Synthetic Data Capping]]

