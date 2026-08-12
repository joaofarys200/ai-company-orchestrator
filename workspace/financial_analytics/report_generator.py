from __future__ import annotations

from workspace.financial_analytics.analyzer import FinancialMetrics, MonteCarloProjection


class FinancialReportGenerator:
    """Executive Financial Report Generator exporting Markdown and JSON summaries."""

    @staticmethod
    def generate_markdown_report(
        company_name: str,
        metrics: FinancialMetrics,
        projection: MonteCarloProjection,
    ) -> str:
        report = f"""# 📊 Relatório de Desempenho Financeiro & Projeção Executiva: {company_name}

> **Sumário Executivo**: Análise automatizada de métricas SaaS e projeções de receita geradas pelo motor JARVIS Financial Analytics.

---

## 📈 1. Métricas Chave de Desempenho (KPIs)

| Métrica Financeira | Valor Calculado | Padrão de Mercado | Avaliação |
|---|---|---|---|
| **MRR (Monthly Recurring Revenue)** | € {metrics.mrr:,.2f} | — | Base Ativa |
| **ARR (Annual Recurring Revenue)** | € {metrics.arr:,.2f} | — | Run-rate Anual |
| **Margem Bruta (Gross Margin)** | {metrics.gross_margin_pct:.1f}% | > 75.0% | {"✅ Excelente" if metrics.gross_margin_pct >= 75 else "⚠️ Atenção"} |
| **Margem EBITDA** | {metrics.ebitda_margin_pct:.1f}% | > 20.0% | {"✅ Saudável" if metrics.ebitda_margin_pct >= 20 else "⚠️ Em otimização"} |
| **CAC (Customer Acquisition Cost)** | € {metrics.cac:,.2f} | — | Custo Comercial |
| **LTV (Lifetime Value)** | € {metrics.ltv:,.2f} | — | Valor do Cliente |
| **Rácio LTV:CAC** | {metrics.ltv_cac_ratio:.2f}x | > 3.0x | {"✅ Excelente (>3x)" if metrics.ltv_cac_ratio >= 3.0 else "⚠️ Rever CAC"} |
| **NRR (Net Revenue Retention)** | {metrics.net_revenue_retention_pct:.1f}% | > 110.0% | {"✅ Forte Retenção" if metrics.net_revenue_retention_pct >= 100 else "⚠️ Atenção ao Churn"} |

---

## 🎲 2. Simulação Monte Carlo de Projeção de MRR ({projection.months} Meses)

- **MRR Inicial**: € {projection.starting_mrr:,.2f}
- **Cenário Pessimista (Percentil 10)**: € {projection.p10_final_mrr:,.2f}
- **Cenário Esperado (Percentil 50)**: € {projection.p50_final_mrr:,.2f}
- **Cenário Otimista (Percentil 90)**: € {projection.p90_final_mrr:,.2f}

---

*Gerado autonomamente pelo JARVIS OS Cognitive Engine.*
"""
        return report


__all__ = ["FinancialReportGenerator"]
