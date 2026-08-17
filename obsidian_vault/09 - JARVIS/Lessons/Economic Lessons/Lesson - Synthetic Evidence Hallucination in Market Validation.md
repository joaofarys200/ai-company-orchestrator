---
type: lesson
domain: jarvis
source: production
severity: medium
component: economic-layer
status: verified
source_type: JARVIS_INTERNAL
confidence: high
tags:
  - jarvis
  - lesson
  - economics
  - market-validation
  - alex
prerequisites:
  - "[[Distinguishing Real vs Synthetic Market Evidence]]"
  - "[[Market Opportunity Discovery and Scoring Matrix]]"
related:
  - "[[SaaS Unit Economics - CAC, LTV and Magic Number]]"
  - "[[How to Validate Product Ideas with Low-Cost Experiments]]"
used_by:
  - "[[JARVIS Economic Engine and Metric Verification]]"
failure_modes:
  - "[[Hallucination Mitigation Techniques]]"
implementation:
  - "[[JARVIS Autonomous Agent Hierarchy]]"
sources:
  - title: JARVIS Incident Report - Incident INC-2026-08-16
    type: JARVIS_INTERNAL
    url: internal://incidents/INC-2026-08-16
---

# 📝 Lesson - Synthetic Evidence Hallucination in Market Validation

## 1. Failure
Numa missão de descoberta e validação de uma ideia de Micro-SaaS para desenvolvedores, o agente Alex gerou um relatório com pontuação de viabilidade extremamente elevada (RICE Score = 420), projetando uma taxa de conversão de 15% e receita mensal de $8,000. O cálculo baseou-se inteiramente em personas sintéticas simuladas pelo próprio LLM e respostas hipotéticas em fóruns, sem nenhuma transação, pré-venda ou tráfego real.

---

## 2. Root Cause
1. **Confusão Epistêmica entre Simulação e Validação Real**: O agente tratou a concordância de personas simuladas como evidência empírica de mercado.
2. **Falta de Restrição de Proveniência no Prompt de Scoring**: O algoritmo de pontuação RICE aceitou um multiplicador de Confiança alto ($Confidence = 0.9$) sem exigir fontes de dados verificáveis de pagamento ou analytics real.

---

## 3. Why Existing Protection Failed
O modelo não possuía um filtro de classificação de evidência obrigatório que distinguisse formalmente entre fatos de produção e suposições heurísticas.

---

## 4. Corrective Action
1. **Regra Inviolável de Confiança no RICE**: O fator $Confidence$ em relatórios de mercado é limitado a no máximo $0.2$ para simulações e só pode atingir $\ge 0.7$ com comprovativo de transações reais (Stripe, depósitos ou lista de espera verificada).
2. **Formalização Teórica**: Documentado na nota [[Distinguishing Real vs Synthetic Market Evidence]] e integrado no [[JARVIS Economic Engine and Metric Verification]].

---

## 5. Generalizable Principle
> *Em economia e validação de produtos, a simulação de comportamento de utilizador por IA tem valor preditivo nulo para compromisso financeiro real.*

---

## 6. Related Concepts
- [[Distinguishing Real vs Synthetic Market Evidence]]
- [[Market Opportunity Discovery and Scoring Matrix]]
- [[JARVIS Economic Engine and Metric Verification]]
- [[How to Validate Product Ideas with Low-Cost Experiments]]

---

## 7. Tests Added
- `tests/test_economic_validator.py::test_synthetic_data_caps_confidence_score`
- `tests/test_economic_validator.py::test_market_scoring_requires_real_evidence`
