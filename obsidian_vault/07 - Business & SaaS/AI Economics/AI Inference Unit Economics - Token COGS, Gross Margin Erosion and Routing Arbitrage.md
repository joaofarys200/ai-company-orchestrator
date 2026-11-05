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
  - ai-economics
  - unit-economics
  - token-cogs
  - gross-margin
---

# 💰 AI Inference Unit Economics - Token COGS, Gross Margin Erosion and Routing Arbitrage

## 1. Por que Produtos de IA Quebram a Margem Bruta Clássica de SaaS
No SaaS tradicional, o custo marginal de servir um utilizador adicional é quase nulo, resultando em margens brutas de $75\%\text{–}85\%$. Em sistemas agênticos, cada tarefa desencadeia múltiplos turnos de inferência, RAG, *thinking tokens* e retentativas de auto-cura, tornando o **COGS de Inferência** uma variável dominante que pode comprimir a margem bruta para $20\%\text{–}50\%$ ou torná-la negativa em *power users*.

O custo real por tarefa concluída ($C_{\text{task}}$) num pipeline multi-turno com taxa média de retentativa $r$ e taxa de acerto em cache de prefixo $h \in [0, 1]$ é:

$$C_{\text{task}} = (1 + r) \sum_{t=1}^{K} \left[ T_{\text{in}, t} \left((1 - h) P_{\text{in}} + h P_{\text{cache}}\right) + \left(T_{\text{think}, t} + T_{\text{out}, t}\right) P_{\text{out}} \right] + C_{\text{infra}}$$

onde tipicamente $P_{\text{out}} \approx 3\times\text{–}8\times P_{\text{in}}$ e $P_{\text{cache}} \approx 0.1\times\text{–}0.25\times P_{\text{in}}$.

---

## 2. Alavancas Estruturais de Proteção de Margem Bruta

| Alavanca de Engenharia | Impacto Direto na Equação | Ganho Típico de COGS |
|---|---|---|
| **Routing Arbitrage (Cascata Local/Small $\to$ Frontier)** | Envia $70\%\text{–}85\%$ de triagem/extração para modelo local (`qwen3.5:9b`) ou *flash/lite* | $-60\%$ a $-85\%$ no custo médio |
| **Prefix / Prompt Caching Estável** | Mantém prefixos de sistema e documentos estáticos no início do prompt ($h \uparrow$) | $-50\%$ a $-75\%$ em $P_{\text{in}}$ |
| **Eliminação de Retries Cegos ($r \downarrow$)** | Constrained decoding + bloqueio de retry duplicado em `429`/truncagem | $-20\%$ a $-40\%$ de desperdício |
| **Poda Estrutural de Contexto / AST** | Evita crescimento quadrático $\sum_{t=1}^K T_{\text{in}, t}$ em loops longos | $-40\%$ em missões multi-ficheiro |

---

## 3. Regra de Ouro Financeira (Gross Margin Floor)
Nenhum plano de preço fixo ilimitado (*flat-rate unlimited*) deve expor inferência frontier sem **teto rígido de orçamento por tenant** (*token budget cap*) ou degradação graciosa para modelos locais/leves após atingir o limiar de margem bruta mínima ($\text{GM} = \frac{\text{ARPU} - \text{COGS}}{\text{ARPU}} \ge 65\%$).

---

## 4. Conceitos Relacionados & Fontes
- [[SaaS Unit Economics - CAC, LTV and Magic Number]]
- [[How to Calculate Net Revenue Retention and Unit Margins]]
- [[Model Routing and Fallback Strategies]]
- [[JARVIS Mission Cost and Token Accounting Engine]]
- [[Outcome-Based vs Usage-Based vs Hybrid Pricing in Agentic SaaS]]
- **Fontes**: Andreessen Horowitz (a16z), *Navigating the High Cost of AI Compute*; Bessemer Venture Partners, *State of the Cloud & AI Unit Economics Benchmarks*.

