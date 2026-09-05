---
type: troubleshooting
domain: business-economics
difficulty: intermediate
tags:
  - business
  - troubleshooting
  - financial-metrics
  - nrr
  - gross-margin
status: verified
---

# 🛠️ï¸ How to Calculate Net Revenue Retention and Unit Margins

## 1. Objetivo & Fórmulas Contábeis
Este guia fornece as instruções passo a passo para calcular a Retenção Líquida de Receita (**NRR**) e a **Margem Bruta Unitária** em produtos SaaS e plataformas de IA.

---

## 2. Passo a Passo do Cálculo de NRR (Net Revenue Retention)

### Dados Necessários para o Período (ex: 12 meses):
1. **MRR Inicial ($R_0$)**: Receita mensal recorrente no início do período para a coorte selecionada.
2. **Receita de Expansão ($E$)**: Upgrades de plano, compra de créditos adicionais de IA pela mesma base.
3. **Receita de Contração ($C$)**: Downgrades de plano feitos pela base existente.
4. **Receita Perdida por Churn ($L$)**: Clientes que cancelaram integralmente.

### Fórmula:
$$\text{NRR \%} = \frac{R_0 + E - C - L}{R_0} \times 100\%$$

### Exemplo Numérico:
- $R_0 = \$10,000$
- $E = +\$2,500$ (clientes compraram mais uso de IA)
- $C = -\$500$ (downgrade)
- $L = -\$800$ (churn)
- $\text{NRR} = \frac{10000 + 2500 - 500 - 800}{10000} = \frac{11200}{10000} \times 100\% = 112.0\%$ (Excelente retenção com expansão líquida).

---

## 3. Passo a Passo do Cálculo da Margem Bruta Unitária de IA (AI Gross Margin)

Em produtos baseados em LLMs, os custos de bens vendidos (**COGS**) incluem:
- Custos de inferência de API (OpenAI, Anthropic, Gemini);
- Custos de GPU / servidores de inferência local (AWS EC2 / RunPod);
- Custos de computação da sandbox de execução de código;
- Custos de tráfego de rede e banco de dados vetorial.

### Fórmula:
$$\text{Margem Bruta \%} = \frac{\text{Preço Cobrado do Cliente} - \text{COGS de IA}}{\text{Preço Cobrado do Cliente}} \times 100\%$$
*(Padrão aceitável para SaaS de IA: $\ge 65\% - 75\%$).*

---

## 4. Implementação em Python

```python
def audit_financial_health(mrr_start: float, expansion: float, contraction: float, churn: float, revenue_per_task: float, cogs_per_task: float) -> dict:
    if mrr_start <= 0 or revenue_per_task <= 0:
        raise ValueError("Valores base devem ser maiores que zero.")

    nrr_pct = ((mrr_start + expansion - contraction - churn) / mrr_start) * 100.0
    unit_margin_pct = ((revenue_per_task - cogs_per_task) / revenue_per_task) * 100.0

    return {
        "nrr_pct": round(nrr_pct, 2),
        "nrr_healthy": nrr_pct >= 105.0,
        "unit_margin_pct": round(unit_margin_pct, 2),
        "margin_healthy": unit_margin_pct >= 70.0
    }
```

---

## 5. Related Concepts
- [[SaaS Unit Economics - CAC, LTV and Magic Number]]
- [[Churn Rate Analysis and Cohort Retention Curves]]
- [[Analise_Financeira_SaaS_e_Algoritmos_Estatisticos]]

---

## 6. Sources
- *Bessemer Venture Partners - Benchmarks for Cloud Giants*: https://www.bvp.com/atlas/scaling-to-100-million
- *SaaS Capital - What is Net Revenue Retention (NRR)?*: https://www.saas-capital.com/blog-posts/net-revenue-retention/

## Query Relevance
Como calcular retenção líquida nrr e margens brutas unitárias em SaaS.

