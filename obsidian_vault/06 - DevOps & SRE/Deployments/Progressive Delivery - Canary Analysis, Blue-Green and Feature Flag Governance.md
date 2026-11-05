---
type: concept
domain: devops
difficulty: advanced
status: verified
source_type: PRIMARY_SOURCE
confidence: high
freshness: stable
tags:
  - devops
  - sre
  - progressive-delivery
  - canary
  - blue-green
  - feature-flags
---

# 🚦 Progressive Delivery - Canary Analysis, Blue-Green and Feature Flag Governance

## 1. Desacoplamento entre Deploy e Release
Em engenharia de confiabilidade moderna, **Deploy** (instalar binários/containers em produção) e **Release** (expor comportamento novo a utilizadores reais) são eventos ortogonais. A **Progressive Delivery** limita o *blast radius* expondo alterações gradualmente sob avaliação estatística contínua de SLIs.

| Estratégia | Mecânica de Tráfego | Tempo de Rollback | Risco / Custo Principal |
|---|---|---|---|
| **Blue-Green** | Duas frotas completas; switch atómico no router/LB | Sub-segundo | $2\times$ capacidade temporária; exige DB compatível com ambas versões |
| **Canary Release** | $1\% \to 5\% \to 25\% \to 100\%$ com comparação *Canary vs Baseline* | Segundos | Requer volume mínimo de tráfego para poder estatístico |
| **Feature Flags** | Ramificação em runtime por `tenant_id`, coorte ou percentagem | Instantâneo (sem redeploy) | Dívida técnica combinatória ($2^k$ estados) se flags não tiverem TTL |

---

## 2. Julgamento Automatizado de Canary (Automated Canary Analysis)
Comparar o *Canary* contra a produção inteira da semana anterior falha devido a sazonalidade diária. O padrão correto instancia um grupo **Baseline fresco** de igual dimensão no mesmo instante $t$ e compara:
1. **Taxa de Erro (`5xx` / exceções)**: Teste exato de Fisher ou razão sequencial de probabilidades; abortar imediatamente se $\text{Error}_{\text{canary}} > \text{SLO}_{\text{burn\_threshold}}$.
2. **Distribuição de Latência (`P50`, `P95`, `P99`)**: Teste não-paramétrico de **Mann-Whitney U** (robusto contra caudas pesadas não-normais).

---

## 3. Governação Estrita de Feature Flags
1. **Classificação de Vida Útil**: *Release toggles* expiram obrigatoriamente em $\le 30$ dias após atingir $100\%$; *Kill switches* operacionais (ex.: desativar fallback externo pago) são permanentes e testados regularmente em Chaos Engineering.
2. **Invariante de Base de Dados**: Nunca acoplar um rollback de binário a uma migração SQL destrutiva (`DROP COLUMN`); aplicar sempre o padrão **Expand-and-Contract**.

---

## 4. Conceitos Relacionados & Fontes
- [[SLI-SLO Metrics and Error Budgets]]
- [[Healthchecks and Circuit Breakers]]
- [[Chaos Engineering and Fault Injection in Autonomous Swarms]]
- [[API Contract Evolution, Backward Compatibility and Schema Versioning]]
- **Fontes**: Beyer et al. (2018), *The Site Reliability Workbook* (Google SRE — *Canarying Releases*); Humble & Farley (2010), *Continuous Delivery*.

