---
type: concept
domain: business-economics
difficulty: intermediate
tags:
  - business
  - saas
  - economics
  - cac
  - ltv
  - magic-number
status: verified
---

# 💰 SaaS Unit Economics - CAC, LTV and Magic Number

## 1. Definições e Formulação Matemática Rigorosa

### 1.1. Customer Acquisition Cost (CAC)
O custo total para adquirir um único cliente pagante durante um período $T$:

$$\text{CAC} = \frac{\sum \text{Custos de Vendas} + \sum \text{Custos de Marketing}}{\text{Novos Clientes Pagantes Adquiridos}}$$

### 1.2. Customer Lifetime Value (LTV)
O valor presente líquido do lucro bruto que um cliente gera durante todo o seu relacionamento comercial:

$$\text{LTV} = \frac{\text{ARPU} \times \text{Margem Bruta \%}}{\text{Taxa de Churn Mensal \%}}$$

Onde:
- $\text{ARPU}$ (*Average Revenue Per User*): Receita média mensal por cliente.
- $\text{Margem Bruta \%} = \frac{\text{Receita} - \text{COGS (Hosting, APIs, Suporte)}}{\text{Receita}} \times 100\%$.

### 1.3. Rácio LTV:CAC
- **$\text{LTV:CAC} < 1.0\text{x}$**: Modelo inviável; cada cliente consome mais capital do que gera.
- **$\text{LTV:CAC} \approx 3.0\text{x}$**: Padrão de excelência de mercado para SaaS saudável.
- **$\text{LTV:CAC} > 5.0\text{x}$**: Subinvestimento em crescimento; a empresa poderia investir mais agressivamente em aquisição.

### 1.4. CAC Payback Period (Meses para Recuperação do CAC)
O número de meses necessários para recuperar o capital investido para adquirir o cliente:

$$\text{CAC Payback} = \frac{\text{CAC}}{\text{ARPU} \times \text{Margem Bruta \%}}$$
*(Meta ideal: $\le 12\text{ meses}$).*

### 1.5. SaaS Magic Number (Eficiência de Vendas)
Mede a eficiência com que o investimento em vendas e marketing se converte em crescimento de receita recorrente anual (ARR):

$$\text{Magic Number} = \frac{(\text{Receita Trimestre } Q_t - \text{Receita Trimestre } Q_{t-1}) \times 4}{\text{Despesas de Vendas e Marketing em } Q_{t-1}}$$
- **$> 1.0$**: Eficiência fantástica; acelerar investimento em aquisição.
- **$0.75 - 1.0$**: Eficiência sustentável.
- **$< 0.75$**: Rever modelo de aquisição e conversão antes de escalar gastos.

---

## 2. Implementação em Python de Calculadora de Economia Unitária

```python
from dataclasses import dataclass

@dataclass
class UnitEconomicsReport:
    cac: float
    ltv: float
    ltv_to_cac: float
    payback_months: float
    is_healthy: bool

def compute_saas_metrics(
    sales_marketing_cost: float,
    new_customers: int,
    arpu_monthly: float,
    gross_margin_pct: float,
    monthly_churn_pct: float
) -> UnitEconomicsReport:
    if new_customers <= 0 or monthly_churn_pct <= 0:
        raise ValueError("Valores inválidos para cálculo.")

    cac = sales_marketing_cost / new_customers
    margin_decimal = gross_margin_pct / 100.0
    churn_decimal = monthly_churn_pct / 100.0
    
    ltv = (arpu_monthly * margin_decimal) / churn_decimal
    ltv_to_cac = ltv / cac
    payback_months = cac / (arpu_monthly * margin_decimal)
    
    is_healthy = (ltv_to_cac >= 3.0) and (payback_months <= 12.0)
    
    return UnitEconomicsReport(
        cac=round(cac, 2),
        ltv=round(ltv, 2),
        ltv_to_cac=round(ltv_to_cac, 2),
        payback_months=round(payback_months, 1),
        is_healthy=is_healthy
    )
```

---

## 3. Related Concepts
- [[SaaS Pricing Models and Monetization Strategies]]
- [[Churn Rate Analysis and Cohort Retention Curves]]
- [[Analise_Financeira_SaaS_e_Algoritmos_Estatisticos]]

---

## 4. Sources
- *David Skok - SaaS Metrics 2.0: A Guide to Measuring and Improving what Matters*: https://www.forentrepreneurs.com/saas-metrics-2/
- *Bessemer Venture Partners - State of the Cloud & SaaS Benchmarks*: https://www.bvp.com/atlas/state-of-the-cloud
