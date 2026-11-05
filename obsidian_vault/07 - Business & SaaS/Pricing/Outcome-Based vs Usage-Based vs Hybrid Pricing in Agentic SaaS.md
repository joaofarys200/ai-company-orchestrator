---
type: concept
domain: business-economics
difficulty: advanced
status: verified
source_type: PRIMARY_SOURCE
confidence: high
freshness: stable
tags:
  - business
  - saas
  - pricing
  - monetization
  - agentic-saas
  - outcome-based
---

# 🏷️ Outcome-Based vs Usage-Based vs Hybrid Pricing in Agentic SaaS

## 1. O Paradoxo da Compressão de Assentos (*Seat Compression*)
Quando um agente autónomo multiplica a produtividade de uma equipa ou resolve tickets/patches sem intervenção humana, o cliente precisa de **menos licenças por colaborador**. Cobrar exclusivamente *per-seat* penaliza a receita do fornecedor à medida que o produto entrega mais valor — exigindo alinhar a métrica de valor (*value metric*) com o trabalho efetivamente realizado.

---

## 2. Comparação de Arquiteturas de Monetização para Agentes

| Modelo de Pricing | Unidade de Cobrança | Vantagem Económica | Modo de Falha Comercial |
|---|---|---|---|
| **Per-Seat (Por Utilizador)** | `€/utilizador/mês` | Receita previsível para comprador CFO | Erosão de margem por *power users* e compressão de seats |
| **Usage-Based Puro (Tokens/API)** | `€/1M tokens` ou `€/minuto` | Protege 100% a margem bruta (COGS repassado) | Ansiedade de fatura imprevisível; cliente penalizado por loops do agente |
| **Outcome-Based (Por Resultado)** | `€/ticket resolvido`, `€/PR aceite` | Alinhamento máximo com ROI mensurável do cliente | Disputas de atribuição se o critério de "sucesso" for ambíguo |
| **Híbrido (Plataforma + Créditos/Outcomes)** | Base mensal + franquia de execuções verificadas | Combina ARR previsível com expansão líquida (NRR $> 120\%$) | Requer medidor transparente e limites configuráveis pelo cliente |

---

## 3. Regras de Desenho para Pricing de Resultados Verificados
1. **Critério Binário e Auditável de Sucesso**: Só cobrar *outcomes* que possuam verificação determinística aceita por ambas as partes (ex.: PR aprovado e *merged*, fatura reconciliada, ticket fechado sem reabertura em 72h).
2. **Nunca Cobrar Retentativas Internas ao Cliente**: Se o agente precisou de 4 loops de auto-correção (`RHO-SHE`) devido a falha própria, o cliente paga 1 tarefa/crédito — incentivando engenharia eficiente no fornecedor.
3. **Hard Spend Caps & Alertas Preventivos**: Expor alertas automáticos aos $50\%$, $80\%$ e $100\%$ da franquia para eliminar choques de faturação (*bill shock*), que são a principal causa de churn em modelos baseados em consumo.

---

## 4. Conceitos Relacionados & Fontes
- [[SaaS Pricing Models and Monetization Strategies]]
- [[Churn Rate Analysis and Cohort Retention Curves]]
- [[AI Inference Unit Economics - Token COGS, Gross Margin Erosion and Routing Arbitrage]]
- [[Economic Evidence Provenance - Real vs Synthetic vs Unverified]]
- **Fontes**: Ramanujam & Tacke (2016), *Monetizing Innovation*; OpenView Venture Partners, *The State of Usage-Based and Hybrid AI Pricing*.

