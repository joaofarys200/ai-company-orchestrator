---
type: concept
domain: business-economics
difficulty: intermediate
tags:
  - business
  - saas
  - churn
  - retention
  - cohorts
status: verified
---

# 📉 Churn Rate Analysis and Cohort Retention Curves

## 1. Definições: Logo Churn vs Revenue Churn

### 1.1. Logo Churn (Perda de Clientes)
A percentagem de clientes que cancelaram o serviço durante o mês:

$$\text{Logo Churn \%} = \frac{\text{Clientes Cancelados no Mês}}{\text{Total de Clientes no Início do Mês}} \times 100\%$$

### 1.2. Net Revenue Retention (NRR) / Net Dollar Retention (NDR)
Mede a percentagem de receita recorrente retida da mesma base de clientes ao longo do tempo, incluindo expansões (upsell), contrações (downsell) e cancelamentos:

$$\text{NRR \%} = \frac{\text{MRR Inicial} + \text{Expansão} - \text{Contração} - \text{Churn}}{\text{MRR Inicial}} \times 100\%$$
- **$\text{NRR} > 100\%$ (Negative Net Churn)**: A receita da base existente cresce mesmo sem adquirir novos clientes (o "Santo Graal" do SaaS). Empresas de topo apresentam $\text{NRR} \ge 120\%$.

---

## 2. Análise de Cohorts (Cohort Retention Matrix)

Uma tabela de cohorts agrupa clientes pelo mês de entrada ($M_0$) e rastreia a percentagem de retenção nos meses subsequentes ($M_1, M_2, \dots, M_{12}$):

| Cohort Mês | Novos Clientes | Mês 0 | Mês 1 | Mês 2 | Mês 3 | Mês 6 | Mês 12 |
|---|---|---|---|---|---|---|---|
| **Jan 2026** | 100 | 100% | 88% | 82% | 80% | 78% | 77% |
| **Fev 2026** | 120 | 100% | 90% | 85% | 83% | 81% | - |
| **Mar 2026** | 150 | 100% | 92% | 88% | 86% | - | - |

---

## 3. Curvas de Retenção e Product-Market Fit (PMF)
- **Curva que cai para Zero**: O produto não tem retenção duradoura (falta de Product-Market Fit).
- **Curva que Achata (Plateau)**: A retenção estabiliza (ex: em 75%), indicando uma base leal de utilizadores recorrentes.

---

## 4. Related Concepts
- [[SaaS Unit Economics - CAC, LTV and Magic Number]]
- [[Market Opportunity Discovery and Scoring Matrix]]
- [[Analise_Financeira_SaaS_e_Algoritmos_Estatisticos]]

---

## 5. Sources
- *Lenny's Newsletter - What is good retention? (B2B vs B2C Benchmarks)*: https://www.lennysnewsletter.com/
- *Tomasz Tunguz - The Anatomy of SaaS Churn*: https://tomtunguz.com/
